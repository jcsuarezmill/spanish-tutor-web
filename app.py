import streamlit as st
from groq import Groq
from gtts import gTTS
import tempfile
import os
import re

# ================= 1. PRO-LEVEL UI SETUP =================
st.set_page_config(page_title="Elite BPO Coach Pro", page_icon="🎧", layout="wide")

st.markdown("""
    <style>
    .stChatMessage { border-radius: 15px; margin-bottom: 20px; border: 1px solid #e0e0e0; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    .persona-tag { font-weight: bold; text-transform: uppercase; font-size: 0.8rem; padding: 3px 8px; border-radius: 5px; margin-bottom: 10px; display: inline-block; }
    .tag-customer { background-color: #ffebee; color: #c62828; }
    .tag-agent { background-color: #e8f5e9; color: #2e7d32; }
    .coach-card { 
        background-color: #fff9c4; 
        border-left: 6px solid #fbc02d; 
        padding: 20px; border-radius: 12px; margin-top: 15px;
        color: #333; font-size: 0.95rem; line-height: 1.5;
    }
    .golden-phrase { color: #e65100; font-weight: bold; background: #fff3e0; padding: 2px 5px; border-radius: 4px; }
    </style>
""", unsafe_allow_html=True)

# API Initialization
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception:
    st.error("🔑 API Key Missing. Please add GROQ_API_KEY to your Streamlit Secrets.")
    st.stop()

# ================= 2. SESSION STATE (STABILITY) =================
if "messages" not in st.session_state: st.session_state.messages = []
if "user_role" not in st.session_state: st.session_state.user_role = "Agent (You handle the call)"
if "level" not in st.session_state: st.session_state.level = "B2"
if "scenario" not in st.session_state: st.session_state.scenario = "Billing Complaint"
if "reset_key" not in st.session_state: st.session_state.reset_key = 0

# ================= 3. THE ENGINE ROOM (FOOLPROOF LOGIC) =================

def get_system_prompt():
    """Generates a high-immersion prompt based on the chosen role."""
    is_user_agent = "Agent" in st.session_state.user_role
    
    if is_user_agent:
        persona = "A frustrated but realistic customer named Roberto. You have a specific billing issue."
        instruction = "The user is the BPO Agent. Respond as a customer would—sometimes impatient, sometimes confused."
    else:
        persona = "An ELITE BPO Professional Agent named Sofia. You have 10 years of experience."
        instruction = "The user is the customer. Provide world-class service, empathy, and perfect BPO protocols."

    return f"""
    SYSTEM ROLE: 
    {persona}. 
    SCENARIO: {st.session_state.scenario}. 
    LEVEL: {st.session_state.level}.

    RULES:
    1. Stay 100% in character for the dialogue. 
    2. Respond to the user's specific words. 
    3. Use the separator '---' to switch from your character to your coaching role.
    4. Provide the Coach's Corner ONLY after the '---'.

    FEEDBACK STRUCTURE (English):
    ---
    **COACH'S CORNER**
    - **Transcription Review:** (Analyze if the user's speech was clear)
    - **Grammar & Vocab:** (Correct any Spanish errors)
    - **The Golden Phrase:** (Provide the #1 most professional way to handle this specific moment)
    - **Soft Skills:** (Grade the empathy and professional tone 1-10)
    """

def get_clean_history():
    """CRITICAL: Removes old coaching notes so the AI stays in character."""
    clean = []
    for m in st.session_state.messages[-8:]: # Last 8 interactions
        content = m["content"]
        if "---" in content:
            content = content.split("---")[0].strip() # Strip coaching
        clean.append({"role": m["role"], "content": content})
    return clean

def get_ai_response(user_text):
    """Fetches AI response with model fallback logic."""
    models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
    history = get_clean_history()
    
    for model in models:
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": get_system_prompt()}] + history + [{"role": "user", "content": user_text}],
                temperature=0.8
            )
            return completion.choices[0].message.content
        except Exception as e:
            if "429" in str(e) and model != models[-1]: continue
            return f"⚠️ Error: {str(e)}"

def generate_voice(full_text):
    """Sanitizes text and generates professional TTS."""
    try:
        dialogue = full_text.split("---")[0].strip()
        # Remove all markdown/symbols for the voice engine
        clean_voice_text = re.sub(r'[*#_~-]', '', dialogue)
        tts = gTTS(text=clean_voice_text, lang='es')
        fp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(fp.name)
        return fp.name
    except: return None

