# Troubleshooting

## Workflow uploading or running issues

Orcheo validates uploaded LangGraph scripts in a RestrictedPython sandbox.
Rejections usually mean the script uses syntax, imports, or runtime behavior
outside the sandbox policy.

What is allowed:
- Python code compiled with RestrictedPython plus async functions, `await`, and
  annotated assignments.
- Imports from allow-listed module prefixes only:
  `asyncio`, `json`, `langgraph`, `langchain*`, `orcheo`, `typing*`,
  `collections`, `dataclasses`, `datetime`, `functools`, `html`,
  `itertools`, `math`, `operator`, `pydantic`, `re`, `uuid`.
- Standard `if __name__ == "__main__":` guards (the sandbox sets `__name__` to
  `"__orcheo_ingest__"`, so guarded blocks do not run).

What is blocked or constrained:
- Importing non-allow-listed modules (for example `os`, `subprocess`, `socket`,
  or third-party packages outside the list).
- Relative imports (`from .foo import bar`).
- Scripts exceeding configured size or execution timeout limits.

How to fix common failures:
- `Import of module ... is not permitted`: replace the dependency with an
  allow-listed module or move the logic into Orcheo/server-side code.
- `Relative imports are not supported`: change to absolute imports from an
  allow-listed package.
- `ValidationError` during upload for a templated custom-node field, for
  example `Input should be a valid list` with
  `input_value='{{config.configurable.text_fields}}'`: ingestion validates the
  node constructor before runtime template resolution, so custom node fields
  must accept the unresolved template string. If the runtime value is expected
  to be a list/dict/bool/etc., widen the field annotation to also include
  `str` (for example `list[str] | str`). Orcheo runtime will resolve the
  template before node execution.
- `script exceeds size limit` (wording may vary): remove dead code, trim large
  constants/embedded assets, and move bulky data or helper logic into
  versioned modules imported from allow-listed packages.
- Timeout errors (for example `execution timed out`): reduce per-step work,
  split the graph into smaller nodes, or move long-running logic outside
  ingestion-time script execution.
