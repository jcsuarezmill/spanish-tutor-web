import streamlit as st
from groq import Groq
from gtts import gTTS
import tempfile
import os

# ================= 1. UI CONFIGURATION =================
st.set_page_config(page_title="Elite Spanish Coach", page_icon="💼", layout="wide")

# Professional Styling
st.markdown("""
    <style>
    .main { background-color: #f4f7f6; }
    .stChatMessage { border-radius: 15px; padding: 15px; margin-bottom: 10px; border: 1px solid #e0e0e0; }
    .coach-card { 
        background-color: #ffffff; 
        border-left: 6px solid #10a37f; 
        padding: 20px; 
        border-radius: 10px; 
        margin-top: 10px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        color: #1a1a1a;
    }
    .golden-phrase { color: #d97706; font-weight: bold; background: #fffcf0; padding: 5px; border-radius: 3px; }
    .stAudio { margin-top: 10px; }
    </style>
""", unsafe_allow_html=True)

# API Initialization
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("🔑 API Key Missing. Please set GROQ_API_KEY in Streamlit Secrets.")
    st.stop()

# ================= 2. SESSION STATE =================
if "messages" not in st.session_state: st.session_state.messages = []
if "level" not in st.session_state: st.session_state.level = "B2"
if "scenario" not in st.session_state: st.session_state.scenario = "General BPO Support"
if "reset_key" not in st.session_state: st.session_state.reset_key = 0

# ================= 3. LOGIC ENGINES =================

def get_ai_response(user_input):
    """Fetches response from Groq with context and persona."""
    
    # Sanitize history for API (Only role and content)
    history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-8:]]
    
    system_prompt = f"""
    ROLE: Professional Spanish BPO Coach & Mock Call Simulator.
    SCENARIO: {st.session_state.scenario}. 
    USER PROFICIENCY: {st.session_state.level}.

    STRICT STRUCTURE:
    1. Respond naturally in Spanish as the person in the scenario.
    2. Add a separator '---'.
    3. Provide 'COACH'S CORNER' in English:
       - **Grammar/Vocab Correction**: Fix what the user just said.
       - **The Golden Phrase**: Provide the most professional, high-level BPO way to say that response.
       - **Pro Tip**: Advice on tone, speed, or empathy.
    """

    # We use llama-3.3-70b as primary, llama3-8b as fallback
    models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
    
    for model in models:
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": user_input}],
                temperature=0.7,
                max_tokens=1000
            )
            return completion.choices[0].message.content
        except Exception as e:
            if model == models[-1]: # If last model also fails
                return f"⚠️ Service error. Please wait a moment. Details: {str(e)}"
            continue # Try next model

def speak(text):
    """Converts only the Spanish dialogue to audio."""
    try:
        spanish_dialogue = text.split("---")[0].strip()
        tts = gTTS(text=spanish_dialogue, lang='es')
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            tts.save(fp.name)
            return fp.name
    except: return None

# ================= 4. SIDEBAR CONTROLS =================
with st.sidebar:
    st.title("💼 BPO Trainer Settings")
    
    st.session_state.level = st.select_slider("Select Proficiency Goal", 
                                            options=["A1", "A2", "B1", "B2", "C1", "C2"], 
                                            value=st.session_state.level)
    
    st.session_state.scenario = st.selectbox("Choose a Track", 
        ["General BPO Support", "Medical Intake VA", "Real Estate VA", "Tech Support Agent", "Hiring Interview", "CUSTOM SCENARIO"])
    
    if st.session_state.scenario == "CUSTOM SCENARIO":
        st.session_state.scenario = st.text_area("Type your specific scenario:", 
                                               placeholder="Ex: I am a customer calling to cancel a subscription...")

    st.divider()
    if st.button("🗑️ Clear & Restart Session", use_container_width=True):
        st.session_state.messages = []
        st.session_state.reset_key += 1
        st.rerun()

    st.caption("Tip: If audio fails to play, check if your browser is blocking auto-play or scripts.")

# ================= 5. CHAT INTERFACE =================
st.title("🇪🇸 Elite Spanish Professional Coach")
st.markdown(f"**Current Goal:** {st.session_state.scenario} at **{st.session_state.level}** level.")

# Display Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "---" in msg["content"]:
            parts = msg["content"].split("---")
            st.markdown(f"**🗣️ Response:** {parts[0]}")
            st.markdown(f"<div class='coach-card'>{parts[1]}</div>", unsafe_allow_html=True)
        else:
            st.markdown(msg["content"])
        if "audio" in msg: st.audio(msg["audio"])

# Input Logic
final_input = None

# Audio Input (Using reset_key to clear buffer)
audio_data = st.audio_input("Record your Spanish response", key=f"audio_{st.session_state.reset_key}")
if audio_data:
    with st.status("Transcribing speech...", expanded=False):
        try:
            transcript = client.audio.transcriptions.create(
                file=("input.wav", audio_data.getvalue()),
                model="whisper-large-v3",
                language="es",
                response_format="text"
            )
            final_input = transcript
        except Exception as e:
            st.error(f"Transcription failed: {e}")

# Text Input fallback
text_data = st.chat_input("Or type your response here...")
if text_data:
    final_input = text_data

# ================= 6. GENERATION ENGINE =================
if final_input:
    # 1. Save User Input
    st.session_state.messages.append({"role": "user", "content": final_input})
    
    # 2. Get AI Response
    with st.chat_message("assistant"):
        with st.spinner("Coach is analyzing and responding..."):
            full_resp = get_ai_response(final_input)
            audio_path = speak(full_resp)
            
            # Display
            if "---" in full_resp:
                parts = full_resp.split("---")
                st.markdown(f"**🗣️ Response:** {parts[0]}")
                st.markdown(f"<div class='coach-card'>{parts[1]}</div>", unsafe_allow_html=True)
            else:
                st.markdown(full_resp)
                
            if audio_path:
                st.audio(audio_path)

            # Save to history
            st.session_state.messages.append({"role": "assistant", "content": full_resp, "audio": audio_path})
    
    # Reset widget to prevent loops
    st.session_state.reset_key += 1
    st.rerun()
