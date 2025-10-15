import os
import io
import json
import threading
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn
import gradio as gr

# Optional: try to import Coqui TTS. If unavailable, the app will return a friendly error.
try:
    from TTS.api import TTS
    TTS_AVAILABLE = True
except Exception:
    TTS_AVAILABLE = False

# -----------------------------
# App and static mounting
# -----------------------------

app = FastAPI(title="Emotion TTS - Render Ready")

# Serve static files at site root. This ensures /sw.js is available at https://yourdomain/sw.js
app.mount("/", StaticFiles(directory="static", html=True), name="static")

# -----------------------------
# Load TTS model (if available)
# -----------------------------

tts = None
if TTS_AVAILABLE:
    try:
        # Pick a small model if you want faster CPU usage. Replace with preferred model id.
        model_name = "tts_models/en/ljspeech/tacotron2-DCA"  # relatively small example
        tts = TTS(model_name, progress_bar=False, gpu=False)
    except Exception as e:
        print("TTS model failed to load:", e)
        tts = None

# -----------------------------
# Utility functions
# -----------------------------

def normalize_emotions(em: dict, max_total: float = 1.4) -> dict:
    vals = {k: float(v) for k, v in em.items()}
    total = sum(abs(v) for v in vals.values())
    if total == 0 or total <= max_total:
        return vals
    scale = max_total / total
    return {k: v * scale for k, v in vals.items()}


def map_params_from_age_emotions(age: int, emotions: dict):
    age = max(5, int(age))
    if age <= 12:
        pitch = 1.15 + (12 - age) * 0.01
    else:
        pitch = 1.0 - min(max((age - 25) / 200, 0), 0.2)
    rate = 1.0 + (emotions.get("happy", 0) - emotions.get("sad", 0)) * 0.1
    rate = max(0.7, min(1.4, rate))
    energy = emotions.get("angry", 0) * 0.5 + emotions.get("happy", 0) * 0.3 + emotions.get("surprise", 0) * 0.25
    return {"pitch_scale": float(pitch), "rate": float(rate), "energy": float(energy)}


def synthesize_audio(text: str, speaker: str, age: int, emotions: dict) -> bytes:
    """Generate audio bytes. If TTS not available, raise a clear error."""
    if tts is None:
        raise RuntimeError("TTS model not available on this host. Use ElevenLabs fallback or deploy on a host with the model.")

    params = map_params_from_age_emotions(age, emotions)
    # The TTS API and models differ in supported args. Here we use tts.tts_to_file as a robust fallback.
    out_path = "output.wav"
    # Some TTS wrappers accept speed/pitch args; if unsupported, they will be ignored.
    tts.tts_to_file(text=text, speaker=speaker if speaker else None, file_path=out_path, speed=params.get("rate", 1.0))
    with open(out_path, "rb") as f:
        return f.read()

# -----------------------------
# FastAPI endpoint for direct HTTP use (n8n)
# -----------------------------

from pydantic import BaseModel

class EmotionDict(BaseModel):
    happy: float = 0.0
    angry: float = 0.0
    sad: float = 0.0
    fear: float = 0.0
    hate: float = 0.0
    low: float = 0.0
    surprise: float = 0.0
    neutral: float = 0.0

class TTSRequest(BaseModel):
    text: str
    gender: str = "female"
    age: int = 25
    emotions: EmotionDict = EmotionDict()
    speaker: str = None

@app.post("/generate")
async def generate(req: TTSRequest):
    payload = req.dict()
    text = payload["text"]
    gender = payload["gender"]
    age = payload["age"]
    emotions = normalize_emotions(payload["emotions"].dict())
    speaker = payload.get("speaker")

    try:
        audio_bytes = synthesize_audio(text, speaker or gender, age, emotions)
        return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/wav")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=503)

# -----------------------------
# Gradio UI app (modern, responsive, professional)
# -----------------------------

EMOTIONS = ["happy", "angry", "sad", "fear", "hate", "low", "surprise", "neutral"]

# The UI will keep the iframe unloaded until the user clicks "Read more".
# When clicked, the server returns HTML to be inserted into the page, which includes the iframe.

