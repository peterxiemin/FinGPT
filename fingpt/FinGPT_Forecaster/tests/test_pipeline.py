"""
Pipeline-level tests covering the fixes made in the automated pipeline integration.

Tests here are fast (mock heavy operations) and do NOT require GPU, real API keys,
or network access — with the exception of test_health_check_timeout which only
needs a closed TCP port.
"""
import os
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import datasets as hf_datasets


# ---------------------------------------------------------------------------
# data_pipeline.main() — return value
# ---------------------------------------------------------------------------

def test_data_pipeline_main_returns_absolute_path(tmp_path, monkeypatch):
    """main() must return an absolute path that exists on disk after saving."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import data_pipeline

    # Minimal HF DatasetDict to satisfy save_to_disk
    dummy_ds = hf_datasets.DatasetDict({
        "train": hf_datasets.Dataset.from_dict({
            "prompt": ["p1"], "answer": ["a1"],
            "label": ["U1"], "symbol": ["AAPL"], "period": ["x"]
        }),
        "test": hf_datasets.Dataset.from_dict({
            "prompt": [], "answer": [],
            "label": [], "symbol": [], "period": []
        }),
    })

    with patch("data_pipeline.prepare_data_for_symbol"), \
         patch("data_pipeline.query_gpt4"), \
         patch("data_pipeline.create_dataset", return_value=dummy_ds):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        result = data_pipeline.main({
            "index_name": "dow",
            "start_date": "2026-01-01",
            "end_date": "2026-02-15",
            "min_past_weeks": 1,
            "max_past_weeks": 4,
            "train_ratio": 0.8,
        })

    assert result is not None, "main() should return a path, not None"
    assert os.path.isabs(result), "returned path must be absolute"
    assert "fingpt-forecaster-dow-30" in result, "path must contain index name"
    assert os.path.exists(result), "dataset directory must exist on disk"


def test_data_pipeline_main_path_contains_dates(tmp_path, monkeypatch):
    """Dataset path must encode start/end dates and split params for traceability."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import data_pipeline

    dummy_ds = hf_datasets.DatasetDict({
        "train": hf_datasets.Dataset.from_dict({
            "prompt": ["p"], "answer": ["a"],
            "label": ["U1"], "symbol": ["AAPL"], "period": ["x"]
        }),
        "test": hf_datasets.Dataset.from_dict({
            "prompt": [], "answer": [], "label": [], "symbol": [], "period": []
        }),
    })

    with patch("data_pipeline.prepare_data_for_symbol"), \
         patch("data_pipeline.query_gpt4"), \
         patch("data_pipeline.create_dataset", return_value=dummy_ds):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        result = data_pipeline.main({
            "index_name": "dow",
            "start_date": "2026-01-01",
            "end_date": "2026-02-15",
            "min_past_weeks": 1,
            "max_past_weeks": 4,
            "train_ratio": 0.8,
        })

    # Dates are encoded as YYYYMMDD, params as integers/decimals stripped of dots
    assert "20260101" in result
    assert "20260215" in result
    assert "-1-4-08" in result   # min-max-ratio encoded


# ---------------------------------------------------------------------------
# train_lora sentinel parsing
# ---------------------------------------------------------------------------

def test_sentinel_parse_finds_path(tmp_path):
    """TRAINED_MODEL_PATH: sentinel is correctly extracted from training log."""
    fake_model_dir = tmp_path / "finetuned_models" / "auto-run-20260228"
    fake_model_dir.mkdir(parents=True)

    log_content = (
        "Loading model...\n"
        "Epoch 1/3: loss=0.45\n"
        f"TRAINED_MODEL_PATH: {fake_model_dir}\n"
        "Saving tokenizer...\n"
    )
    log_file = tmp_path / "training.log"
    log_file.write_text(log_content)

    # Replicate the parsing logic from cron_pipeline.step4_train_lora
    model_path = None
    with open(log_file) as fh:
        for line in fh:
            if line.startswith("TRAINED_MODEL_PATH:"):
                model_path = line.split("TRAINED_MODEL_PATH:", 1)[1].strip()
                break

    assert model_path == str(fake_model_dir), "sentinel value must be parsed exactly"
    assert os.path.isdir(model_path), "parsed path must point to an existing directory"


def test_sentinel_parse_absent_returns_none(tmp_path):
    """When sentinel line is absent, parser returns None (triggers mtime fallback)."""
    log_file = tmp_path / "training.log"
    log_file.write_text("Epoch 1/3: loss=0.45\nTraining complete.\n")

    model_path = None
    with open(log_file) as fh:
        for line in fh:
            if line.startswith("TRAINED_MODEL_PATH:"):
                model_path = line.split("TRAINED_MODEL_PATH:", 1)[1].strip()
                break

    assert model_path is None, "absent sentinel must yield None (mtime fallback)"


# ---------------------------------------------------------------------------
# _health_check — graceful timeout
# ---------------------------------------------------------------------------

def test_health_check_timeout_graceful():
    """_health_check returns False (not an exception) when no server is listening."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from cron_pipeline import _health_check

    # Port 19876 is almost certainly unused; use very short timeout for test speed
    result = _health_check(port=19876, timeout_secs=3, interval_secs=1)
    assert result is False, "_health_check must return False on timeout, not raise"


def test_health_check_succeeds_when_server_running(tmp_path):
    """_health_check returns True immediately when the port responds."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from cron_pipeline import _health_check
    import urllib.request

    # Mock urlopen to simulate a successful response
    mock_response = MagicMock()
    with patch("urllib.request.urlopen", return_value=mock_response):
        result = _health_check(port=7860, timeout_secs=10, interval_secs=1)

    assert result is True, "_health_check must return True when server responds"


# ---------------------------------------------------------------------------
# model_config.json write (step5 core logic)
# ---------------------------------------------------------------------------

def test_model_config_json_written_correctly(tmp_path, monkeypatch):
    """step5_deploy_model writes correct JSON and the path is recorded."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import cron_pipeline

    fake_model_path = str(tmp_path / "finetuned_models" / "test-run")
    Path(fake_model_path).mkdir(parents=True)

    # Patch manage.sh restart and health check so the test stays fast
    with patch("cron_pipeline.subprocess.run") as mock_run, \
         patch("cron_pipeline._health_check", return_value=True):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        monkeypatch.chdir(tmp_path)

        result = cron_pipeline.step5_deploy_model(fake_model_path)

    assert result is True
    config_path = tmp_path / "model_config.json"
    assert config_path.exists(), "model_config.json must be written"

    with open(config_path) as f:
        config = json.load(f)

    assert config["latest_model_path"] == fake_model_path
    assert "updated_at" in config
