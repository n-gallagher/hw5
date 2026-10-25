import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The dashboard runs on http://localhost:5173 and calls the FastAPI backend on
// http://localhost:8000 (set in .env as VITE_API_URL; the backend allows this origin via CORS).
export default defineConfig({
  plugins: [react()],
  // PORT lets a launcher pick another port when 5173 is taken; npm run dev uses 5173.
  server: { port: Number(process.env.PORT) || 5173, host: "localhost" },
});
