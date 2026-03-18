import streamlit as st
from groq import Groq
from gtts import gTTS
import tempfile
import os
import json

# ================= CONFIGURATION & STYLING =================
st.set_page_config(page_title="Elite Spanish BPO Coach", page_icon="💼", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stChatMessage { border-radius: 15px; border: 1px solid #e0e0e0; margin-bottom: 10px; }
    .coach-feedback { background-color: #e1f5fe; padding: 15px; border-left: 5px solid #0288d1; border-radius: 5px; }
    .bpo-stat { font-size: 0.9rem; color: #666; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# ================= INITIALIZATION =================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_track" not in st.session_state:
    st.session_state.current_track = "General Conversation"
if "level" not in st.session_state:
    st.session_state.level = "B1"

# API Setup
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("Missing GROQ_API_KEY in secrets.")
    st.stop()

# ================= AI ENGINE (With Memory) =================
def get_ai_response(user_input, track, level):
    # Professional System Prompts based on Track
    prompts = {
        "General Conversation": f"You are a professional Spanish tutor. Level: {level}. Focus on natural flow and CEFR standards.",
        "BPO: Customer Support": f"You are an angry or confused customer calling a BPO center. The user is the agent. Level: {level}. Use industry-specific terms (billing, troubleshooting).",
        "VA: Executive Assistant": f"You are a busy US-based CEO. The user is your Spanish-speaking Virtual Assistant. Task: Manage my calendar and emails professionally in Spanish.",
        "BPO: Real Estate": f"You are a property buyer/seller. The user is a Real Estate VA. Discuss listings, escrow, and viewings in Spanish.",
        "Technical Support": f"You are a non-technical person with a major internet outage. The user must guide you through steps in Spanish."
    }

    system_message = {
        "role": "system",
        "content": f"{prompts[track]} \n\n"
                   f"CRITICAL INSTRUCTIONS:\n"
                   f"1. Stay in character during the dialogue.\n"
                   f"2. At the end of every response, provide a 'COACH'S CORNER' section in English.\n"
                   f"3. In Coach's Corner: List 3 corrections, 1 professional vocabulary word used, and a Tone Rating (1-10).\n"
                   f"4. Format: [Character Dialogue] \n---\n[Coach's Corner]"
    }

    # Build memory context (Last 6 messages)
    history = [system_message] + st.session_state.messages[-6:]
    history.append({"role": "user", "content": user_input})

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=history,
            temperature=0.7,
            max_tokens=1000
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error connecting to AI: {e}"

# ================= HELPER FUNCTIONS =================
def text_to_speech(text):
    # Strip the Coach's Corner from audio
    clean_text = text.split("---")[0].replace("*", "")
    try:
        tts = gTTS(text=clean_text, lang='es', slow=False)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            tts.save(fp.name)
            return fp.name
    except:
        return None

# ================= SIDEBAR: COACHING CONTROLS =================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3898/3898834.png", width=100)
    st.title("Spanish Professional")
    
    st.session_state.level = st.select_slider(
        "Current Proficiency Level",
        options=["A1", "A2", "B1", "B2", "C1", "C2"],
        value=st.session_state.level
    )
    
    st.divider()
    
    st.subheader("Career Tracks")
    track_options = [
        "General Conversation", 
        "BPO: Customer Support", 
        "VA: Executive Assistant", 
        "BPO: Real Estate", 
        "Technical Support"
    ]
    st.session_state.current_track = st.selectbox("Select Training Module", track_options)
    
    st.info(f"**Current Goal:** Training for {st.session_state.current_track} at {st.session_state.level} level.")
    
    if st.button("🔄 Reset Session", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ================= MAIN INTERFACE =================
st.title(f"🚀 {st.session_state.current_track} Coach")

# Display History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "---" in msg["content"]:
            parts = msg["content"].split("---")
            st.markdown(parts[0])
            with st.container():
                st.markdown(f"<div class='coach-feedback'><b>👨‍🏫 Coach's Corner:</b><br>{parts[1]}</div>", unsafe_allow_html=True)
        else:
            st.markdown(msg["content"])
        
        if "audio" in msg:
            st.audio(msg["audio"])

# Input Logic
user_input = st.chat_input("Speak or type your Spanish response...")
audio_input = st.audio_input("Record your voice")

if audio_input:
    with st.status("Transcribing audio...", expanded=False):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_input.getvalue())
            with open(tmp.name, "rb") as f:
                transcription = client.audio.transcriptions.create(
                    file=(tmp.name, f), 
                    model="whisper-large-v3", 
                    language="es"
                )
                user_input = transcription.text

if user_input:
    # Append User Message
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Get AI Response
    with st.spinner("AI Coach is thinking..."):
        full_response = get_ai_response(user_input, st.session_state.current_track, st.session_state.level)
        audio_path = text_to_speech(full_response)
        
        st.session_state.messages.append({
            "role": "assistant", 
            "content": full_response,
            "audio": audio_path
        })
    
    st.rerun()
