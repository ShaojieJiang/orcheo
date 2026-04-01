from orcheo_backend.app.history.models import RunHistoryRecord


def test_build_trace_update_returns_none_without_spans(monkeypatch):
    from orcheo_backend.app.trace_utils import build_trace_update

    record = RunHistoryRecord(
        workflow_id="workflow",
        execution_id="exec",
        runnable_config={"configurable": {}},
    )
    update = build_trace_update(record)
    assert update is None


def test_trace_update_includes_root(monkeypatch):
    from orcheo_backend.app.trace_utils import build_trace_update

    record = RunHistoryRecord(
        workflow_id="workflow",
        execution_id="exec",
        runnable_config={"configurable": {"thread_id": "thread"}},
    )
    step = record.append_step({"node": {"output": "value"}})
    update = build_trace_update(record, include_root=True, step=step)
    assert update is not None
