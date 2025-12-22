"""Tests for Celery task signal handlers in tasks.py."""

from __future__ import annotations
import time
from unittest.mock import MagicMock, patch


class TestTaskPrerunHandler:
    """Tests for task_prerun_handler signal."""

    def test_logs_task_start_with_task_id(self) -> None:
        """Test that prerun handler logs task start and records start time."""
        from orcheo_backend.worker.tasks import _task_start_times, task_prerun_handler

        task_id = "test-task-123"
        mock_task = MagicMock()
        mock_task.name = "test_task"

        # Clear any existing entries
        _task_start_times.clear()

        with patch("orcheo_backend.worker.tasks.logger") as mock_logger:
            task_prerun_handler(task_id=task_id, task=mock_task)

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0]
            assert "Task started" in call_args[0]
            assert task_id in _task_start_times

    def test_logs_unknown_task_name_when_task_is_none(self) -> None:
        """Test that prerun handler logs 'unknown' when task is None."""
        from orcheo_backend.worker.tasks import task_prerun_handler

        task_id = "orphan-task-456"

        with patch("orcheo_backend.worker.tasks.logger") as mock_logger:
            task_prerun_handler(task_id=task_id, task=None)

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0]
            assert "unknown" in str(call_args)

    def test_handles_none_task_id(self) -> None:
        """Test that prerun handler handles None task_id gracefully."""
        from orcheo_backend.worker.tasks import _task_start_times, task_prerun_handler

        initial_count = len(_task_start_times)
        mock_task = MagicMock()
        mock_task.name = "test_task"

        with patch("orcheo_backend.worker.tasks.logger") as mock_logger:
            task_prerun_handler(task_id=None, task=mock_task)

            mock_logger.info.assert_called_once()
            # None should not be added to start times
            assert len(_task_start_times) == initial_count


class TestTaskPostrunHandler:
    """Tests for task_postrun_handler signal."""

    def test_logs_task_completion_with_duration(self) -> None:
        """Test that postrun handler logs completion with duration."""
        from orcheo_backend.worker.tasks import _task_start_times, task_postrun_handler

        task_id = "completed-task-789"
        mock_task = MagicMock()
        mock_task.name = "completed_task"

        # Set up start time
        _task_start_times[task_id] = time.monotonic() - 0.5  # 500ms ago

        with patch("orcheo_backend.worker.tasks.logger") as mock_logger:
            task_postrun_handler(
                task_id=task_id, task=mock_task, retval={"status": "ok"}
            )

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0]
            assert "Task completed" in call_args[0]
            assert "duration" in call_args[0]
            # Verify start time was cleaned up
            assert task_id not in _task_start_times

    def test_logs_completion_without_duration_when_no_start_time(self) -> None:
        """Test that postrun handler logs without duration if start time missing."""
        from orcheo_backend.worker.tasks import _task_start_times, task_postrun_handler

        task_id = "no-start-time-task"
        mock_task = MagicMock()
        mock_task.name = "quick_task"

        # Ensure no start time exists
        _task_start_times.pop(task_id, None)

        with patch("orcheo_backend.worker.tasks.logger") as mock_logger:
            task_postrun_handler(task_id=task_id, task=mock_task, retval=None)

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0]
            assert "Task completed" in call_args[0]
            assert "duration" not in call_args[0]

    def test_logs_unknown_task_name_when_task_is_none(self) -> None:
        """Test that postrun handler logs 'unknown' when task is None."""
        from orcheo_backend.worker.tasks import task_postrun_handler

        task_id = "orphan-completed-task"

        with patch("orcheo_backend.worker.tasks.logger") as mock_logger:
            task_postrun_handler(task_id=task_id, task=None, retval=None)

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0]
            assert "unknown" in str(call_args)

    def test_handles_none_task_id(self) -> None:
        """Test that postrun handler handles None task_id gracefully."""
        from orcheo_backend.worker.tasks import task_postrun_handler

        mock_task = MagicMock()
        mock_task.name = "test_task"

        with patch("orcheo_backend.worker.tasks.logger") as mock_logger:
            task_postrun_handler(task_id=None, task=mock_task, retval=None)

            # Should log without crashing
            mock_logger.info.assert_called_once()


class TestTaskFailureHandler:
    """Tests for task_failure_handler signal."""

    def test_logs_task_failure_with_exception(self) -> None:
        """Test that failure handler logs error with exception details."""
        from orcheo_backend.worker.tasks import task_failure_handler

        task_id = "failed-task-123"
        mock_task = MagicMock()
        mock_task.name = "failing_task"
        exception = ValueError("Something went wrong")

        with patch("orcheo_backend.worker.tasks.logger") as mock_logger:
            task_failure_handler(task_id=task_id, task=mock_task, exception=exception)

            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args[0]
            assert "Task failed" in call_args[0]
            assert "Something went wrong" in str(call_args)

    def test_cleans_up_start_time_on_failure(self) -> None:
        """Test that failure handler cleans up start time."""
        from orcheo_backend.worker.tasks import _task_start_times, task_failure_handler

        task_id = "cleanup-task-456"
        mock_task = MagicMock()
        mock_task.name = "cleanup_task"

        # Set up start time
        _task_start_times[task_id] = time.monotonic()

        with patch("orcheo_backend.worker.tasks.logger"):
            task_failure_handler(task_id=task_id, task=mock_task, exception=None)

            # Verify start time was cleaned up
            assert task_id not in _task_start_times

    def test_logs_unknown_when_exception_is_none(self) -> None:
        """Test that failure handler logs 'unknown' when exception is None."""
        from orcheo_backend.worker.tasks import task_failure_handler

        task_id = "no-exception-task"
        mock_task = MagicMock()
        mock_task.name = "mystery_task"

        with patch("orcheo_backend.worker.tasks.logger") as mock_logger:
            task_failure_handler(task_id=task_id, task=mock_task, exception=None)

            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args[0]
            assert "unknown" in str(call_args)

    def test_logs_unknown_task_name_when_task_is_none(self) -> None:
        """Test that failure handler logs 'unknown' when task is None."""
        from orcheo_backend.worker.tasks import task_failure_handler

        task_id = "orphan-failed-task"

        with patch("orcheo_backend.worker.tasks.logger") as mock_logger:
            task_failure_handler(
                task_id=task_id, task=None, exception=ValueError("err")
            )

            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args[0]
            assert "unknown" in str(call_args)

    def test_handles_none_task_id_cleanup(self) -> None:
        """Test that failure handler handles None task_id for cleanup."""
        from orcheo_backend.worker.tasks import task_failure_handler

        mock_task = MagicMock()
        mock_task.name = "test_task"

        with patch("orcheo_backend.worker.tasks.logger") as mock_logger:
            # Should not crash with None task_id
            task_failure_handler(task_id=None, task=mock_task, exception=None)

            mock_logger.error.assert_called_once()
