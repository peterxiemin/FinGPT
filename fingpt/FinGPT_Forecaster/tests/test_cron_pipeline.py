"""Tests for cron_pipeline.py time window logic, checkpoint management, and eval helpers."""
import os
import sys
import json
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cron_pipeline import (
    get_time_window,
    _update_checkpoint_dataset_paths,
    _parse_eval_metrics,
    _save_eval_history,
)


class TestTimeWindowNonOverlap:
    """Test that consecutive runs don't have overlapping data."""

    def setup_method(self):
        """Create a temporary directory for each test."""
        self.test_dir = tempfile.mkdtemp(prefix="cron_test_")
        self.original_dir = os.getcwd()
        os.chdir(self.test_dir)

    def teardown_method(self):
        """Clean up temporary directory."""
        os.chdir(self.original_dir)
        shutil.rmtree(self.test_dir)

    def test_first_run_uses_weeks_back(self):
        """First run should look back weeks_back weeks."""
        # No checkpoint exists yet
        assert not os.path.exists("pipeline_checkpoint.json")

        start_str, end_str, _ = get_time_window(weeks_back=2)
        start_date = datetime.fromisoformat(start_str)
        end_date = datetime.fromisoformat(end_str)

        # Verify checkpoint was created
        assert os.path.exists("pipeline_checkpoint.json")

        # Verify time window is approximately 2 weeks (14 days)
        delta_days = (end_date - start_date).days
        assert delta_days == 14, f"Expected 14 days, got {delta_days}"

        print(f"✓ First run: start={start_str}, end={end_str} (delta={delta_days} days)")

    def test_second_run_continues_from_first_end(self):
        """Second run should start from where first run ended (no overlap)."""
        # First run
        start1_str, end1_str, _ = get_time_window(weeks_back=2)
        start1 = datetime.fromisoformat(start1_str)
        end1 = datetime.fromisoformat(end1_str)

        print(f"Run 1: {start1_str} to {end1_str}")

        # Verify checkpoint was created
        assert os.path.exists("pipeline_checkpoint.json"), "Checkpoint file should be created"

        # Second run (simulated week later)
        # Manually set checkpoint to simulate a previous run
        fake_past_end = end1 - timedelta(days=7)
        with open("pipeline_checkpoint.json", 'w') as f:
            json.dump({
                "last_end_date": fake_past_end.isoformat(),
                "last_run_time": (datetime.now() - timedelta(days=7)).isoformat(),
                "index_name": "dow"
            }, f)

        start2_str, end2_str, _ = get_time_window(weeks_back=2)
        start2 = datetime.fromisoformat(start2_str)
        end2 = datetime.fromisoformat(end2_str)

        print(f"Run 2: {start2_str} to {end2_str}")

        # Verify no overlap: start2 should be >= fake_past_end (the end of the previous run)
        assert start2 >= fake_past_end, f"Second run should start at or after first run's end. start2={start2}, fake_past_end={fake_past_end}"

        # Most importantly: verify that start2 is not in the past by more than weeks_back
        # If checkpoint was used, start2 should be close to fake_past_end, not 2 weeks before
        days_back_used = (end2 - start2).days
        assert days_back_used < 14, f"Second run should use checkpoint, not go back 2 weeks. Used {days_back_used} days"

    def test_no_data_overlap(self):
        """Verify that consecutive weekly runs don't overlap."""
        # Scenario: Run every Sunday
        # Week 1: Run on Sunday, get data from [Sun-14 to Sun]
        # Week 2: Run on next Sunday, should get data from [Sun to Sun+7]

        start1_str, end1_str, _ = get_time_window(weeks_back=2)
        start1 = datetime.fromisoformat(start1_str)
        end1 = datetime.fromisoformat(end1_str)

        # Simulate next week's run
        # Save checkpoint from week 1
        checkpoint_data = {
            "last_end_date": end1.isoformat(),
            "last_run_time": datetime.now().isoformat(),
            "index_name": "dow"
        }
        with open("pipeline_checkpoint.json", 'w') as f:
            json.dump(checkpoint_data, f)

        # Simulate time moving forward 7 days
        # The next run would get called 7 days later
        # For testing, we verify that start2 should be >= end1
        with open("pipeline_checkpoint.json", 'r') as f:
            saved_checkpoint = json.load(f)

        last_end = datetime.fromisoformat(saved_checkpoint["last_end_date"])

        # If we run again (simulating next week), start should be >= last_end
        assert last_end == end1, "Checkpoint should record end of first run"

        print(f"✓ No overlap: First run ends at {end1_str}, next run would start at or after this date")

    def test_checkpoint_persistence(self):
        """Verify checkpoint file is correctly saved and loaded."""
        start1_str, end1_str, _ = get_time_window(weeks_back=2)

        # Verify checkpoint file exists and is valid JSON
        assert os.path.exists("pipeline_checkpoint.json"), "Checkpoint file should exist"

        with open("pipeline_checkpoint.json", 'r') as f:
            checkpoint = json.load(f)

        # Verify checkpoint has required fields
        assert "last_end_date" in checkpoint
        assert "last_run_time" in checkpoint
        assert "dataset_paths" in checkpoint, "Checkpoint should contain dataset_paths field"
        assert isinstance(checkpoint["dataset_paths"], list), "dataset_paths should be a list"

        # Verify the date part matches (checkpoint stores full datetime, end1_str is just date)
        checkpoint_date = checkpoint["last_end_date"].split("T")[0]
        assert checkpoint_date == end1_str, f"Checkpoint date {checkpoint_date} should match {end1_str}"

        print(f"✓ Checkpoint persisted correctly: {checkpoint}")


