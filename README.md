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
- ---

## Final notes
- The ad iframe is intentionally **lazy-loaded** (only inserted into the page when the user clicks "Read more" inside the Gradio UI), so it won't interfere with the main user experience.
- The "Complete" action is gated so the user must open the ad iframe once to activate it — implemented client-side inside the Gradio app.

If you'd like, I can also:
- Add an ElevenLabs fallback implementation in `server.py` (requires you to set `ELEVEN_API_KEY` as an environment variable on Render).
- Produce a ZIP of this repo (or push to a GitHub repo for you if you give a repo name).


---

*End of project files.*
