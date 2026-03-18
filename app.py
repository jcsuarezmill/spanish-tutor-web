import streamlit as st
from groq import Groq
from gtts import gTTS
import tempfile
import os
import re
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup

# ================= 1. FILE PARSING UTILITIES =================
def extract_text(uploaded_file):
    """Extracts text from PDF, HTML, or TXT."""
    if uploaded_file is None:
        return ""
    
    file_type = uploaded_file.name.split('.')[-1].lower()
    
    try:
        if file_type == 'pdf':
            reader = PdfReader(uploaded_file)
            return " ".join([page.extract_text() for page in reader.pages])
        elif file_type == 'html':
            soup = BeautifulSoup(uploaded_file.read(), 'html.parser')
            return soup.get_text()
        else: # Treat as txt
            return uploaded_file.read().decode("utf-8")
    except Exception as e:
        st.error(f"Error reading file: {e}")
        return ""

# ================= 2. UI SETUP =================
st.set_page_config(page_title="Elite Spanish Coach", layout="wide")

# API Initialization
if "GROQ_API_KEY" in st.secrets:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
else:
    st.error("Missing GROQ_API_KEY in secrets.")
    st.stop()

# ================= 3. SESSION STATE =================
if "messages" not in st.session_state: st.session_state.messages = []
if "kb_text" not in st.session_state: st.session_state.kb_text = ""
if "resume_text" not in st.session_state: st.session_state.resume_text = ""

# ================= 4. PROMPT ENGINE =================
def get_system_prompt():
    role = st.session_state.role_mode
    scenario = st.session_state.custom_scenario
    kb = st.session_state.kb_text
    resume = st.session_state.resume_text
    level = st.session_state.target_level

    # Context Construction
    context = f"SCENARIO: {scenario}\nLEVEL: {level}\n"
    if kb: context += f"COMPANY/PRODUCT DATA: {kb[:2000]}\n" # Truncated for token safety
    if resume: context += f"USER/CANDIDATE DATA: {resume[:2000]}\n"

    # Role Mapping
    if "AI is Interviewer" in role:
        persona = "You are a Hiring Manager. Use the Company Data and User Resume to ask tough, specific interview questions in Spanish."
    elif "AI is Applicant" in role:
        persona = "You are a candidate being interviewed. Use the User Resume as YOUR background and the Company Data as the place you want to work."
    elif "AI is Customer" in role:
        persona = "You are a customer. Use the Company Data to complain or ask about specific services/products. Be realistic."
    else:
        persona = "You are a professional BPO Agent providing support based on the Company Data."

    return f"""
    SYSTEM ROLE: {persona}
    {context}

    STRICT OUTPUT FORMAT:
    [Spanish Dialogue ONLY]
    ---FEEDBACK---
    **Elite Coach Analysis**
    - **Mistakes Found:** (Correct any grammar/vocab errors the user made)
    - **Pro Phrase:** (A high-level Spanish 'Golden Phrase' for this exact moment)
    - **Tone Check:** (Was the user professional? Score 1-10)
    """

# ================= 5. SIDEBAR (RESOURCE CENTER) =================
with st.sidebar:
    st.title("🛡️ Simulation Control")
    
    st.session_state.role_mode = st.selectbox("Roleplay Mode", [
        "User as Applicant (AI is Interviewer)",
        "User as Interviewer (AI is Applicant)",
        "User as Agent (AI is Customer)",
        "User as Customer (AI is Agent)"
    ])
    
    st.session_state.target_level = st.select_slider("Target Level", ["A2", "B1", "B2", "C1", "C2"])
    
    st.session_state.custom_scenario = st.text_area("🚩 Define Custom Scenario", 
        placeholder="Example: The customer is angry about a late delivery... or: Interview for a Senior Manager role.",
        value="General professional interaction")

    st.divider()
    
    # File Uploaders
    st.subheader("📄 Upload Knowledge Base")
    kb_file = st.file_uploader("Upload Company SOP, Manual, or Website (PDF/HTML)", type=['pdf', 'html', 'txt'])
    if kb_file:
        st.session_state.kb_text = extract_text(kb_file)
        st.success("KB Loaded!")

    st.subheader("👤 Upload Resume")
    res_file = st.file_uploader("Upload Resume or Candidate Profile", type=['pdf', 'html', 'txt'])
    if res_file:
        st.session_state.resume_text = extract_text(res_file)
        st.success("Resume Loaded!")

    if st.button("🗑️ Reset Simulation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ================= 6. MAIN INTERFACE & LOGIC =================
st.title("🚀 Elite BPO & Interview Simulator")

# Display Messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "---FEEDBACK---" in msg["content"]:
            parts = msg["content"].split("---FEEDBACK---")
            st.markdown(parts[0])
            with st.expander("📝 Coach's Corner"):
                st.markdown(parts[1])
        else:
            st.markdown(msg["content"])

# Input Logic
user_input = None
audio_data = st.audio_input("Speak Spanish")
text_data = st.chat_input("Type your response...")

if audio_data:
    with st.status("Transcribing..."):
        transcript = client.audio.transcriptions.create(
            file=("speech.wav", audio_data.getvalue()), 
            model="whisper-large-v3", 
            language="es"
        )
        user_input = transcript.text

if text_data: user_input = text_data

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"): st.write(user_input)

    with st.chat_message("assistant"):
        # We pass only the last 10 messages for context, excluding the feedback parts
        history = []
        for m in st.session_state.messages[-10:]:
            content = m["content"].split("---FEEDBACK---")[0]
            history.append({"role": m["role"], "content": content})

        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": get_system_prompt()}] + history
        )
        
        full_response = completion.choices[0].message.content
        
        if "---FEEDBACK---" in full_response:
            dialogue = full_response.split("---FEEDBACK---")[0]
            st.markdown(dialogue)
            
            # TTS
            tts = gTTS(text=re.sub(r'[*#_~-]', '', dialogue), lang='es')
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                tts.save(fp.name)
                st.audio(fp.name)
                
            with st.expander("📝 Coach's Corner"):
                st.markdown(full_response.split("---FEEDBACK---")[1])
        else:
            st.markdown(full_response)
            
        st.session_state.messages.append({"role": "assistant", "content": full_response})