def server_generate(text, gender, age, *emotion_vals):
    try:
        em = {k: float(v) for k, v in zip(EMOTIONS, emotion_vals)}
    except Exception:
        em = {k: 0.0 for k in EMOTIONS}
    em = normalize_emotions(em)
    # synthesize audio and return path for Gradio audio component
    try:
        audio_bytes = synthesize_audio(text, gender, age, em)
        # Write to a file Gradio can serve
        path = "generated.wav"
        with open(path, "wb") as f:
            f.write(audio_bytes)
        return (path, json.dumps(em))
    except Exception as e:
        return (None, f"Error: {e}")

# When the user clicks Read More, this function returns HTML that contains the iframe.
# The iframe source is the link you provided: https://otieu.com/4/9924373

def load_ad_iframe():
    iframe_html = f"""
    <div style='width:100%;display:flex;justify-content:center;margin-top:10px;'>
      <iframe src="https://otieu.com/4/9924373"
              style="width:100%;max-width:800px;height:420px;border:0;box-shadow:0 6px 24px rgba(0,0,0,0.12);border-radius:8px;"
              scrolling="no" loading="lazy"></iframe>
    </div>
    """
    # Also return a flag that tells the frontend the ad was opened (so the "Complete" button can activate)
    return iframe_html

# Build Gradio layout
with gr.Blocks(css="""
/* small custom CSS for a professional look */
body {font-family: Inter, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial;}
.gradio-container {max-width:1200px;margin-left:auto;margin-right:auto}
.header-row{display:flex;justify-content:space-between;align-items:center}
.card{background:linear-gradient(180deg, rgba(255,255,255,0.98), rgba(250,250,250,0.98));padding:18px;border-radius:14px;box-shadow:0 8px 30px rgba(13,38,76,0.06);}
""") as demo:
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("# 🎧 Emotion Voice — Professional Generator")
            gr.Markdown("Create natural-sounding voices with age & emotion controls. Works on phones, tablets and desktops.")
        with gr.Column(scale=1, min_width=200):
            gr.Markdown("**Need help?** Contact: support@example.com")

    with gr.Row():
        with gr.Column(scale=2):
            with gr.Card():
                text_input = gr.Textbox(label="Enter text", placeholder="Type the text to synthesize here...", lines=4)
                gender = gr.Radio(["female", "male"], value="female", label="Voice Gender")
                age = gr.Slider(5, 80, value=25, step=1, label="Age")

                with gr.Accordion("Advanced emotions (drag to set 0.0–1.4)", open=False):
                    emotion_sliders = []
                    for e in EMOTIONS:
                        emotion_sliders.append(gr.Slider(0.0, 1.4, value=0.0, step=0.05, label=e.capitalize()))

                gen_btn = gr.Button("Generate Voice", variant="primary")
                audio_out = gr.Audio(label="Generated Voice", type="filepath")
                emotion_out = gr.Textbox(label="Emotion weights (debug)", interactive=False)

                gen_btn.click(fn=server_generate, inputs=[text_input, gender, age] + emotion_sliders, outputs=[audio_out, emotion_out])

        with gr.Column(scale=1):
            with gr.Card():
                gr.Markdown("### About this demo")
                gr.Markdown("This demo keeps promotional content separate from the main experience for best UX. Click the button below to \"Read more\" — the ad iframe will load only after you click it.")

                # Placeholder HTML; iframe only loads when user clicks the button
                ad_placeholder = gr.HTML("<div id='ad-placeholder' style='text-align:center;padding:10px;color:#666'>Ad content will appear here when you click \"Read more\".</div>")
                read_more_btn = gr.Button("Read more")
                # The "Complete" button is disabled until the ad iframe is opened.
                complete_btn = gr.Button("Complete — get full download", variant="secondary", interactive=False)

                # When Read more clicked: load iframe html into ad_placeholder and enable Complete button
                def on_read_more_click():
                    html = load_ad_iframe()
                    return html, gr.update(interactive=True)

                read_more_btn.click(fn=on_read_more_click, inputs=None, outputs=[ad_placeholder, complete_btn])

                # The Complete button can show a short thank-you or redirect to a completion page
                def on_complete_click():
                    return "Thank you — process completed. You may download the generated file from the audio player above."

                complete_btn.click(fn=on_complete_click, inputs=None, outputs=[gr.Textbox(label="Status")])

    # Footer
    with gr.Row():
        gr.Markdown("---\n*Built with care — responsive on phones, tablets, and desktops.*")

# Mount Gradio app at /app while FastAPI serves / and /sw.js from static folder
app = gr.mount_gradio_app(app, demo, path="/app")

# -----------------------------
# Entrypoint
# -----------------------------
if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port)
