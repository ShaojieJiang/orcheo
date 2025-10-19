# Orcheo Canvas

Front‑end workspace for the Orcheo workflow canvas prototype. The app is built with Vite, React 19, TypeScript, Tailwind, and shadcn/ui components.

## Getting Started

```bash
uv run npm install         # install orcheo-canvas dependencies
uv run npm run dev         # start Vite on http://localhost:5173
uv run npm run build       # create a production build
uv run npm run lint        # lint with eslint
```

## Project Layout

- `src/main.tsx` / `src/App.tsx` — App bootstrap and router.
- `src/features/orcheo-canvas/` — Feature modules (auth, workflow canvas, account, support, shared).
- `src/design-system/` — Wrapped shadcn/ui primitives that back the UI.
- `src/hooks/`, `src/lib/` — Reusable hooks and utilities.

## Testing

The project is configured with Vitest and Testing Library. Run the suite with:

```bash
uv run npm test
```

## Notes

- The repo excludes `node_modules`; install dependencies before running scripts.
- Tailwind configuration lives in `tailwind.config.js` with PostCSS settings in `postcss.config.js`.
