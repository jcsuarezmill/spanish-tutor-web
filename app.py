import streamlit as st
from groq import Groq
from gtts import gTTS
import tempfile
import os
import io

# ================= CONFIGURATION & UI SETUP =================
st.set_page_config(page_title="Elite Spanish BPO Coach", page_icon="💼", layout="wide")

# Professional CSS
st.markdown("""
    <style>
    .stChatMessage { border-radius: 12px; margin-bottom: 15px; border: 1px solid #f0f2f6; }
    .coach-box { 
        background-color: #f0f7ff; 
        padding: 15px; 
        border-radius: 8px; 
        border-left: 5px solid #007bff;
        margin-top: 10px;
        font-size: 0.95rem;
    }
    .bpo-label { color: #555; font-weight: bold; text-transform: uppercase; font-size: 0.7rem; }
    </style>
""", unsafe_allow_html=True)

# API Initialization
try:
    # Works for Streamlit Cloud (Secrets) and Local (.streamlit/secrets.toml)
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    client = Groq(api_key=GROQ_API_KEY)
except Exception:
    st.error("⚠️ GROQ_API_KEY not found. Please set it in Streamlit Secrets.")
    st.stop()

# ================= SESSION STATE MANAGEMENT =================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "level" not in st.session_state:
    st.session_state.level = "B1"
if "track" not in st.session_state:
    st.session_state.track = "General Support"

# ================= CORE LOGIC FUNCTIONS =================

def get_bpo_system_prompt(track, level):
    """Generates a high-precision system prompt for the AI."""
    prompts = {
        "General Support": "You are a customer calling a BPO center about a billing error.",
        "Medical VA": "You are a patient calling your doctor's office to schedule an urgent surgery follow-up.",
        "Real Estate VA": "You are an investor interested in buying 3 multi-family properties. Ask about ROI and escrow.",
        "Tech Support": "You are an elderly person whose WiFi is out. You are frustrated and don't know technology.",
        "Executive VA": "You are a CEO. The user is your Assistant. You need to reschedule 5 meetings and book a flight to Madrid."
    }
    
    return (
        f"ROLE: {prompts[track]} "
        f"PROFICIENCY LEVEL: {level}. "
        "INSTRUCTIONS:\n"
        "1. Start the conversation in Spanish.\n"
        "2. Be realistic. If the track is 'Tech Support', act confused. If 'General Support', act frustrated.\n"
        "3. Every response MUST follow this structure:\n"
        "[Spanish Dialogue]\n"
        "---\n"
        "**COACH FEEDBACK (English)**\n"
        "- **Grammar Fix:** [Point out one specific error the user made]\n"
        "- **BPO Vocabulary:** [Suggest a more professional Spanish word]\n"
        "- **Tone Rating:** [Score 1-10]"
    )

def generate_tts(text):
    """Converts the Spanish part of the AI response to audio."""
    try:
        # Only speak the part BEFORE the '---' (the Spanish dialogue)
        spanish_part = text.split("---")[0].strip()
        tts = gTTS(text=spanish_part, lang='es')
        fp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(fp.name)
        return fp.name
    except Exception:
        return None

def process_ai_chat(user_input):
    """Handles the Groq API call with sanitized history."""
    
    # 1. Clean History (The fix for 'property audio is unsupported')
    # We only send 'role' and 'content' to the API.
    sanitized_history = [
        {"role": m["role"], "content": m["content"]} 
        for m in st.session_state.messages[-10:] # Sliding window of 10 messages
    ]
    
    # 2. Add System Context
    system_msg = {"role": "system", "content": get_bpo_system_prompt(st.session_state.track, st.session_state.level)}
    
    # 3. Call Groq
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[system_msg] + sanitized_history + [{"role": "user", "content": user_input}],
            temperature=0.7,
            max_tokens=800
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ API Error: {str(e)}"

# ================= SIDEBAR UI =================
with st.sidebar:
    st.title("Settings")
    st.session_state.level = st.select_slider(
        "Proficiency Level", 
        options=["A1", "A2", "B1", "B2", "C1", "C2"], 
        value=st.session_state.level
    )
    
    st.session_state.track = st.selectbox(
        "Training Track",
        ["General Support", "Medical VA", "Real Estate VA", "Tech Support", "Executive VA"]
    )
    
    st.divider()
    if st.button("🗑️ Clear Conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    st.info(f"**Current Goal:** Practice {st.session_state.track} at {st.session_state.level} level.")

# ================= MAIN CHAT UI =================
st.title("🇪🇸 Elite Spanish BPO & VA Coach")

# Display Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "---" in msg["content"]:
            parts = msg["content"].split("---")
            st.markdown(parts[0]) # Spanish Dialogue
            st.markdown(f"<div class='coach-box'>{parts[1]}</div>", unsafe_allow_html=True) # English Feedback
        else:
            st.markdown(msg["content"])
        
        if "audio" in msg and msg["audio"]:
            st.audio(msg["audio"])

# Handle Inputs
user_query = st.chat_input("Type your response in Spanish...")
audio_query = st.audio_input("Record your voice")

# Logic for Audio Transcription
if audio_query:
    try:
        with st.status("Transcribing...", expanded=False):
            # Groq Whisper requires a filename extension to determine format
            transcription = client.audio.transcriptions.create(
                file=("speech.wav", audio_query.getvalue()),
                model="whisper-large-v3",
                language="es",
                response_format="text"
            )
            user_query = transcription
    except Exception as e:
        st.error(f"Transcription failed: {e}")

# Process Input and Generate Response
if user_query:
    # Add user message to state
    st.session_state.messages.append({"role": "user", "content": user_query})
    
    # Generate AI Response
    with st.chat_message("assistant"):
        with st.spinner("Customer is responding..."):
            full_response = process_ai_chat(user_query)
            audio_path = generate_tts(full_response)
            
            # Display immediately
            if "---" in full_response:
                parts = full_response.split("---")
                st.markdown(parts[0])
                st.markdown(f"<div class='coach-box'>{parts[1]}</div>", unsafe_allow_html=True)
            else:
                st.markdown(full_response)
                
            if audio_path:
                st.audio(audio_path)
            
            # Save to history
            st.session_state.messages.append({
                "role": "assistant", 
                "content": full_response, 
                "audio": audio_path
            })
    st.rerun()
