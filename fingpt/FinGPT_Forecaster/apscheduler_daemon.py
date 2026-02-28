#!/usr/bin/env python3
"""
APScheduler Daemon for FinGPT Forecaster Pipeline
Runs the cron_pipeline.py automatically on schedule
"""

import os
import sys
import subprocess
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scheduler.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("APScheduler-Daemon")


def run_pipeline():
    """Execute the FinGPT Forecaster pipeline"""
    logger.info("=" * 70)
    logger.info(f"🚀 Starting FinGPT Pipeline Run at {datetime.now()}")
    logger.info("=" * 70)

    try:
        result = subprocess.run(
            [
                sys.executable, "cron_pipeline.py",
                "--run", "--index", "dow", "--weeks", "2"
            ],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=False,  # Show output in real-time
            text=True,
            timeout=3600  # 1 hour timeout
        )

        if result.returncode == 0:
            logger.info("=" * 70)
            logger.info("✅ Pipeline completed successfully")
            logger.info("=" * 70)
        else:
            logger.error("=" * 70)
            logger.error(f"❌ Pipeline failed with exit code {result.returncode}")
            logger.error("=" * 70)

    except subprocess.TimeoutExpired:
        logger.error("❌ Pipeline timeout (exceeded 1 hour)")
    except Exception as e:
        logger.error(f"❌ Error running pipeline: {e}", exc_info=True)


def start_scheduler():
    """Start the APScheduler daemon"""
    logger.info("=" * 70)
    logger.info("🔧 Initializing APScheduler Daemon")
    logger.info("=" * 70)

    scheduler = BackgroundScheduler(
        job_defaults={
            'coalesce': True,  # Combine multiple missed jobs into one
            'max_instances': 1  # Only run one instance at a time
        }
    )

    # Schedule job: Every Sunday at 02:00 UTC
    # day_of_week: 0=Monday, 1=Tuesday, ..., 6=Sunday
    scheduler.add_job(
        run_pipeline,
        CronTrigger(day_of_week=6, hour=2, minute=0),
        id="fingpt_pipeline",
        name="FinGPT Forecaster Pipeline",
        replace_existing=True
    )

    scheduler.start()

    logger.info("=" * 70)
    logger.info("✅ Scheduler started successfully")
    logger.info("⏰ Schedule: Every Sunday at 02:00 UTC")
    logger.info("📝 Logs: cron_pipeline.log (pipeline) + scheduler.log (scheduler)")
    logger.info("=" * 70)
    logger.info("Press Ctrl+C to stop the scheduler")
    logger.info("=" * 70)

    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("=" * 70)
        logger.info("🛑 Shutting down scheduler...")
        scheduler.shutdown()
        logger.info("✅ Scheduler stopped")
        logger.info("=" * 70)
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Scheduler error: {e}", exc_info=True)
        scheduler.shutdown()
        sys.exit(1)


if __name__ == "__main__":
    start_scheduler()
