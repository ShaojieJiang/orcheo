"""Exception types raised during LangGraph ingestion."""


class ScriptIngestionError(RuntimeError):
    """Raised when a LangGraph script cannot be converted into a workflow graph."""


__all__ = ["ScriptIngestionError"]
