# ChatKit Publish CLI Examples

The following examples demonstrate how to manage public ChatKit access using the
Orcheo CLI and MCP server tools.

## Publish a workflow

```bash
orcheo workflow publish wf-123 --require-login
```

The command confirms the action, toggles `require_login`, and prints the share URL
(e.g. `https://canvas.example.com/chat/wf-123`) alongside the one-time publish token.

MCP equivalent:

```python
result = client.call_tool(
    "workflows.publish",
    {"workflow_id": "wf-123", "require_login": True},
)
print(result["share_url"], result["publish_token"])
```

## Rotate the publish token

```bash
orcheo workflow rotate-token wf-123
```

CLI output includes the refreshed token once and reiterates the share link. Existing
sessions can finish, but new chats must use the rotated token.

MCP equivalent:

```python
result = client.call_tool("workflows.rotate_publish_token", {"workflow_id": "wf-123"})
print(result["workflow"]["share_url"], result["publish_token"])
```

## Unpublish a workflow

```bash
orcheo workflow unpublish wf-123
```

Unpublishing immediately revokes public access and removes the share URL from the
workflow metadata.

MCP equivalent:

```python
result = client.call_tool("workflows.unpublish", {"workflow_id": "wf-123"})
assert result["workflow"]["share_url"] is None
```
