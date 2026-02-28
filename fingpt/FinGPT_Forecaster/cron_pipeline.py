import os
import sys
import json
import time
import subprocess
import argparse
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("cron_pipeline.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("CronPipeline")

# Import pipeline components
from data_pipeline import main as run_data_pipeline


def get_time_window(weeks_back=2):
    """Calculate start_date and end_date for the pipeline (non-overlapping runs).

    On first run: returns [now - weeks_back, now]
    On subsequent runs: returns [last_run_end_date, now] to avoid data overlap
    """
    checkpoint_file = "pipeline_checkpoint.json"
    end_date = datetime.now()

    # Check if we have a previous checkpoint
    if os.path.exists(checkpoint_file):
        try:
            with open(checkpoint_file, 'r') as f:
                checkpoint = json.load(f)
                # Start from where the last run ended to avoid overlap
                start_date = datetime.fromisoformat(checkpoint["last_end_date"])
                logger.info(f"Using checkpoint: last run ended at {checkpoint['last_end_date']}")
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Checkpoint file corrupted ({e}); falling back to weeks_back={weeks_back}")
            start_date = end_date - timedelta(days=7 * weeks_back)
    else:
        # First run: look back weeks_back weeks
        logger.info(f"No checkpoint found; looking back {weeks_back} weeks")
        start_date = end_date - timedelta(days=7 * weeks_back)

    # Save checkpoint for next run
    try:
        with open(checkpoint_file, 'w') as f:
            json.dump({
                "last_end_date": end_date.isoformat(),
                "last_run_time": datetime.now().isoformat(),
                "index_name": "dow"  # Will be updated by step1_to_3_data_pipeline
            }, f, indent=2)
        logger.info(f"Updated checkpoint: next run will start from {end_date.isoformat()}")
    except Exception as e:
        logger.error(f"Failed to save checkpoint: {e}")

    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


def step1_to_3_data_pipeline(index_name="dow", weeks_back=2):
    """Run steps 1, 2, and 3: Acquire data, LLM analysis, and HF dataset creation."""
    logger.info("=== Starting Phase: Data Pipeline (Steps 1-3) ===")

    start_date, end_date = get_time_window(weeks_back)
    logger.info(f"Time window: {start_date} to {end_date}")

    args = {
        'index_name': index_name,
        'start_date': start_date,
        'end_date': end_date,
        'min_past_weeks': 1,
        'max_past_weeks': 4,
        'train_ratio': 0.8
    }

    try:
        # Run the full data pipeline; main() returns the absolute dataset path
        dataset_path = run_data_pipeline(args)
        if not dataset_path or not os.path.exists(dataset_path):
            logger.error(f"Dataset path returned by pipeline not found: {dataset_path}")
            return False, None

        logger.info(f"Data pipeline completed. Dataset verified at: {dataset_path}")
        return True, dataset_path

    except Exception as e:
        logger.error(f"Data pipeline failed: {e}", exc_info=True)
        return False, None


def step4_train_lora(dataset_path):
    """Run step 4: LoRA Fine-tuning, streaming output to a timestamped log."""
    logger.info("=== Starting Phase: Model Fine-tuning (Step 4) ===")
    logger.info(f"Using dataset: {dataset_path}")

    run_name = f"auto-finetune-{datetime.now().strftime('%Y%m%d%H%M')}"
    training_log = f"training_{datetime.now().strftime('%Y%m%d%H%M')}.log"

    script_dir = os.path.dirname(os.path.abspath(__file__))

    cmd = [
        "python", "train_lora.py",
        "--dataset", dataset_path,
        "--base_model", "llama3",
        "--run_name", run_name,
        "--num_epochs", "3",
        "--batch_size", "1",
        "--gradient_accumulation_steps", "8",
        "--learning_rate", "2e-5",
        "--max_length", "4096",
        "--load_in_4bit",
        "--ds_config", "none",
    ]

    logger.info(f"Executing training command: {' '.join(cmd)}")
    logger.info(f"Streaming training output to: {training_log}")

    try:
        env = os.environ.copy()
        env['WANDB_MODE'] = 'disabled'

        # Stream stdout/stderr directly to the log file instead of buffering in memory
        with open(training_log, 'w') as log_fh:
            result = subprocess.run(
                cmd,
                env=env,
                check=True,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=script_dir,
            )

        # Parse the sentinel line from the log to get the exact output dir
        model_path = None
        with open(training_log, 'r') as log_fh:
            for line in log_fh:
                if line.startswith("TRAINED_MODEL_PATH:"):
                    model_path = line.split("TRAINED_MODEL_PATH:", 1)[1].strip()
                    break

        if model_path and os.path.isdir(model_path):
            logger.info(f"Model path from sentinel: {model_path}")
            return True, model_path

        # Fallback: find latest subdir by mtime
        logger.warning("TRAINED_MODEL_PATH sentinel not found; falling back to mtime scan.")
        models_dir = "./finetuned_models"
        subdirs = [
            os.path.join(models_dir, d)
            for d in os.listdir(models_dir)
            if os.path.isdir(os.path.join(models_dir, d))
        ]
        if not subdirs:
            logger.error("No finetuned models found in ./finetuned_models.")
            return False, None

        latest_model = max(subdirs, key=os.path.getmtime)
        logger.info(f"Latest finetuned model (mtime fallback): {latest_model}")
        return True, latest_model

    except subprocess.CalledProcessError as e:
        logger.error(f"Training failed with exit code {e.returncode}. See {training_log} for details.")
        return False, None


def _health_check(port=7860, timeout_secs=600, interval_secs=15):
    """Poll localhost:{port} until it responds or timeout is reached."""
    import urllib.request
    import urllib.error

    url = f"http://localhost:{port}"
    deadline = time.time() + timeout_secs
    logger.info(f"Health check: polling {url} every {interval_secs}s (timeout {timeout_secs}s)…")

    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=5)
            logger.info(f"Health check passed — app responded on port {port}.")
            return True
        except (urllib.error.URLError, OSError):
            remaining = int(deadline - time.time())
            logger.info(f"App not ready yet; {remaining}s remaining. Retrying…")
            time.sleep(interval_secs)

    logger.warning(
        f"Health check timed out after {timeout_secs}s. "
        "The app may still be loading the model; check app.log for details."
    )
    return False


