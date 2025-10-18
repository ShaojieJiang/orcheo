from orcheo.observability.metrics import MetricEvent, MetricRecorder


def test_metric_recorder_summary() -> None:
    recorder = MetricRecorder()
    recorder.record(MetricEvent(name="runs", value=1, tags={"workflow": "abc"}))
    recorder.record(MetricEvent(name="runs", value=2, tags={"workflow": "abc"}))
    recorder.record(MetricEvent(name="runs", value=1, tags={"workflow": "xyz"}))

    summary = recorder.summary()
    assert summary["runs"]["workflow=abc"] == 3
    assert summary["runs"]["workflow=xyz"] == 1
