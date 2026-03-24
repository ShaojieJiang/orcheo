# Coding Orcheo workflows

Use `orcheo code` to generate workflow or node scaffolds.
When unsure of the available options, use the `--help` flag to see all available options.
When writing code, don't use or declare private attributes (those starting with `_`) as these are not supported by the Orcheo runtime.

## Install the Orcheo library

```bash
uv pip install -U orcheo
```

## Generate starter code

```bash
orcheo code template -o workflow.py
```

## Inspect schemas while coding

```bash
orcheo node show <node_name>
orcheo edge show <edge_name>
orcheo agent-tool show <tool_name>
```