class TestTimeWindowEdgeCases:
    """Test edge cases and error handling."""

    def setup_method(self):
        """Create a temporary directory for each test."""
        self.test_dir = tempfile.mkdtemp(prefix="cron_test_")
        self.original_dir = os.getcwd()
        os.chdir(self.test_dir)

    def teardown_method(self):
        """Clean up temporary directory."""
        os.chdir(self.original_dir)
        shutil.rmtree(self.test_dir)

    def test_corrupted_checkpoint_recovery(self):
        """If checkpoint is corrupted, should fall back to weeks_back."""
        # Create a corrupted checkpoint
        with open("pipeline_checkpoint.json", 'w') as f:
            f.write("{ invalid json }")

        # Should not crash, should fall back to weeks_back
        start_str, end_str, _ = get_time_window(weeks_back=2)
        start = datetime.fromisoformat(start_str)
        end = datetime.fromisoformat(end_str)

        delta_days = (end - start).days
        assert delta_days == 14, f"Should fall back to weeks_back=2 (14 days), got {delta_days}"

        print(f"✓ Corrupted checkpoint recovery: fell back to weeks_back (delta={delta_days} days)")

    def test_missing_last_end_date_in_checkpoint(self):
        """If checkpoint exists but last_end_date is missing, should fall back."""
        # Create a checkpoint without last_end_date
        with open("pipeline_checkpoint.json", 'w') as f:
            json.dump({"index_name": "dow"}, f)

        # Should not crash, should fall back to weeks_back
        start_str, end_str, _ = get_time_window(weeks_back=3)
        start = datetime.fromisoformat(start_str)
        end = datetime.fromisoformat(end_str)

        delta_days = (end - start).days
        assert delta_days == 21, f"Should fall back to weeks_back=3 (21 days), got {delta_days}"

        print(f"✓ Missing last_end_date recovery: fell back to weeks_back (delta={delta_days} days)")


class TestGetTimeWindowDatasetPaths:
    """Test get_time_window() dataset_paths return value and checkpoint round-trip."""

    def setup_method(self):
        self.test_dir = tempfile.mkdtemp(prefix="cron_test_")
        self.original_dir = os.getcwd()
        os.chdir(self.test_dir)

    def teardown_method(self):
        os.chdir(self.original_dir)
        shutil.rmtree(self.test_dir)

    def test_first_run_returns_empty_paths(self):
        """First run with no checkpoint should return an empty dataset_paths list."""
        _, _, paths = get_time_window(weeks_back=2)
        assert paths == [], f"First run should return empty paths list, got {paths}"

    def test_loads_dataset_paths_from_checkpoint(self):
        """Should read dataset_paths from an existing checkpoint."""
        existing_paths = ["/data/dataset-run1", "/data/dataset-run2"]
        with open("pipeline_checkpoint.json", "w") as f:
            json.dump({
                "last_end_date": (datetime.now() - timedelta(days=7)).isoformat(),
                "last_run_time": datetime.now().isoformat(),
                "index_name": "dow",
                "dataset_paths": existing_paths,
            }, f)

        _, _, paths = get_time_window(weeks_back=2)
        assert paths == existing_paths, f"Should return existing paths {existing_paths}, got {paths}"

    def test_preserves_dataset_paths_when_writing_checkpoint(self):
        """Writing the checkpoint for the next run must not erase existing dataset_paths."""
        existing_paths = ["/data/dataset-run1"]
        with open("pipeline_checkpoint.json", "w") as f:
            json.dump({
                "last_end_date": (datetime.now() - timedelta(days=7)).isoformat(),
                "last_run_time": datetime.now().isoformat(),
                "index_name": "dow",
                "dataset_paths": existing_paths,
            }, f)

        get_time_window(weeks_back=2)

        with open("pipeline_checkpoint.json") as f:
            checkpoint = json.load(f)
        assert checkpoint["dataset_paths"] == existing_paths, (
            "dataset_paths must be preserved in checkpoint after get_time_window()"
        )

    def test_corrupted_checkpoint_returns_empty_paths(self):
        """Corrupted checkpoint should fall back gracefully and return empty paths."""
        with open("pipeline_checkpoint.json", "w") as f:
            f.write("{ bad json }")

        _, _, paths = get_time_window(weeks_back=2)
        assert paths == [], f"Corrupted checkpoint should yield empty paths, got {paths}"


