from datetime import UTC

from orcheo.observability.metrics import SuccessMetricsTracker


def test_success_metrics_tracker_records_history() -> None:
    tracker = SuccessMetricsTracker()
    tracker.record_uv_install()
    tracker.record_github_star(2)
    tracker.record_quickstart_completion()
    tracker.record_failure(3)
    tracker.resolve_failure(1)

    summary = tracker.summary()
    assert summary["uv_installs"] == 1
    assert summary["github_stars"] == 2
    assert summary["quickstart_completions"] == 1
    assert summary["failure_backlog"] == 2

    history = tracker.history()
    assert len(history) == 5
    assert history[-1].recorded_at.tzinfo is UTC
