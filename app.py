import streamlit as st
from groq import Groq
from gtts import gTTS
import tempfile
import os

# ================= 1. UI CONFIGURATION =================
st.set_page_config(page_title="Elite Spanish BPO Coach", page_icon="💼", layout="wide")

st.markdown("""
    <style>
    .stChatMessage { border-radius: 15px; padding: 15px; margin-bottom: 10px; border: 1px solid #e0e0e0; }
    .customer-box { color: #2e7d32; font-weight: bold; font-size: 1.2rem; margin-bottom: 5px; }
    .coach-card { 
        background-color: #f0f7ff; 
        border-left: 6px solid #0288d1; 
        padding: 15px; 
        border-radius: 10px; 
        margin-top: 10px;
        color: #01579b;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .golden-phrase { color: #ef6c00; font-weight: bold; background: #fff3e0; padding: 2px 5px; border-radius: 4px; }
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

def get_bpo_prompt():
    scenarios = {
        "General BPO Support": "A frustrated customer calling because their internet bill is $100 higher than usual. They want a credit.",
        "Medical Intake VA": "A patient in mild pain calling to book a follow-up appointment after a gallstone surgery.",
        "Real Estate VA": "A wealthy investor asking about property taxes and HOA fees for a condo in Miami.",
        "Tech Support Agent": "A non-technical elderly person whose printer is making a loud grinding noise.",
        "Hiring Interview": "A strict HR Manager interviewing the user for a high-paying Bilingual VA position."
    }
    details = scenarios.get(st.session_state.scenario, st.session_state.scenario)
    
    return f"""
    SYSTEM ROLE: 
    You are a dual-persona AI. 
    1. PRIMARY ROLE: You are the CUSTOMER/CLIENT in this scenario: {details}.
    2. SECONDARY ROLE: You are a Professional BPO Coach.

    STRICT INTERACTION RULES:
    - The User is the BPO Agent. 
    - You must act realistically. If the user says something unprofessional, react as a customer would (get annoyed or confused).
    - Do NOT be a teacher in the first half of your response. Be the character.
    - Your Spanish must match the level: {st.session_state.level}.

    RESPONSE STRUCTURE (MANDATORY):
    [Spanish Customer Dialogue]
    ---
    **COACH'S CORNER**
    **Correction:** (Fix the user's last Spanish mistake)
    **The Golden Phrase:** (Show the most professional BPO industry standard way to say it)
    **Soft Skills Note:** (Critique the user's empathy, tone, or efficiency)
    """

def get_ai_response(user_input):
    history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-6:]]
    
    # Model fallback logic
    models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
    
    for model in models:
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": get_bpo_prompt()}] + history + [{"role": "user", "content": user_input}],
                temperature=0.8
            )
            return completion.choices[0].message.content
        except Exception:
            if model == models[-1]: return "⚠️ Groq is overloaded. Please try again in 10 seconds."
            continue

def speak(text):
    try:
        spanish_dialogue = text.split("---")[0].strip()
        tts = gTTS(text=spanish_dialogue, lang='es')
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            tts.save(fp.name)
            return fp.name
    except: return None

# ================= 4. SIDEBAR =================
with st.sidebar:
    st.title("💼 BPO Coach Settings")
    st.session_state.level = st.select_slider("Goal Proficiency", ["A1", "A2", "B1", "B2", "C1", "C2"], value=st.session_state.level)
    
    choice = st.selectbox("Scenario Track", ["General BPO Support", "Medical Intake VA", "Real Estate VA", "Tech Support Agent", "Hiring Interview", "CUSTOM SCENARIO"])
    if choice == "CUSTOM SCENARIO":
        st.session_state.scenario = st.text_area("Describe the customer & problem:")
    else:
        st.session_state.scenario = choice

    st.divider()
    if st.button("🗑️ Reset Call / New Customer", use_container_width=True):
        st.session_state.messages = []
        st.session_state.reset_key += 1
        st.rerun()

# ================= 5. CHAT UI =================
st.title("🇪🇸 Professional BPO Call Simulator")
st.caption(f"Track: {st.session_state.scenario} | Goal: {st.session_state.level}")

# Display Chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "---" in msg["content"]:
            parts = msg["content"].split("---")
            st.markdown(f"<div class='customer-box'>👤 Customer</div>", unsafe_allow_html=True)
            st.markdown(parts[0])
            st.markdown(f"<div class='coach-card'><b>👨‍🏫 Coach's Corner</b><br>{parts[1]}</div>", unsafe_allow_html=True)
        else:
            st.markdown(msg["content"])
        if "audio" in msg: st.audio(msg["audio"])

# Inputs
final_input = None
audio_data = st.audio_input("Speak to the customer", key=f"audio_{st.session_state.reset_key}")
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
        with st.spinner("Customer is responding..."):
            full_resp = get_ai_response(final_input)
            audio_path = speak(full_resp)
            
            if "---" in full_resp:
                parts = full_resp.split("---")
                st.markdown(f"<div class='customer-box'>👤 Customer</div>", unsafe_allow_html=True)
                st.markdown(parts[0])
                st.markdown(f"<div class='coach-card'><b>👨‍🏫 Coach's Corner</b><br>{parts[1]}</div>", unsafe_allow_html=True)
            else:
                st.markdown(full_resp)
            
            if audio_path: st.audio(audio_path)
            st.session_state.messages.append({"role": "assistant", "content": full_resp, "audio": audio_path})
    
    st.session_state.reset_key += 1
    st.rerun()

# Initial Greeting if Chat is Empty
if not st.session_state.messages:
    with st.chat_message("assistant"):
        st.write("✨ **System:** Call connected. The customer is waiting for your greeting. (Say 'Hola, ¿en qué puedo ayudarle?')")