def step5_deploy_model(model_path):
    """Run step 5: Update model_config.json and restart the Gradio app via manage.sh."""
    logger.info("=== Starting Phase: Deployment (Step 5) ===")
    logger.info(f"Deploying model: {model_path}")

    config_path = "./model_config.json"

    try:
        # Update config file — json already imported at module level
        config = {"latest_model_path": model_path, "updated_at": datetime.now().isoformat()}
        with open(config_path, "w") as f:
            json.dump(config, f, indent=4)
        logger.info(f"Updated {config_path} with new model path.")

        # Delegate process management to manage.sh restart
        logger.info("Restarting Gradio application via manage.sh…")
        result = subprocess.run(
            ["bash", "manage.sh", "restart"],
            check=True,
            text=True,
            capture_output=True
        )
        logger.info(result.stdout.strip())
        if result.stderr.strip():
            logger.warning(result.stderr.strip())

        # Wait for the app to become healthy
        _health_check(port=7860, timeout_secs=600)

        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"manage.sh restart failed (exit {e.returncode}): {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Deployment failed: {e}", exc_info=True)
        return False


def run_cron(index_name="dow", weeks_back=2):
    logger.info("=========================================")
    logger.info(f"Starting Scheduled Pipeline Run at {datetime.now()}")

    # Steps 1-3
    success, dataset_path = step1_to_3_data_pipeline(index_name=index_name, weeks_back=weeks_back)
    if not success:
        logger.error("Pipeline aborted at Data Pipeline phase.")
        return

    # Step 4
    success, model_path = step4_train_lora(dataset_path)
    if not success:
        logger.error("Pipeline aborted at Training phase.")
        return

    # Step 5
    success = step5_deploy_model(model_path)
    if not success:
        logger.error("Pipeline aborted at Deployment phase.")
        return

    logger.info("=========================================")
    logger.info("Scheduled Pipeline Run Completed Successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser("FinGPT-Forecaster Cron Pipeline")
    parser.add_argument("--run", action="store_true", help="Run the pipeline immediately")
    parser.add_argument("--index", default="dow", choices=["dow", "euro", "crypto"],
                        help="Stock index to process (default: dow)")
    parser.add_argument("--weeks", default=2, type=int,
                        help="Number of weeks of history to fetch (default: 2)")
    args = parser.parse_args()

    if args.run:
        run_cron(index_name=args.index, weeks_back=args.weeks)
    else:
        print("Use --run to execute the pipeline.")
