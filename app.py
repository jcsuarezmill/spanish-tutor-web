import streamlit as st
from groq import Groq
from gtts import gTTS
import tempfile
import os
import re
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup

# ================= 1. ADVANCED FILE PROCESSING =================
def extract_text_from_file(uploaded_file):
    """Handles PDF, HTML, and TXT extraction."""
    if uploaded_file is None:
        return ""
    file_extension = uploaded_file.name.split('.')[-1].lower()
    
    try:
        if file_extension == 'pdf':
            pdf_reader = PdfReader(uploaded_file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
        elif file_extension == 'html':
            soup = BeautifulSoup(uploaded_file.read(), 'html.parser')
            return soup.get_text()
        else:
            return uploaded_file.read().decode("utf-8")
    except Exception as e:
        st.error(f"Error processing {uploaded_file.name}: {e}")
        return ""

# ================= 2. UI & SESSION STATE =================
st.set_page_config(page_title="Elite Spanish Coach Pro", page_icon="🎙️", layout="wide")

# Initialize Session States
if "messages" not in st.session_state: st.session_state.messages = []
if "metrics" not in st.session_state: 
    st.session_state.metrics = {"Grammar": 0, "Empathy": 0, "Resolution": 0, "Turns": 0}
if "kb_content" not in st.session_state: st.session_state.kb_content = ""
if "resume_content" not in st.session_state: st.session_state.resume_content = ""

# API Check
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("Missing GROQ_API_KEY. Add it to Streamlit Secrets.")
    st.stop()

# ================= 3. PROMPT & CHARACTER ENGINE =================
def build_system_prompt():
    role = st.session_state.role_mode
    scenario = st.session_state.scenario_text
    level = st.session_state.target_level
    kb = st.session_state.kb_content
    resume = st.session_state.resume_content

    # Determine Persona
    if "AI is Interviewer" in role:
        persona = "You are a Senior Hiring Manager. Use the provided Resume to challenge the user and the Company Info to ask specific cultural questions."
    elif "AI is Applicant" in role:
        persona = "You are a job applicant. Use the Resume as your own background. The user is interviewing you for a role described in the Company Info."
    elif "AI is Customer" in role:
        persona = "You are a customer calling a BPO center. Use the Company Info to present a specific problem. Be realistic: stay in character even if frustrated."
    else: # AI is Agent
        persona = "You are an Elite BPO Agent. Provide perfect support using the provided Company SOPs and Knowledge Base."

    return f"""
    ROLE: {persona}
    SPANISH LEVEL: {level}
    SCENARIO: {scenario}
    
    KNOWLEDGE BASE (CONTEXT): {kb[:3000]} 
    USER RESUME/PROFILE: {resume[:3000]}

    INSTRUCTIONS:
    1. Stay 100% in character in the first part of your response.
    2. Analyze the user's Spanish, tone, and accuracy.
    3. Use the separator '---COACH_DATA---'.

    OUTPUT FORMAT:
    [Character Response in Spanish]
    ---COACH_DATA---
    **Elite Analysis**
    - **Mistakes:** (List any grammar/vocab errors)
    - **Golden Phrase:** (A pro-level Spanish alternative for what the user said)
    - **Metrics:** (Provide a comma-separated score out of 10 for: Grammar, Empathy, Resolution)
    """

def update_metrics(score_string):
    """Parses the score from AI and updates the dashboard."""
    try:
        scores = re.findall(r'\d+', score_string)
        if len(scores) >= 3:
            st.session_state.metrics["Grammar"] += int(scores[0])
            st.session_state.metrics["Empathy"] += int(scores[1])
            st.session_state.metrics["Resolution"] += int(scores[2])
            st.session_state.metrics["Turns"] += 1
    except: pass

# ================= 4. SIDEBAR & FILE MANAGEMENT =================
with st.sidebar:
    st.title("🛡️ Training Command")
    
    st.session_state.role_mode = st.selectbox("Select Roleplay Mode", [
        "User as Applicant (AI is Interviewer)",
        "User as Interviewer (AI is Applicant)",
        "User as Agent (AI is Customer)",
        "User as Customer (AI is Agent)"
    ])
    
    st.session_state.target_level = st.select_slider("Target Proficiency", ["A2", "B1", "B2", "C1", "C2"])
    
    st.session_state.scenario_text = st.text_area("🚩 Define Custom Scenario", 
        placeholder="E.g. Technical support for a broken router, or Final interview for a Team Lead role.")

    st.divider()
    
    # Knowledge Base Upload
    st.subheader("📖 Company Data / SOPs")
    kb_file = st.file_uploader("Upload Product Manuals, HTML site, or SOPs", type=['pdf', 'html', 'txt'])
    if kb_file:
        st.session_state.kb_content = extract_text_from_file(kb_file)
        st.success("KB Loaded!")

    # Resume Upload
    st.subheader("👤 Your Resume / Profile")
    res_file = st.file_uploader("Upload your Resume or the AI's persona bio", type=['pdf', 'html', 'txt'])
    if res_file:
        st.session_state.resume_content = extract_text_from_file(res_file)
        st.success("Resume Loaded!")

    if st.button("🗑️ Reset All Progress"):
        st.session_state.messages = []
        st.session_state.metrics = {"Grammar": 0, "Empathy": 0, "Resolution": 0, "Turns": 0}
        st.rerun()

# ================= 5. DASHBOARD & MAIN UI =================
st.title("🚀 Elite BPO & Interview Simulator")

# Show Metrics Dashboard
if st.session_state.metrics["Turns"] > 0:
    t = st.session_state.metrics["Turns"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Grammar Avg", f"{round(st.session_state.metrics['Grammar']/t, 1)}/10")
    c2.metric("Empathy Avg", f"{round(st.session_state.metrics['Empathy']/t, 1)}/10")
    c3.metric("Goal Progress", f"{round(st.session_state.metrics['Resolution']/t, 1)}/10")

# Display Conversation History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "---COACH_DATA---" in msg["content"]:
            char_text, coach_text = msg["content"].split("---COACH_DATA---")
            st.markdown(char_text)
            with st.expander("📝 Coaching & Professional Feedback"):
                st.markdown(coach_text)
        else:
            st.markdown(msg["content"])

# ================= 6. INPUT & LOGIC =================
user_input = None
audio_in = st.audio_input("Speak in Spanish")
text_in = st.chat_input("Type your response...")

if audio_in:
    with st.spinner("Transcribing..."):
        transcript = client.audio.transcriptions.create(
            file=("audio.wav", audio_in.getvalue()),
            model="whisper-large-v3",
            language="es"
        )
        user_input = transcript.text

if text_in: user_input = text_in

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"): st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing and Responding..."):
            # Construct History (Excluding coach data to avoid AI confusion)
            clean_history = []
            for m in st.session_state.messages[-8:]:
                content = m["content"].split("---COACH_DATA---")[0]
                clean_history.append({"role": m["role"], "content": content})
            
            # AI Request
            chat_completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": build_system_prompt()}] + clean_history
            )
            
            full_reply = chat_completion.choices[0].message.content
            
            if "---COACH_DATA---" in full_reply:
                dialogue, coach = full_reply.split("---COACH_DATA---")
                st.markdown(dialogue.strip())
                
                # Voice Synthesis (Dialogue Only)
                tts = gTTS(text=re.sub(r'[*#_~-]', '', dialogue), lang='es')
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                    tts.save(fp.name)
                    st.audio(fp.name)
                
                with st.expander("📝 Coaching & Professional Feedback"):
                    st.markdown(coach.strip())
                
                update_metrics(coach)
            else:
                st.markdown(full_reply)
            
            st.session_state.messages.append({"role": "assistant", "content": full_reply})
