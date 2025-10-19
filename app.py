from flask import Flask, render_template, request, jsonify, send_file
from TTS.api import TTS
import torch
import os
import io
import tempfile
import json
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class TTSEngine:
    def __init__(self):
        self.models = {}
        self.available_models = {}
        self.load_available_models()
        
    def load_available_models(self):
        """Load available TTS models with metadata"""
        self.available_models = {
            "male": {
                "young": ["tts_models/en/ljspeech/tacotron2-DDC", "tts_models/en/ljspeech/glow-tts"],
                "adult": ["tts_models/en/ljspeech/tacotron2-DDC", "tts_models/en/ljspeech/speedy-speech"],
                "senior": ["tts_models/en/ljspeech/tacotron2-DDC"]
            },
            "female": {
                "young": ["tts_models/en/ljspeech/glow-tts", "tts_models/en/ljspeech/tacotron2-DDC"],
                "adult": ["tts_models/en/ljspeech/vits", "tts_models/en/ljspeech/tacotron2-DDC"],
                "senior": ["tts_models/en/ljspeech/tacotron2-DDC"]
            },
            "neutral": {
                "all": ["tts_models/en/ljspeech/tacotron2-DDC", "tts_models/en/ljspeech/glow-tts"]
            }
        }
        
    def get_age_group(self, age: int) -> str:
        """Convert age to age group"""
        if age <= 15:
            return "young"
        elif age <= 40:
            return "adult"
        else:
            return "senior"
    
    def get_model_for_voice(self, gender: str, age: int, voice_type: str) -> str:
        """Select appropriate model based on parameters"""
        age_group = self.get_age_group(age)
        
        if gender in self.available_models:
            if age_group in self.available_models[gender]:
                models = self.available_models[gender][age_group]
                # Simple selection based on voice_type hash
                import hashlib
                hash_val = int(hashlib.md5(voice_type.encode()).hexdigest(), 16)
                model_index = hash_val % len(models)
                return models[model_index]
        
        # Fallback to default model
        return "tts_models/en/ljspeech/tacotron2-DDC"
    
    def synthesize_speech(self, text: str, gender: str, age: int, tone: str, 
                         intensity: float, voice_type: str, accent: str) -> bytes:
        """Synthesize speech with given parameters"""
        try:
            model_name = self.get_model_for_voice(gender, age, voice_type)
            
            # Initialize TTS with the selected model
            if model_name not in self.models:
                logger.info(f"Loading model: {model_name}")
                self.models[model_name] = TTS(model_name=model_name, progress_bar=False)
            
            tts = self.models[model_name]
            
            # Apply tone and intensity adjustments
            speed = self.calculate_speed(tone, intensity)
            pitch = self.calculate_pitch(gender, age, tone, intensity)
            
            # Generate speech
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_path = temp_file.name
            
            tts.tts_to_file(
                text=text,
                file_path=temp_path,
                speed=speed,
                # Note: Coqui TTS has limited pitch control in some models
            )
            
            # Read the generated audio
            with open(temp_path, 'rb') as f:
                audio_data = f.read()
            
            # Clean up
            os.unlink(temp_path)
            
            return audio_data
            
        except Exception as e:
            logger.error(f"Error in speech synthesis: {str(e)}")
            raise
    
    def calculate_speed(self, tone: str, intensity: float) -> float:
        """Calculate speech speed based on tone and intensity"""
        base_speeds = {
            "normal": 1.0,
            "angry": 1.2,
            "happy": 1.3,
            "sad": 0.7,
            "surprised": 1.4,
            "fear": 1.1,
            "playful": 1.25
        }
        base_speed = base_speeds.get(tone, 1.0)
        return base_speed * (0.8 + intensity * 0.4)
    
    def calculate_pitch(self, gender: str, age: int, tone: str, intensity: float) -> float:
        """Calculate pitch adjustments"""
        # Base pitch by gender and age
        if gender == "male":
            base_pitch = 0.8 - (age / 200)  # Lower pitch for older males
        elif gender == "female":
            base_pitch = 1.0 - (age / 250)  # Slightly lower for older females
        else:
            base_pitch = 0.9 - (age / 225)
        
        # Tone adjustments
        tone_adjustments = {
            "angry": 0.1,
            "happy": 0.15,
            "sad": -0.1,
            "surprised": 0.2,
            "fear": 0.05,
            "playful": 0.1,
            "normal": 0.0
        }
        
        adjustment = tone_adjustments.get(tone, 0.0) * intensity
        return max(0.5, min(1.5, base_pitch + adjustment))

# Initialize TTS engine
tts_engine = TTSEngine()

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/voices')
def get_voice_options():
    """Get available voice options"""
    voices = {
        "male": [
            "Deep Voice", "Smooth Baritone", "Raspy Voice", "Warm Voice",
            "Authoritative", "Friendly", "Narrator", "Casual"
        ],
        "female": [
            "Soft Voice", "Bright Voice", "Warm Alto", "Clear Voice",
            "Professional", "Friendly", "Expressive", "Calm"
        ],
        "neutral": [
            "Balanced Voice", "Clear Speaker", "Standard Voice", "Versatile"
        ]
    }
    
    accents = [
        "US English", "UK English", "Australian", "Indian English",
        "Nigerian English", "Canadian", "Irish", "Scottish",
        "South African", "New Zealand"
    ]
    
    tones = ["normal", "angry", "happy", "sad", "surprised", "fear", "playful"]
    
    return jsonify({
        "voices": voices,
        "accents": accents,
        "tones": tones
    })

@app.route('/api/synthesize', methods=['POST'])
def synthesize_speech():
    """Synthesize speech from text"""
    try:
        data = request.get_json()
        
        required_fields = ['text', 'gender', 'age', 'tone', 'intensity', 'voiceType', 'accent']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Validate parameters
        if not data['text'].strip():
            return jsonify({"error": "Text cannot be empty"}), 400
        
        if len(data['text']) > 5000:
            return jsonify({"error": "Text too long. Maximum 5000 characters."}), 400
        
        age = int(data['age'])
        if age < 5 or age > 60:
            return jsonify({"error": "Age must be between 5 and 60"}), 400
        
        intensity = float(data['intensity'])
        if intensity < 0.0 or intensity > 1.4:
            return jsonify({"error": "Intensity must be between 0.0 and 1.4"}), 400
        
        # Generate speech
        audio_data = tts_engine.synthesize_speech(
            text=data['text'],
            gender=data['gender'],
            age=age,
            tone=data['tone'],
            intensity=intensity,
            voice_type=data['voiceType'],
            accent=data['accent']
        )
        
        return send_file(
            io.BytesIO(audio_data),
            mimetype='audio/wav',
            as_attachment=True,
            download_name='speech.wav'
        )
        
    except Exception as e:
        logger.error(f"Synthesis error: {str(e)}")
        return jsonify({"error": f"Speech synthesis failed: {str(e)}"}), 500

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "models_loaded": len(tts_engine.models)})

if __name__ == '__main__':
    # For production deployment
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    app.run(host='0.0.0.0', port=port, debug=debug)
