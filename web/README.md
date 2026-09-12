# Web front-end

| Path | Purpose |
|------|---------|
| `kivi-ui/` | React source (Vite + TypeScript) |
| `dist/` | Build output — served at `/` (run `npm run build` in `kivi-ui/`) |
| `assets/` | Static JSON for the UI (`query_cases.json`, `demo_chats.json`) and `DEMO_CHATS.md` |

```bash
cd kivi-ui && npm install && npm run build
```

FastAPI mounts `web/` at `/static/`; the app shell loads from `/static/dist/`.
