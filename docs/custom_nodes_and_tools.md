# Loading Custom Nodes and Agent Tools via `sitecustomize`

This guide explains how Orcheo developers can surface local, user-defined nodes and agent tools in the CLI (and other clients that use the same registries) without modifying the Orcheo codebase. The approach relies on Python's [`sitecustomize`](https://docs.python.org/3/library/site.html#module-site) hook to import your custom modules before the registries are queried.

## Overview

Orcheo exposes node and agent-tool catalogs through global registries populated by decorators:

- Nodes use `@registry.register(...)` from `orcheo.nodes.registry`.
- Agent tools use `@tool_registry.register(...)` from `orcheo.nodes.agent_tools.registry`.

When the CLI lists available nodes or tools, it simply reads the already-populated registries; it does not scan the filesystem. Therefore, custom nodes and tools appear only if their modules have been imported before the CLI requests the registry contents.

`sitecustomize` gives us a guaranteed import hook at interpreter startup, letting us import custom packages automatically. Once the modules run, their decorators populate the registries and the CLI displays them alongside the built-ins.

## Prepare a Custom Package

1. Create a Python package (for example `~/orcheo-custom/orcheo_custom/`).
2. Implement your nodes and tools inside that package, decorating each class or function with the appropriate registry decorator. Nodes should inherit from one of the base classes such as `TaskNode`, `AINode`, or `BaseNode`, and both nodes and tools must be registered with their corresponding metadata objects. Agent tools often combine the Orcheo registry decorator with LangChain's `@tool` helper so they work seamlessly in both contexts. Example:

   ```python
   # ~/orcheo-custom/orcheo_custom/nodes/my_custom_node.py
   from orcheo.nodes.base import TaskNode
   from orcheo.nodes.registry import NodeMetadata, registry

   @registry.register(
       NodeMetadata(
           name="my_custom_node",
           description="Demo node",
           category="custom",
       )
   )
   class MyCustomNode(TaskNode):
       ...
   ```

   ```python
   # ~/orcheo-custom/orcheo_custom/agent_tools/my_custom_tool.py
   from langchain_core.tools import tool
   from orcheo.nodes.agent_tools.registry import ToolMetadata, tool_registry

   @tool_registry.register(
       ToolMetadata(
           name="say_hello",
           description="Greets the user",
           category="custom",
       )
   )
   @tool
   def say_hello(name: str) -> str:
       return f"Hello, {name}!"
   ```

3. Expose the modules in `__init__.py` files so a single import pulls in all registrations:

   ```python
   # ~/orcheo-custom/orcheo_custom/nodes/__init__.py
   from . import my_custom_node  # noqa: F401
   ```

   ```python
   # ~/orcheo-custom/orcheo_custom/agent_tools/__init__.py
   from . import my_custom_tool  # noqa: F401
   ```

## Make the Package Importable

Add the custom directory to `PYTHONPATH` so both the CLI and the backend can import it:

```bash
export PYTHONPATH="${PYTHONPATH}:$HOME/orcheo-custom"
```

You can append this to your shell profile or integrate it into the process environment used to run Orcheo.

## Add `sitecustomize`

Create `~/orcheo-custom/sitecustomize.py` with the imports needed to register your modules:

```python
# ~/orcheo-custom/sitecustomize.py
import orcheo.nodes  # ensure built-in nodes register
import orcheo.nodes.agent_tools.tools  # ensure built-in tools register

import orcheo_custom.nodes  # trigger custom node registrations
import orcheo_custom.agent_tools  # trigger custom tool registrations
```

Because the directory is on `PYTHONPATH`, Python automatically imports `sitecustomize` during startup. The imports inside the file trigger the decorators and populate the registries before the CLI reads them.

If you have many custom packages, you can expand this file to import each one or loop over module names read from an environment variable.

## Verify in the CLI

With the environment configured, run the standard Orcheo CLI commands. For example:

```bash
orcheo node list
orcheo agent-tool list
```

Both commands should now include your custom entries. No modifications to the Orcheo repository are necessary—the `sitecustomize` hook ensures your modules register themselves ahead of time.

## Troubleshooting Tips

- If your custom entries do not appear, confirm that `PYTHONPATH` includes the directory containing `sitecustomize.py` and your package.
- Run `python -c "import sitecustomize"` to verify that Python can import the hook without errors.
- Ensure each module you expect to load is imported by `sitecustomize.py`; missing imports mean the decorators never execute.
- Inspect `registry.list_metadata()` or `tool_registry.list_agent_tools_data()` in a Python shell to confirm the registrations exist before invoking CLI commands.

This workflow keeps custom logic outside the Orcheo repository while still letting developers surface bespoke nodes and agent tools in the CLI and MCP interfaces.
