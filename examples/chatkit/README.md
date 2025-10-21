# ChatKit Embed Example

This minimal example shows how to embed the OpenAI ChatKit web component so it
can talk to the Orcheo backend. Update the constants at the bottom of
`embed.html` with the ID of a workflow that includes a chat trigger and (optionally)
the specific node identifier you want to exercise.

## Quick start

1. Install the backend dependencies and start the Orcheo backend on
   `http://localhost:8000`.
2. Save the workflow that you want to trigger via chat and copy its UUID.
3. Edit `embed.html` and replace the placeholder workflow (and node) identifiers.
4. Serve the file locally, for example:

   ```bash
   cd examples/chatkit
   python -m http.server 8090
   ```

5. Visit `http://localhost:8090/embed.html` and send a chat message. Each message
   is sent to `/api/chatkit` with the workflow headers so the backend dispatches
   the appropriate run.

The UI uses the same ChatKit component that is now integrated with Orcheo Canvas,
so any configuration changes you make here can be transferred to the application
with minimal adjustments.
