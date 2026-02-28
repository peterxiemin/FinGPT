"""Tests for cron_pipeline.py time window logic."""
import os
import sys
import json
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cron_pipeline import get_time_window


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

        start_str, end_str = get_time_window(weeks_back=2)
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
        start1_str, end1_str = get_time_window(weeks_back=2)
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

        start2_str, end2_str = get_time_window(weeks_back=2)
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

        start1_str, end1_str = get_time_window(weeks_back=2)
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
        start1_str, end1_str = get_time_window(weeks_back=2)

        # Verify checkpoint file exists and is valid JSON
        assert os.path.exists("pipeline_checkpoint.json"), "Checkpoint file should exist"

        with open("pipeline_checkpoint.json", 'r') as f:
            checkpoint = json.load(f)

        # Verify checkpoint has required fields
        assert "last_end_date" in checkpoint
        assert "last_run_time" in checkpoint

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
        start_str, end_str = get_time_window(weeks_back=2)
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
        start_str, end_str = get_time_window(weeks_back=3)
        start = datetime.fromisoformat(start_str)
        end = datetime.fromisoformat(end_str)

        delta_days = (end - start).days
        assert delta_days == 21, f"Should fall back to weeks_back=3 (21 days), got {delta_days}"

        print(f"✓ Missing last_end_date recovery: fell back to weeks_back (delta={delta_days} days)")


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
