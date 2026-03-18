import streamlit as st
from groq import Groq
from gtts import gTTS
import tempfile
import os

# ================= CONFIGURATION =================
st.set_page_config(page_title="Elite Spanish BPO Coach", page_icon="💼", layout="wide")

# Styling
st.markdown("""
    <style>
    .stChatMessage { border-radius: 12px; margin-bottom: 15px; border: 1px solid #f0f2f6; }
    .coach-box { 
        background-color: #f0f7ff; padding: 15px; border-radius: 8px; 
        border-left: 5px solid #007bff; margin-top: 10px; color: #1e3a8a;
    }
    </style>
""", unsafe_allow_html=True)

# API Setup
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("⚠️ Please set GROQ_API_KEY in Streamlit Secrets.")
    st.stop()

# ================= SESSION STATE =================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "level" not in st.session_state:
    st.session_state.level = "B1"
if "track" not in st.session_state:
    st.session_state.track = "General Support"
# THIS IS THE LOOP KILLER:
if "widget_key" not in st.session_state:
    st.session_state.widget_key = 0

# ================= LOGIC =================

def get_bpo_system_prompt():
    track = st.session_state.track
    level = st.session_state.level
    
    prompts = {
        "General Support": "You are a customer calling a BPO center about a billing error. You are frustrated but professional.",
        "Medical VA": "You are a patient calling to schedule a follow-up surgery. You are in slight pain.",
        "Real Estate VA": "You are a wealthy investor asking for ROI details on a luxury apartment.",
        "Tech Support": "You are an elderly user whose computer won't turn on. You are very confused.",
        "Executive VA": "You are a CEO. The user is your assistant. You are in a rush to book a flight."
    }
    
    return (
        f"SCENARIO: {prompts[track]} PROFICIENCY: {level}. "
        "INSTRUCTIONS: \n"
        "1. Speak ONLY Spanish in the dialogue. Stay in character.\n"
        "2. Provide feedback AFTER the separator '---'.\n"
        "3. Focus on the CURRENT interaction. Do not repeat instructions indefinitely.\n"
        "FORMAT:\n"
        "[Spanish Dialogue]\n"
        "---\n"
        "**COACH FEEDBACK**\n"
        "- Grammar Fix: [One sentence correction]\n"
        "- Professional Word: [Better Spanish word for BPO context]\n"
        "- Tone Score: [1-10]"
    )

def generate_tts(text):
    try:
        spanish_text = text.split("---")[0].strip()
        tts = gTTS(text=spanish_text, lang='es')
        fp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(fp.name)
        return fp.name
    except: return None

# ================= SIDEBAR =================
with st.sidebar:
    st.title("💼 Career Coach")
    st.session_state.level = st.select_slider("Level", ["A1", "A2", "B1", "B2", "C1", "C2"], value=st.session_state.level)
    st.session_state.track = st.selectbox("Track", ["General Support", "Medical VA", "Real Estate VA", "Tech Support", "Executive VA"])
    if st.button("🗑️ Reset All"):
        st.session_state.messages = []
        st.session_state.widget_key += 1
        st.rerun()

# ================= MAIN UI =================
st.title("🇪🇸 Elite Spanish Professional Coach")

# Display Messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "---" in msg["content"]:
            parts = msg["content"].split("---")
            st.markdown(parts[0])
            st.markdown(f"<div class='coach-box'>{parts[1]}</div>", unsafe_allow_html=True)
        else:
            st.markdown(msg["content"])
        if "audio" in msg: st.audio(msg["audio"])

# ================= INPUT PROCESSING =================

# TEXT INPUT
user_query = st.chat_input("Type your response in Spanish...")

# AUDIO INPUT (Uses a dynamic key to prevent infinite loops)
audio_data = st.audio_input("Record your voice", key=f"audio_input_{st.session_state.widget_key}")

final_input = None

# If audio is recorded, transcribe it immediately
if audio_data:
    with st.spinner("Transcribing..."):
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
            st.error(f"Mic Error: {e}")

# If text is typed, use it
if user_query:
    final_input = user_query

# MAIN PROCESSING ENGINE
if final_input:
    # 1. Add User Message
    st.session_state.messages.append({"role": "user", "content": final_input})
    
    # 2. Get AI Response
    with st.chat_message("assistant"):
        with st.spinner("AI is evaluating..."):
            # Sanitize history (Only role and content)
            clean_history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-6:]]
            
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": get_bpo_system_prompt()}] + clean_history,
                temperature=0.7
            )
            ai_text = response.choices[0].message.content
            audio_path = generate_tts(ai_text)
            
            # Save to state
            st.session_state.messages.append({"role": "assistant", "content": ai_text, "audio": audio_path})
            
    # 3. KILL THE LOOP: Increment the widget key to reset the recorder
    st.session_state.widget_key += 1
    st.rerun()
