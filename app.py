import streamlit as st
from groq import Groq
from gtts import gTTS
import tempfile
import os

# ================= CONFIGURATION & UI SETUP =================
st.set_page_config(page_title="Elite Spanish Coach", page_icon="💼", layout="wide")

st.markdown("""
    <style>
    .stChatMessage { border-radius: 12px; margin-bottom: 15px; border: 1px solid #f0f2f6; }
    .coach-box { 
        background-color: #f0f7ff; 
        padding: 15px; border-radius: 8px; border-left: 5px solid #007bff;
        margin-top: 10px; font-size: 0.95rem; color: #1e3a8a;
    }
    </style>
""", unsafe_allow_html=True)

# API Initialization
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception:
    st.error("⚠️ API Key missing in Secrets.")
    st.stop()

# ================= SESSION STATE =================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "level" not in st.session_state:
    st.session_state.level = "B1"
if "track" not in st.session_state:
    st.session_state.track = "General Support"

# ================= AI LOGIC =================

def get_bpo_system_prompt(track, level):
    prompts = {
        "General Support": "You are a customer calling a BPO center about a billing error.",
        "Medical VA": "You are a patient calling your doctor's office.",
        "Real Estate VA": "You are an investor asking about property ROI.",
        "Tech Support": "You are an elderly person whose WiFi is broken.",
        "Executive VA": "You are a CEO. The user is your assistant."
    }
    return (
        f"ROLE: {prompts[track]}. LEVEL: {level}. "
        "DIRECTIONS: 1. Speak ONLY Spanish in the dialogue. 2. After '---', provide Coaching in English. "
        "3. DO NOT repeat the user's past mistakes in your current Spanish dialogue. Focus on the NEW response. "
        "FORMAT: [Spanish Dialogue] \n---\n **Coach Feedback** \n- Grammar Fix: \n- Professionalism Tip:"
    )

def generate_tts(text):
    try:
        spanish_part = text.split("---")[0].strip()
        tts = gTTS(text=spanish_part, lang='es')
        fp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(fp.name)
        return fp.name
    except: return None

def process_ai_chat(user_input):
    # SANITIZE HISTORY: Only send role and content to Groq (Fixes the 400 error)
    sanitized_history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-6:]]
    
    system_msg = {"role": "system", "content": get_bpo_system_prompt(st.session_state.track, st.session_state.level)}
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[system_msg] + sanitized_history + [{"role": "user", "content": user_input}],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

# ================= SIDEBAR =================
with st.sidebar:
    st.title("💼 Coach Settings")
    st.session_state.level = st.select_slider("Proficiency", ["A1", "A2", "B1", "B2", "C1", "C2"], value=st.session_state.level)
    st.session_state.track = st.selectbox("Career Track", ["General Support", "Medical VA", "Real Estate VA", "Tech Support", "Executive VA"])
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# ================= MAIN CHAT UI =================
st.title("🇪🇸 Spanish Professional Coach")

# Display History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "---" in msg["content"]:
            parts = msg["content"].split("---")
            st.markdown(parts[0])
            st.markdown(f"<div class='coach-box'>{parts[1]}</div>", unsafe_allow_html=True)
        else:
            st.markdown(msg["content"])
        if "audio" in msg: st.audio(msg["audio"])

# ================= INPUT HANDLING (THE LOOP FIX) =================

# 1. Gather Inputs
user_query = st.chat_input("Type here...")
audio_data = st.audio_input("Record your voice")

final_input = None

# 2. Process Audio (If present and hasn't been processed yet)
if audio_data:
    # Use the unique ID of the audio buffer to prevent re-processing
    audio_id = audio_data.name if hasattr(audio_data, 'name') else "audio_file"
    
    with st.status("Transcribing...", expanded=False):
        try:
            transcription = client.audio.transcriptions.create(
                file=("speech.wav", audio_data.getvalue()),
                model="whisper-large-v3",
                language="es",
                response_format="text"
            )
            if transcription.strip():
                final_input = transcription
        except Exception as e:
            st.error(f"Transcription Error: {e}")

# 3. Process Text
if user_query:
    final_input = user_query

# 4. Final Processing Engine
if final_input:
    # Save user message
    st.session_state.messages.append({"role": "user", "content": final_input})
    
    with st.chat_message("assistant"):
        with st.spinner("AI Coach is evaluating..."):
            response_text = process_ai_chat(final_input)
            audio_path = generate_tts(response_text)
            
            # Save assistant message
            st.session_state.messages.append({
                "role": "assistant", 
                "content": response_text, 
                "audio": audio_path
            })
    
    # CRITICAL: Clear audio_data state to stop the loop
    st.rerun()
