# ChatKit Embedding Guide

Learn how to drop the ChatKit bubble into any static HTML page and connect it to
Orcheo's published workflows. Use this guide in tandem with the demo at
`examples/chatkit-orcheo.html`, which ships a working implementation you can
copy/paste or customize.

## When to use this guide
- You have a workflow that is already published via `orcheo workflow publish`
  (with or without the `--require-login` flag).
- You want to embed a floating chat bubble in a marketing site, docs page, or
  prototype without pulling in the full Canvas frontend.
- You can point the page at an Orcheo backend that exposes `/api/chatkit` to the
  public internet. The backend may live on localhost for testing; the browser
  must be able to reach it directly.

## Prerequisites
1. **Published workflow** – run `orcheo workflow publish <workflow_id>` and grab
   the share URL (e.g. `https://canvas.example/chat/wf_123`).
2. **Backend URL** – the base `http(s)` origin where your Orcheo FastAPI server
  is running. The ChatKit JS client hits `${backend}/api/chatkit` for every
  message. Serve the HTML page itself via `http://` or `https://`; ChatKit iframes
  cannot initialize from a `file://` origin.
3. **Domain key** – set `window.ORCHEO_CHATKIT_DOMAIN_KEY` or configure
   `VITE_ORCHEO_CHATKIT_DOMAIN_KEY` if you are bundling assets. Local builds can
   default to `domain_pk_localhost_dev`.
4. **Optional cookies** – when `--require-login` is enabled, the page must be
   served from the same origin (or a domain that already carries the OAuth
   session cookies) so ChatKit can forward them via `credentials: "include"`.

## Embedding steps
1. **Load the ChatKit bundle**
   ```html
   <script
     async
     src="https://cdn.platform.openai.com/deployments/chatkit/chatkit.js"
     crossorigin="anonymous"
   ></script>
   ```
2. **Add a launcher + container** – place a floating button and a hidden panel
   that contains `<openai-chatkit>`. See `examples/chatkit-orcheo.html` for a
   fully styled version that mirrors the Canvas chat bubble UX.
3. **Capture configuration** – collect:
   - Backend base URL (`http://localhost:8000` for local dev)
   - Workflow share URL or ID (we parse either)
   - Optional display name for the bubble header
4. **Inject ChatKit options** – call `chatkit.setOptions({ ... })` once the
   widget is defined. Use the helper below to ensure every request carries the
   required `workflow_id` metadata for published workflows.
   ```js
   const fetchWithWorkflow = ({ workflowId, workflowName, backendBase }) => {
     const baseFetch = window.fetch.bind(window);
     const apiUrl = `${backendBase}/api/chatkit`;

     return async (input, init = {}) => {
       const requestInfo = input || apiUrl;
       const nextInit = { ...init, credentials: "include" };
       const headers = new Headers(nextInit.headers || {});
       const isJsonBody =
         typeof nextInit.body === "string" ||
         (headers.get("Content-Type") || "").includes("application/json");

       const serialize = (original) => {
         if (!original) {
           return JSON.stringify({
             workflow_id: workflowId,
             metadata: { workflow_name: workflowName, workflow_id: workflowId },
           });
         }
         const payload = JSON.parse(original);
         payload.workflow_id ||= workflowId;
         payload.metadata = {
           ...(payload.metadata || {}),
           workflow_name: workflowName,
           workflow_id: workflowId,
         };
         return JSON.stringify(payload);
       };

       if (isJsonBody || !nextInit.body) {
         const serialized = typeof nextInit.body === "string" ? nextInit.body : null;
         nextInit.body = serialize(serialized);
         headers.set("Content-Type", "application/json");
       }

       nextInit.headers = headers;
       const response = await baseFetch(requestInfo, nextInit);
       if (!response.ok) {
         console.error("ChatKit request failed", await response.clone().text());
       }
       return response;
     };
   };
   ```
5. **Wire up the bubble** – toggle the panel with CSS transitions, and block the
   send button until a workflow is configured. The example page polls the shadow
   DOM every ~800 ms to keep the composer disabled when needed.
6. **Persist selection (optional)** – storing the backend URL and workflow ID in
   `sessionStorage` lets users refresh without re-entering data.

## Sample snippet
```html
<openai-chatkit></openai-chatkit>
<script>
  const chatkit = document.querySelector("openai-chatkit");
  function configureChat(options) {
    const assign = () => chatkit.setOptions(options);
    if (customElements.get("openai-chatkit")) {
      assign();
    } else {
      customElements.whenDefined("openai-chatkit").then(assign);
    }
  }

  const workflowId = "wf_123";
  const workflowName = "Support Assistant";
  const backendBase = "https://api.example";

  configureChat({
    api: {
      url: `${backendBase}/api/chatkit`,
      domainKey: window.ORCHEO_CHATKIT_DOMAIN_KEY,
      fetch: fetchWithWorkflow({ workflowId, workflowName, backendBase }),
    },
    header: { enabled: true, title: { text: workflowName } },
    history: { enabled: true },
    composer: { placeholder: `Ask ${workflowName} a question…` },
  });
</script>
```

## Troubleshooting checklist
- **403 or 404 responses** – confirm the workflow is still published and that the
  workflow ID matches the final segment of the share URL.
- **401 responses** – required when `--require-login` is set. Make sure the page
  is served from the same origin as Canvas so OAuth cookies are available.
- **CORS failures** – `/api/chatkit` must allow the host running your HTML page.
  Set `ORCHEO_CORS_ALLOW_ORIGINS` (see `docs/environment_variables.md`) to a JSON
  list of allowed origins such as
  ``export ORCHEO_CORS_ALLOW_ORIGINS='["http://localhost:8080","http://127.0.0.1:5173"]'``.
  Include every scheme/host/port that will load the embedded page.
- **Domain key errors** – supply a valid `ORCHEO_CHATKIT_DOMAIN_KEY` value. Use
  different keys per environment when possible.
- **Bubble never opens** – check the console for errors and verify the page
  called `chatkit.setOptions` after the custom element loaded.

## References
- Working demo: `examples/chatkit-orcheo.html`
- Backend contract: `apps/backend/src/orcheo_backend/app/routers/chatkit.py`
- Canvas embedding code: `apps/canvas/src/features/chatkit/components/public-chat-widget.tsx`
