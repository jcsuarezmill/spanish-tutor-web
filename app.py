import streamlit as st
from groq import Groq
from gtts import gTTS
import tempfile
import os
import re

# ================= 1. ADVANCED UI SETUP =================
st.set_page_config(page_title="Elite BPO & Interview Coach", page_icon="🎧", layout="wide")

st.markdown("""
    <style>
    .stChatMessage { border-radius: 15px; margin-bottom: 20px; border: 1px solid #e0e0e0; }
    .persona-tag { font-weight: bold; text-transform: uppercase; font-size: 0.75rem; padding: 2px 8px; border-radius: 4px; margin-bottom: 8px; display: inline-block; }
    .tag-customer { background-color: #ffebee; color: #c62828; }
    .tag-agent { background-color: #e8f5e9; color: #2e7d32; }
    .tag-interviewer { background-color: #e3f2fd; color: #1565c0; }
    .golden-phrase { color: #2e7d32; font-weight: bold; background: #f1f8e9; padding: 2px 5px; border-radius: 4px; }
    /* Hide the feedback from standard view if needed, but we use expanders */
    </style>
""", unsafe_allow_html=True)

# API Initialization
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception:
    st.error("🔑 API Key Missing. Please add GROQ_API_KEY to your Streamlit Secrets.")
    st.stop()

# ================= 2. SESSION STATE =================
if "messages" not in st.session_state: st.session_state.messages = []
if "level" not in st.session_state: st.session_state.level = "B2"
if "role" not in st.session_state: st.session_state.role = "User as Agent (AI as Customer)"
if "scenario" not in st.session_state: st.session_state.scenario = "Billing Complaint"
if "company_info" not in st.session_state: st.session_state.company_info = ""
if "user_resume" not in st.session_state: st.session_state.user_resume = ""
if "reset_key" not in st.session_state: st.session_state.reset_key = 0

# ================= 3. THE KNOWLEDGE ENGINE =================

def get_system_prompt():
    """Constructs a high-context prompt using uploaded resources."""
    role = st.session_state.role
    level = st.session_state.level
    scenario = st.session_state.scenario
    kb = st.session_state.company_info
    resume = st.session_state.user_resume

    # Base Context
    context = f"SCENARIO: {scenario}. LEVEL: {level}.\n"
    if kb: context += f"COMPANY KNOWLEDGE BASE: {kb}\n"
    if resume: context += f"USER RESUME/PROFILE: {resume}\n"

    # Role Logic
    if "Interviewer" in role:
        persona = "You are a Hiring Manager/Interviewer. Use the Company Info to ask specific questions and the Resume to challenge the candidate."
    elif "AI as Agent" in role:
        persona = "You are an ELITE BPO Agent. Use the Company Knowledge Base to provide perfect support and spiels."
    else:
        persona = "You are a Customer calling into the company described in the Knowledge Base."

    return f"""
    SYSTEM ROLE: {persona}
    {context}

    STRICT OUTPUT FORMAT:
    [Spanish Dialogue ONLY]
    ---SPLIT---
    **COACH'S CORNER**
    - **Transcription Review:** (Correct pronunciation/misheard words)
    - **Grammar & Vocab:** (Correct Spanish errors)
    - **Elite Spielberg:** (Provide a 'Golden Phrase' for the user to use next time)
    - **Professionalism Rating:** (Score 1-10 based on BPO/Interview standards)
    """

def get_clean_history():
    """The 'Memory Firewall' - scrubs feedback so AI stays in character."""
    clean = []
    for m in st.session_state.messages[-10:]:
        content = m["content"]
        if "---SPLIT---" in content:
            content = content.split("---SPLIT---")[0].strip()
        clean.append({"role": m["role"], "content": content})
    return clean

def generate_voice(full_text):
    """Voice Engine: ONLY speaks the Spanish part. Ignores Coaching."""
    try:
        dialogue = full_text.split("---SPLIT---")[0].strip()
        clean_text = re.sub(r'[*#_~-]', '', dialogue)
        tts = gTTS(text=clean_text, lang='es')
        fp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(fp.name)
        return fp.name
    except: return None