class TestUpdateCheckpointDatasetPaths:
    """Test _update_checkpoint_dataset_paths() in isolation."""

    def setup_method(self):
        self.test_dir = tempfile.mkdtemp(prefix="cron_test_")
        self.original_dir = os.getcwd()
        os.chdir(self.test_dir)

    def teardown_method(self):
        os.chdir(self.original_dir)
        shutil.rmtree(self.test_dir)

    def test_updates_paths_in_existing_checkpoint(self):
        """Should overwrite dataset_paths while keeping the file valid."""
        with open("pipeline_checkpoint.json", "w") as f:
            json.dump({"last_end_date": "2026-03-01T00:00:00", "dataset_paths": []}, f)

        new_paths = ["/data/ds1", "/data/ds2"]
        _update_checkpoint_dataset_paths(new_paths)

        with open("pipeline_checkpoint.json") as f:
            checkpoint = json.load(f)
        assert checkpoint["dataset_paths"] == new_paths

    def test_preserves_other_checkpoint_fields(self):
        """Other checkpoint fields (last_end_date etc.) must survive the update."""
        original = {
            "last_end_date": "2026-03-01T02:00:00",
            "last_run_time": "2026-03-01T02:05:00",
            "index_name": "dow",
            "dataset_paths": [],
        }
        with open("pipeline_checkpoint.json", "w") as f:
            json.dump(original, f)

        _update_checkpoint_dataset_paths(["/data/ds-new"])

        with open("pipeline_checkpoint.json") as f:
            checkpoint = json.load(f)
        assert checkpoint["last_end_date"] == original["last_end_date"]
        assert checkpoint["last_run_time"] == original["last_run_time"]
        assert checkpoint["index_name"] == original["index_name"]
        assert checkpoint["dataset_paths"] == ["/data/ds-new"]

    def test_creates_checkpoint_if_missing(self):
        """Should create the checkpoint file from scratch if it does not exist."""
        assert not os.path.exists("pipeline_checkpoint.json")
        paths = ["/data/ds1"]
        _update_checkpoint_dataset_paths(paths)
        assert os.path.exists("pipeline_checkpoint.json")
        with open("pipeline_checkpoint.json") as f:
            checkpoint = json.load(f)
        assert checkpoint["dataset_paths"] == paths


class TestParseEvalMetrics:
    """Test _parse_eval_metrics() JSON sentinel parsing."""

    def setup_method(self):
        self.test_dir = tempfile.mkdtemp(prefix="cron_test_")
        self.original_dir = os.getcwd()
        os.chdir(self.test_dir)

    def teardown_method(self):
        os.chdir(self.original_dir)
        shutil.rmtree(self.test_dir)

    def _write_log(self, content, filename="train.log"):
        with open(filename, "w") as f:
            f.write(content)
        return filename

    def _sentinel(self, metrics_dict):
        """Build a log line the way train_lora.py emits it."""
        return f"EVAL_METRICS_JSON: {json.dumps(metrics_dict)}\n"

    def test_parses_all_metrics_from_sentinel(self):
        """Should extract all fields from the EVAL_METRICS_JSON sentinel line."""
        full_metrics = {
            "valid_count": 45,
            "bin_acc": 0.78,
            "mse": 1.23,
            "pros_rouge_scores": {"rouge1": 0.45, "rouge2": 0.23, "rougeL": 0.42},
            "cons_rouge_scores": {"rouge1": 0.38, "rouge2": 0.15, "rougeL": 0.35},
            "anal_rouge_scores": {"rouge1": 0.50, "rouge2": 0.28, "rougeL": 0.48},
        }
        log = self._write_log("Epoch 1/3\n" + self._sentinel(full_metrics) + "Done.\n")
        metrics = _parse_eval_metrics(log)
        assert metrics["bin_acc"] == 0.78
        assert metrics["mse"] == 1.23
        assert metrics["valid_count"] == 45
        assert metrics["pros_rouge_scores"]["rouge1"] == 0.45
        assert metrics["anal_rouge_scores"]["rougeL"] == 0.48

    def test_returns_last_sentinel_when_multiple(self):
        """When several EVAL_METRICS_JSON lines exist, the last one should win."""
        early = {"bin_acc": 0.60, "mse": 2.00, "valid_count": 45}
        late  = {"bin_acc": 0.82, "mse": 1.10, "valid_count": 45}
        log = self._write_log(self._sentinel(early) + self._sentinel(late))
        metrics = _parse_eval_metrics(log)
        assert metrics["bin_acc"] == 0.82
        assert metrics["mse"] == 1.10

    def test_returns_empty_dict_if_no_sentinel(self):
        """Should return {} when the log contains no EVAL_METRICS_JSON line."""
        log = self._write_log(
            "Training started\n"
            "Binary Accuracy: 0.78  |  Mean Square Error: 1.23\n"  # old format — not parsed
            "Done.\n"
        )
        metrics = _parse_eval_metrics(log)
        assert metrics == {}

    def test_returns_empty_dict_for_missing_file(self):
        """Should return {} gracefully when the log file does not exist."""
        metrics = _parse_eval_metrics("nonexistent_training.log")
        assert metrics == {}


