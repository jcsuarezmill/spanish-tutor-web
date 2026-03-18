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
        background-color: #fff9c4; 
        border-left: 6px solid #fbc02d; 
        padding: 18px; 
        border-radius: 12px; 
        margin-top: 15px;
        color: #424242;
    }
    .feedback-header { color: #f57f17; font-weight: bold; text-transform: uppercase; font-size: 0.85rem; margin-bottom: 8px; }
    </style>
""", unsafe_allow_html=True)

# API Initialization
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("🔑 API Key Missing. Please add GROQ_API_KEY to your Streamlit Secrets.")
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
    persona = "A FRUSTRATED CUSTOMER (Speak with emotion)" if is_agent else "AN ELITE BPO PROFESSIONAL AGENT (Speak with perfect empathy)"
    
    return f"""
    SYSTEM ROLE: 
    1. ACT AS: {persona}. Your name is Juan/Maria. 
    2. SCENARIO: {st.session_state.scenario}. 
    3. CURRENT LEVEL: {st.session_state.level}.

    STRICT RESPONSE RULE:
    - You MUST start your response with a direct reply in character.
    - If you are the Customer, react to what the Agent said.
    - If you are the Agent, provide professional service.
    - After your character dialogue, add a separator '---' and then provide COACHING feedback.

    OUTPUT FORMAT:
    [Character Speech in Spanish]
    ---
    **COACH'S CORNER**
    - **Spiel & Phrasing:** (Critique and provide a 'Golden Phrase' alternative)
    - **Soft Skills & Tone:** (Rate 1-10)
    - **Voice & Pronunciation:** (Analyze transcription)
    - **Pro Tip:** (One trick for BPO success)
    """

def get_ai_response(user_input):
    # --- CRITICAL FIX: HISTORY SCRUBBING ---
    # We strip the "Coach's Corner" from previous AI messages so the AI doesn't get confused.
    scrubbed_history = []
    for m in st.session_state.messages[-6:]:
        content = m["content"]
        if "---" in content:
            content = content.split("---")[0].strip() # Take only the dialogue part
        scrubbed_history.append({"role": m["role"], "content": content})
    
    models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
    
    for model in models:
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": get_dual_prompt()}] + scrubbed_history + [{"role": "user", "content": user_input}],
                temperature=0.8 # Slightly higher for more realistic personality
            )
            return completion.choices[0].message.content
        except Exception as e:
            if "429" in str(e) and model != models[-1]: continue
            return f"⚠️ Error: {str(e)}"

def speak(text):
    try:
        dialogue = text.split("---")[0].strip()
        clean_text = re.sub(r'[*#_~]', '', dialogue)
        tts = gTTS(text=clean_text, lang='es')
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            tts.save(fp.name)
            return fp.name
    except: return None

# ================= 4. SIDEBAR =================
with st.sidebar:
    st.title("🎧 Training Center")
    new_role = st.radio("Switch Your Role:", ["Agent (User handles call)", "Customer (AI handles call)"])
    if new_role != st.session_state.user_role:
        st.session_state.user_role = new_role
        st.session_state.messages = [] # Reset on role change for fresh start
        st.rerun()

    st.divider()
    st.session_state.level = st.select_slider("My Target Level", ["A1", "A2", "B1", "B2", "C1", "C2"], value=st.session_state.level)
    st.session_state.scenario = st.selectbox("Scenario", ["Billing Complaint", "Tech Support", "Medical VA", "Real Estate Inquiry", "CUSTOM"])
    
    if st.button("🗑️ Reset Interaction", use_container_width=True):
        st.session_state.messages = []
        st.session_state.reset_key += 1
        st.rerun()

# ================= 5. CHAT UI =================
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
audio_data = st.audio_input("Record your response", key=f"audio_{st.session_state.reset_key}")
if audio_data:
    with st.status("Transcribing...", expanded=False):
        transcript = client.audio.transcriptions.create(file=("in.wav", audio_data.getvalue()), model="whisper-large-v3", language="es", response_format="text")
        final_input = transcript

text_data = st.chat_input("Type here...")
if text_data: final_input = text_data

# ================= 6. EXECUTION =================
if final_input:
    st.session_state.messages.append({"role": "user", "content": final_input})
    
    with st.chat_message("assistant"):
        with st.spinner("Wait, the character is responding..."):
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