# ================= 4. SIDEBAR (RESOURCE CENTER) =================
with st.sidebar:
    st.title("🛡️ Coaching Resource Center")
    
    # 1. Role Selector
    st.session_state.role = st.selectbox("Current Mode:", [
        "User as Agent (AI as Customer)",
        "User as Customer (AI as Agent)",
        "User as Applicant (AI as Interviewer)"
    ])
    
    st.divider()
    
    # 2. Level and Scenario
    st.session_state.level = st.select_slider("Target Proficiency:", ["A1", "A2", "B1", "B2", "C1", "C2"], value=st.session_state.level)
    st.session_state.scenario = st.text_input("Scenario / Job Title:", value=st.session_state.scenario)

    st.divider()
    
    # 3. Knowledge Injection
    with st.expander("📁 Import Company Details / SOPs"):
        st.session_state.company_info = st.text_area("Paste Company Info, FAQ, or Job Description here...", height=150)
        
    with st.expander("📄 Import Your Resume / Profile"):
        st.session_state.user_resume = st.text_area("Paste your Resume or experience details here...", height=150)

    if st.button("🗑️ Reset All Progress", use_container_width=True):
        st.session_state.messages = []
        st.session_state.reset_key += 1
        st.rerun()

# ================= 5. MAIN CHAT INTERFACE =================
st.title("🇪🇸 Elite BPO & Interview Simulator")
st.caption(f"Active Mode: {st.session_state.role}")

# Display Logic
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "---SPLIT---" in msg["content"]:
            parts = msg["content"].split("---SPLIT---")
            
            # Label Assignment
            if "Interviewer" in st.session_state.role: tag, cls = "👔 Interviewer", "tag-interviewer"
            elif "AI as Agent" in st.session_state.role: tag, cls = "🎧 Elite Agent", "tag-agent"
            else: tag, cls = "👤 Customer", "tag-customer"
            
            st.markdown(f"<div class='persona-tag {cls}'>{tag}</div>", unsafe_allow_html=True)
            st.markdown(parts[0]) # The Dialogue
            
            # The Hidden Coaching (Expander)
            with st.expander("➕ View Professional Coaching & Feedback"):
                st.markdown(parts[1])
        else:
            st.markdown(msg["content"])
        
        if "audio" in msg: st.audio(msg["audio"])

# ================= 6. THE INPUT PIPELINE =================
user_input = None
audio_data = st.audio_input("Speak in Spanish", key=f"audio_{st.session_state.reset_key}")

if audio_data:
    with st.status("Transcribing...", expanded=False):
        transcript = client.audio.transcriptions.create(
            file=("speech.wav", audio_data.getvalue()), 
            model="whisper-large-v3", 
            language="es", 
            response_format="text"
        )
        user_input = transcript

text_data = st.chat_input("Type your response...")
if text_data: user_input = text_data

# ================= 7. RESPONSE LOGIC =================
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            # AI Logic
            raw_ai = ""
            models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
            for model in models:
                try:
                    comp = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "system", "content": get_system_prompt()}] + get_clean_history() + [{"role": "user", "content": user_input}],
                        temperature=0.7
                    )
                    raw_ai = comp.choices[0].message.content
                    break
                except: continue
            
            # Audio Generation (Dialogue Only)
            audio_path = generate_voice(raw_ai)
            
            # UI Display
            if "---SPLIT---" in raw_ai:
                parts = raw_ai.split("---SPLIT---")
                if "Interviewer" in st.session_state.role: tag, cls = "👔 Interviewer", "tag-interviewer"
                elif "AI as Agent" in st.session_state.role: tag, cls = "🎧 Elite Agent", "tag-agent"
                else: tag, cls = "👤 Customer", "tag-customer"
                
                st.markdown(f"<div class='persona-tag {cls}'>{tag}</div>", unsafe_allow_html=True)
                st.markdown(parts[0])
                with st.expander("➕ View Professional Coaching & Feedback"):
                    st.markdown(parts[1])
            else:
                st.markdown(raw_ai)
            
            if audio_path: st.audio(audio_path)
            
            # Save to History
            st.session_state.messages.append({"role": "assistant", "content": raw_ai, "audio": audio_path})
    
    st.session_state.reset_key += 1
    st.rerun()

# Initial Trigger
if not st.session_state.messages:
    # Role-based starting greetings
    if "AI as Agent" in st.session_state.role:
        start = "🎧 **Elite Agent:** 'Gracias por llamar, mi nombre es Juan. ¿En qué puedo asistirle hoy?'"
    elif "Interviewer" in st.session_state.role:
        start = "👔 **Interviewer:** 'Hola, bienvenido. He revisado su perfil. Para comenzar, hábleme de su experiencia relevante.'"
    else:
        start = "✨ **System:** Llamada conectada. El cliente está esperando. (Diga 'Hola, ¿en qué puedo ayudarle?')"
    
    st.session_state.messages.append({"role": "assistant", "content": start})
    st.rerun()
