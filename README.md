# Emotion TTS - Render-ready

This repo is a ready-to-deploy project for Render.com (FastAPI + Gradio) that exposes:

- `GET /` → static landing page (static/index.html)
- `GET /sw.js` → service worker required by the ad network
- `GET /app` → Gradio UI (voice generator)
- `POST /generate` → JSON API endpoint for TTS (n8n friendly)

## Deploy on Render
1. Create a GitHub repo and push these files with the same folder structure.
2. Log into Render, create a new **Web Service**, and connect your GitHub repo.
3. Set the build command to: pip install -r requirements.txt
4. Set the start command to: python server.py
5. Deploy. The first deploy may take time if the TTS model needs to download.

## Notes
- If the Coqui `TTS` model is too heavy for the free instance, enable an ElevenLabs fallback. You can modify `synthesize_audio` to call ElevenLabs REST API when local TTS is unavailable.
- `sw.js` is served from `/sw.js` because `static/` is mounted at the site root.

---

*End of project files.*
