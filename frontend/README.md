# The Lethe Desk (Campus Customs dashboard)

React + Vite + TypeScript. Start the backend first (`cd backend && uvicorn main:app --reload --port 8000`), then:

```bash
npm install
npm run dev
```

Open http://localhost:5173. It calls the API at `http://localhost:8000`; set `VITE_API_URL` to change it.

- `src/App.tsx`: the layout and live polling
- `src/derive.ts`: turns audit events into agent states, feed lines and the summary
- `src/houses.tsx`: the five agents' colors and sigils
- `src/api.ts`: typed calls to the backend routes
- `src/index.css`: the look

The design is explained in `../output/design.md`.