# ================= 4. SIDEBAR (CONTROL PANEL) =================
with st.sidebar:
    st.title("🚀 Career Training Center")
    
    # Role Selector (Resets on change)
    role_choice = st.radio("Choose Your Practice Role:", 
                          ["Agent (You handle the call)", "Customer (AI handles the call)"])
    if role_choice != st.session_state.user_role:
        st.session_state.user_role = role_choice
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.session_state.level = st.select_slider("Target Spanish Level:", ["A1", "A2", "B1", "B2", "C1", "C2"], value=st.session_state.level)
    
    scenario_list = ["Billing Complaint", "Medical VA (Scheduling)", "Real Estate (Lead Gen)", "Tech Support Agent", "CUSTOM SCENARIO"]
    st.session_state.scenario = st.selectbox("Scenario:", scenario_list)
    if st.session_state.scenario == "CUSTOM SCENARIO":
        st.session_state.scenario = st.text_input("Describe your custom scenario:")

    if st.button("🗑️ Reset Interaction", use_container_width=True):
        st.session_state.messages = []
        st.session_state.reset_key += 1
        st.rerun()

# ================= 5. MAIN INTERFACE =================
st.title("🇪🇸 Elite Spanish BPO Coach")
mode_label = "AGENT" if "Agent" in st.session_state.user_role else "CUSTOMER"
st.info(f"**MODE:** You are practicing as the **{mode_label}**")

# Display Messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "---" in msg["content"]:
            parts = msg["content"].split("---")
            tag_class = "tag-customer" if "Agent" in st.session_state.user_role else "tag-agent"
            tag_label = "👤 Customer" if "Agent" in st.session_state.user_role else "🎧 Elite Agent"
            
            st.markdown(f"<div class='persona-tag {tag_class}'>{tag_label}</div>", unsafe_allow_html=True)
            st.markdown(parts[0]) # Dialogue
            st.markdown(f"<div class='coach-card'><b>👨‍🏫 Coach's Corner</b><br>{parts[1]}</div>", unsafe_allow_html=True)
        else:
            st.markdown(msg["content"])
        if "audio" in msg: st.audio(msg["audio"])

# ================= 6. INPUT PIPELINE =================
user_input = None

# Audio Handler
audio_data = st.audio_input("Record your Spanish response", key=f"audio_{st.session_state.reset_key}")
if audio_data:
    with st.status("Transcribing...", expanded=False):
        transcript = client.audio.transcriptions.create(
            file=("speech.wav", audio_data.getvalue()), 
            model="whisper-large-v3", 
            language="es", 
            response_format="text"
        )
        user_input = transcript

# Text Fallback
text_input = st.chat_input("Or type your response here...")
if text_input: user_input = text_input

# ================= 7. PROCESSING LOOP =================
if user_input:
    # 1. Store User Input
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # 2. Generate AI Response
    with st.chat_message("assistant"):
        with st.spinner("Wait, the character is responding..."):
            ai_raw = get_ai_response(user_input)
            audio_path = generate_voice(ai_raw)
            
            # Display Immediately
            if "---" in ai_raw:
                parts = ai_raw.split("---")
                tag_class = "tag-customer" if "Agent" in st.session_state.user_role else "tag-agent"
                tag_label = "👤 Customer" if "Agent" in st.session_state.user_role else "🎧 Elite Agent"
                st.markdown(f"<div class='persona-tag {tag_class}'>{tag_label}</div>", unsafe_allow_html=True)
                st.markdown(parts[0])
                st.markdown(f"<div class='coach-card'><b>👨‍🏫 Coach's Corner</b><br>{parts[1]}</div>", unsafe_allow_html=True)
            else:
                st.markdown(ai_raw)
                
            if audio_path: st.audio(audio_path)
            
            # 3. Save to History
            st.session_state.messages.append({"role": "assistant", "content": ai_raw, "audio": audio_path})
    
    # 4. Clean up and Refresh
    st.session_state.reset_key += 1
    st.rerun()

# Initial Prompt for "Customer" Mode
if not st.session_state.messages and "Customer" in st.session_state.user_role:
    initial_greet = "🎧 **Elite Agent:** 'Gracias por llamar a soporte técnico, mi nombre es Juan. ¿Con quién tengo el gusto de hablar?'"
    st.session_state.messages.append({"role": "assistant", "content": initial_greet})
    st.rerun()