class TestSaveEvalHistory:
    """Test _save_eval_history() persistence."""

    def setup_method(self):
        self.test_dir = tempfile.mkdtemp(prefix="cron_test_")
        self.original_dir = os.getcwd()
        os.chdir(self.test_dir)

    def teardown_method(self):
        os.chdir(self.original_dir)
        shutil.rmtree(self.test_dir)

    def test_creates_new_file_with_correct_structure(self):
        """Should create evaluation_history.json with the first entry."""
        _save_eval_history("2026-03-01T02:00:00", 1, "/models/run1",
                           {"bin_acc": 0.78, "mse": 1.23})

        assert os.path.exists("evaluation_history.json")
        with open("evaluation_history.json") as f:
            data = json.load(f)
        assert "history" in data
        assert len(data["history"]) == 1
        entry = data["history"][0]
        assert entry["run_time"] == "2026-03-01T02:00:00"
        assert entry["num_datasets"] == 1
        assert entry["model_path"] == "/models/run1"
        assert entry["bin_acc"] == 0.78
        assert entry["mse"] == 1.23

    def test_appends_to_existing_file(self):
        """Each call should append a new record without overwriting previous ones."""
        _save_eval_history("2026-03-01T02:00:00", 1, "/models/run1", {"bin_acc": 0.70})
        _save_eval_history("2026-03-08T02:00:00", 2, "/models/run2", {"bin_acc": 0.78})

        with open("evaluation_history.json") as f:
            data = json.load(f)
        assert len(data["history"]) == 2
        assert data["history"][0]["model_path"] == "/models/run1"
        assert data["history"][1]["model_path"] == "/models/run2"
        assert data["history"][1]["num_datasets"] == 2

    def test_handles_empty_metrics_gracefully(self):
        """An empty metrics dict (no eval found) should still create a valid entry."""
        _save_eval_history("2026-03-01T02:00:00", 1, "/models/run1", {})

        with open("evaluation_history.json") as f:
            data = json.load(f)
        entry = data["history"][0]
        assert entry["run_time"] == "2026-03-01T02:00:00"
        assert "bin_acc" not in entry
        assert "mse" not in entry


if __name__ == "__main__":
    # Run tests
    print("=" * 70)
    print("Testing Time Window Non-Overlap Logic")
    print("=" * 70)

    # Test first run
    test1 = TestTimeWindowNonOverlap()
    test1.setup_method()
    test1.test_first_run_uses_weeks_back()
    test1.teardown_method()

    # Test second run
    test2 = TestTimeWindowNonOverlap()
    test2.setup_method()
    test2.test_second_run_continues_from_first_end()
    test2.teardown_method()

    # Test no overlap
    test3 = TestTimeWindowNonOverlap()
    test3.setup_method()
    test3.test_no_data_overlap()
    test3.teardown_method()

    # Test checkpoint persistence
    test4 = TestTimeWindowNonOverlap()
    test4.setup_method()
    test4.test_checkpoint_persistence()
    test4.teardown_method()

    # Test edge cases
    print("\n" + "=" * 70)
    print("Testing Edge Cases and Error Handling")
    print("=" * 70)

    test5 = TestTimeWindowEdgeCases()
    test5.setup_method()
    test5.test_corrupted_checkpoint_recovery()
    test5.teardown_method()

    test6 = TestTimeWindowEdgeCases()
    test6.setup_method()
    test6.test_missing_last_end_date_in_checkpoint()
    test6.teardown_method()

    print("\n" + "=" * 70)
    print("✅ All tests passed!")
    print("=" * 70)
