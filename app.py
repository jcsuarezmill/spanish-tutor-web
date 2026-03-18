import streamlit as st
from groq import Groq
from gtts import gTTS
import tempfile
import os
import re

# ================= 1. UI CONFIGURATION =================
st.set_page_config(page_title="Professional BPO Dual-Coach", page_icon="🎧", layout="wide")

st.markdown("""
    <style>
    .stChatMessage { border-radius: 15px; padding: 15px; margin-bottom: 10px; border: 1px solid #e0e0e0; }
    .persona-label { color: #1a73e8; font-weight: bold; font-size: 1.1rem; margin-bottom: 5px; }
    .coach-card { 
        background-color: #f1f8e9; 
        border-left: 6px solid #4caf50; 
        padding: 18px; 
        border-radius: 12px; 
        margin-top: 15px;
        color: #1b5e20;
    }
    .feedback-header { color: #2e7d32; font-weight: bold; text-transform: uppercase; font-size: 0.85rem; margin-bottom: 8px; }
    </style>
""", unsafe_allow_html=True)

# API Initialization
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("🔑 API Key Missing. Add your new key to '.streamlit/secrets.toml' as GROQ_API_KEY")
    st.stop()

# ================= 2. SESSION STATE =================
if "messages" not in st.session_state: st.session_state.messages = []
if "level" not in st.session_state: st.session_state.level = "B2"
if "scenario" not in st.session_state: st.session_state.scenario = "Billing Complaint"
if "user_role" not in st.session_state: st.session_state.user_role = "Agent (User handles call)"
if "reset_key" not in st.session_state: st.session_state.reset_key = 0

# ================= 3. LOGIC ENGINES =================

def get_dual_prompt():
    is_agent = "Agent" in st.session_state.user_role
    persona = "A frustrated customer" if is_agent else "An ELITE BPO Professional Agent"
    
    return f"""
    SYSTEM ROLE: You are an Elite Spanish Coach. 
    1. ACT AS: {persona}. SCENARIO: {st.session_state.scenario}. LEVEL: {st.session_state.level}.
    2. COACHING: Provide high-level feedback after '---'.

    STRICT FEEDBACK STRUCTURE:
    [Spanish Dialogue Only]
    ---
    **COACH'S CORNER**
    - **Spiel & Phrasing:** (Critique the dialogue and provide a 'Golden Phrase' alternative)
    - **Soft Skills & Tone:** (Rate professionalism 1-10)
    - **Voice & Pronunciation:** (Analyze the transcription for clarity. If words seem misspelled in the transcript, suggest it might be a pronunciation issue.)
    - **Pro Tip:** (One trick to sound like a native professional)
    """

def get_ai_response(user_input):
    history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-6:]]
    
    # LIST OF MODELS FOR FALLBACK (70b -> 8b)
    # If the smart one is rate-limited, use the fast one.
    models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
    
    for model in models:
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": get_dual_prompt()}] + history + [{"role": "user", "content": user_input}],
                temperature=0.7
            )
            return completion.choices[0].message.content
        except Exception as e:
            if "429" in str(e) and model != models[-1]:
                continue # Try the next model in the list
            return f"⚠️ Error: {str(e)}"

def speak(text):
    """Clean text and convert to audio."""
    try:
        # 1. Take only the Spanish dialogue
        dialogue = text.split("---")[0].strip()
        # 2. REMOVE ALL ASTERISKS AND MARKDOWN SYMBOLS FOR THE VOICE
        clean_text = re.sub(r'[*#_~]', '', dialogue)
        
        tts = gTTS(text=clean_text, lang='es')
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            tts.save(fp.name)
            return fp.name
    except: return None

# ================= 4. SIDEBAR =================
with st.sidebar:
    st.title("🎧 Training Center")
    st.session_state.user_role = st.radio("Switch Your Role:", 
                                         ["Agent (User handles call)", "Customer (AI handles call)"])
    st.divider()
    st.session_state.level = st.select_slider("My Target Level", ["A1", "A2", "B1", "B2", "C1", "C2"], value=st.session_state.level)
    
    st.session_state.scenario = st.selectbox("Scenario", ["Billing Complaint", "Tech Support", "Medical VA", "Hiring Interview", "CUSTOM"])
    if st.session_state.scenario == "CUSTOM":
        st.session_state.scenario = st.text_input("Describe scenario:")

    if st.button("🗑️ New Call / Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.reset_key += 1
        st.rerun()

# ================= 5. MAIN CHAT UI =================
st.title("🇪🇸 BPO Professional Dual-Coach")
st.info(f"**MODE:** You are the **{'AGENT' if 'Agent' in st.session_state.user_role else 'CUSTOMER'}**")

# Display Messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "---" in msg["content"]:
            parts = msg["content"].split("---")
            label = "👤 Customer" if "Agent" in st.session_state.user_role else "🎧 Elite Agent"
            st.markdown(f"<div class='persona-label'>{label}</div>", unsafe_allow_html=True)
            st.markdown(parts[0])
            st.markdown(f"<div class='coach-card'><div class='feedback-header'>👨‍🏫 Performance Coaching</div>{parts[1]}</div>", unsafe_allow_html=True)
        else:
            st.markdown(msg["content"])
        if "audio" in msg: st.audio(msg["audio"])

# Input Logic
final_input = None
audio_data = st.audio_input("Record your voice", key=f"audio_{st.session_state.reset_key}")

if audio_data:
    with st.status("Transcribing...", expanded=False):
        transcript = client.audio.transcriptions.create(file=("in.wav", audio_data.getvalue()), model="whisper-large-v3", language="es", response_format="text")
        final_input = transcript

text_data = st.chat_input("Type your response...")
if text_data: final_input = text_data

# ================= 6. EXECUTION =================
if final_input:
    st.session_state.messages.append({"role": "user", "content": final_input})
    
    with st.chat_message("assistant"):
        with st.spinner("Analyzing interaction..."):
            full_resp = get_ai_response(final_input)
            audio_path = speak(full_resp)
            
            if "---" in full_resp:
                parts = full_resp.split("---")
                label = "👤 Customer" if "Agent" in st.session_state.user_role else "🎧 Elite Agent"
                st.markdown(f"<div class='persona-label'>{label}</div>", unsafe_allow_html=True)
                st.markdown(parts[0])
                st.markdown(f"<div class='coach-card'><div class='feedback-header'>👨‍🏫 Performance Coaching</div>{parts[1]}</div>", unsafe_allow_html=True)
            else:
                st.markdown(full_resp)
            
            if audio_path: st.audio(audio_path)
            st.session_state.messages.append({"role": "assistant", "content": full_resp, "audio": audio_path})
    
    st.session_state.reset_key += 1
    st.rerun()

# Auto-Greeting for Customer Mode
if not st.session_state.messages and "Customer" in st.session_state.user_role:
    greeting = "🎧 **Elite Agent:** 'Gracias por llamar a soporte técnico, mi nombre es Juan. ¿Con quién tengo el gusto de hablar?'"
    st.session_state.messages.append({"role": "assistant", "content": greeting})
    st.rerun()
