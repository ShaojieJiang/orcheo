# Orcheo operations

Use this guide for day-to-day `orcheo` operations after booting succeeds.

## Workflows

Use workflow commands to list, inspect, upload, run, publish, and manage schedules.

### List and inspect workflows

```bash
orcheo workflow list
orcheo workflow show <workflow_id>
```

### Upload development workflow

```bash
orcheo workflow upload workflow.py
```

Useful upload flags:
- `--entrypoint` for explicit LangGraph entrypoint selection
- `--name` to rename uploaded workflow
- `--config` / `--config-file` for runnable config payload

### Reuploading after changes

```bash
# Reupload the workflow to the same workflow_id
orcheo workflow upload --id <workflow_id> workflow.py
```

### Run and evaluate workflows

```bash
orcheo workflow run <workflow_id>
orcheo workflow run <workflow_id> --inputs '{"key":"value"}'
orcheo workflow run <workflow_id> --inputs-file inputs.json
```

Useful execution flags:
- `--config` / `--config-file` for runnable config payload
- `--verbose` to print full payloads
- `--no-stream` to disable live streaming output

### Publish, schedule, and export workflows

```bash
orcheo workflow publish <workflow_id>
orcheo workflow publish <workflow_id> --require-login
orcheo workflow unpublish <workflow_id>
orcheo workflow schedule <workflow_id>
orcheo workflow unschedule <workflow_id>
orcheo workflow download <workflow_id> --format json -o workflow.json
```

### Delete workflows

```bash
orcheo workflow delete <workflow_id>
orcheo workflow delete <workflow_id> --force
```

## Credentials

Use credential commands to manage secrets in the Orcheo vault.

### List credentials

```bash
orcheo credential list
orcheo credential list --workflow-id <workflow_id>
```

### Create credentials

```bash
orcheo credential create <credential_name> --provider <provider_name> --secret <credential_value>
```

Useful create flags:
- `--access private|shared|public`
- `--workflow-id <workflow_id>`
- `--scope <scope>` (can be passed multiple times)
- `--kind <kind>`

### Update and delete credentials

```bash
orcheo credential update <credential_id> --secret <new_secret>
orcheo credential update <credential_id> --metadata '{"key":"value"}'
orcheo credential delete <credential_id>
orcheo credential delete <credential_id> --force
```

## Plugins

Use plugin commands to manage Orcheo plugins.

### List, show, and search plugins

```bash
orcheo plugin list
orcheo plugin show <plugin_name>
orcheo plugin doctor
```

### Install, update, and uninstall plugins

```bash
orcheo plugin install <ref>          # package, path, wheel, or git ref
orcheo plugin update <plugin_name>
orcheo plugin update --all
orcheo plugin uninstall <plugin_name>
orcheo plugin enable <plugin_name>
orcheo plugin disable <plugin_name>
```

### Scaffold a new plugin

```bash
orcheo plugin init <name>
orcheo plugin init my-plugin --author "Jane Doe" --exports "nodes,edges"
orcheo plugin init my-plugin --output-dir /tmp
```

This generates a complete package skeleton with `pyproject.toml`, manifest,
starter node implementation, and tests — no need to clone the template repo.
