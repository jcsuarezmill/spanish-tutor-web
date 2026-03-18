import streamlit as st
from groq import Groq
from gtts import gTTS
import tempfile
import re

# ================= 1. CONFIG & UI =================
st.set_page_config(page_title="Coach AI: BPO & Interview", layout="wide")

# Custom CSS for better chat bubbles and status
st.markdown("""
    <style>
    .reportview-container { background: #f0f2f6; }
    .stChatMessage { border-radius: 10px; border: 1px solid #ddd; }
    .feedback-box { background-color: #f9f9f9; border-left: 5px solid #4CAF50; padding: 10px; margin-top: 10px; font-size: 0.9em; }
    .score-tag { font-weight: bold; color: #1565c0; }
    </style>
""", unsafe_allow_html=True)

# API Initialization
if "GROQ_API_KEY" in st.secrets:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
else:
    st.error("Missing GROQ_API_KEY in secrets.")
    st.stop()

# ================= 2. SESSION STATE =================
if "messages" not in st.session_state: st.session_state.messages = []
if "session_id" not in st.session_state: st.session_state.session_id = 0

# ================= 3. LOGIC ENGINES =================

def generate_system_prompt():
    """Dynamically builds the prompt based on the chosen role."""
    role_mode = st.session_state.get('role_mode', 'User as Applicant')
    kb = st.session_state.get('kb_data', '')
    resume = st.session_state.get('resume_data', '')
    level = st.session_state.get('target_level', 'B2')
    
    base_instructions = f"Act strictly according to the role. Language: Spanish. Proficiency Level: {level}."
    
    if role_mode == "User as Interviewee (AI is Interviewer)":
        persona = f"You are a Hiring Manager. Use this Company Info: {kb}. Interview the user based on their Resume: {resume}. Be professional, challenging, and stay in character."
    elif role_mode == "User as Interviewer (AI is Applicant)":
        persona = f"You are a candidate applying for a job. Your resume/experience is: {resume}. The company you are applying to is: {kb}. Answer the interviewer's questions naturally, occasionally making small mistakes typical of a {level} level student for the coach to correct."
    elif role_mode == "User as Agent (AI is Customer)":
        persona = f"You are a customer calling a BPO center. Company SOPs: {kb}. Be realistic, sometimes frustrated, but stay focused on the scenario."
    else: # User as Customer (AI is Agent)
        persona = f"You are an Elite BPO Agent. Use these SOPs: {kb}. Provide perfect service."

    return f"""
    SYSTEM PERSONA: {persona}
    CONTEXT: {base_instructions}
    
    IMPORTANT: Your response MUST be in two parts separated by '---FEEDBACK---'.
    Part 1: The direct Spanish response in character.
    Part 2: A short analysis of the USER'S last message (Grammar, Vocabulary, and a 'Golden Phrase' in Spanish).
    """

def get_clean_history():
    """Filters out coaching feedback so the AI memory isn't cluttered."""
    clean = []
    for m in st.session_state.messages[-6:]: # Last 6 messages for context
        content = m["content"]
        if "---FEEDBACK---" in content:
            content = content.split("---FEEDBACK---")[0]
        clean.append({"role": m["role"], "content": content})
    return clean

# ================= 4. SIDEBAR & TOOLS =================
with st.sidebar:
    st.header("🛠️ Simulation Settings")
    
    st.session_state.role_mode = st.selectbox("Roleplay Mode", [
        "User as Interviewee (AI is Interviewer)",
        "User as Interviewer (AI is Applicant)",
        "User as Agent (AI is Customer)",
        "User as Customer (AI is Agent)"
    ])
    
    st.session_state.target_level = st.select_slider("Target Spanish Level", ["A2", "B1", "B2", "C1"])
    
    st.divider()
    st.subheader("📄 Knowledge Injection")
    st.session_state.kb_data = st.text_area("Company Details / Job Description", placeholder="Paste company info or product details...")
    st.session_state.resume_data = st.text_area("Your Resume / Candidate Bio", placeholder="Paste your resume or the AI's persona bio...")

    if st.button("Clear Session"):
        st.session_state.messages = []
        st.rerun()

# ================= 5. CHAT INTERFACE =================
st.title("🚀 Elite BPO & Interview Coach")
st.info(f"Current Mode: {st.session_state.role_mode} | Level: {st.session_state.target_level}")

# Display Chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "---FEEDBACK---" in msg["content"]:
            text, feedback = msg["content"].split("---FEEDBACK---")
            st.write(text.strip())
            with st.expander("📝 Coaching & Feedback"):
                st.markdown(feedback.strip())
        else:
            st.write(msg["content"])

# Input Handling
user_input = None
audio_input = st.audio_input("Respond in Spanish")
text_input = st.chat_input("Type your response...")

if audio_input:
    with st.spinner("Transcribing..."):
        transcript = client.audio.transcriptions.create(
            file=("audio.wav", audio_input.getvalue()),
            model="whisper-large-v3",
            language="es"
        )
        user_input = transcript.text

if text_input:
    user_input = text_input

# ================= 6. RESPONSE GENERATION =================
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"): st.write(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": generate_system_prompt()}] + get_clean_history() + [{"role": "user", "content": user_input}]
            )
            full_res = response.choices[0].message.content
            
            if "---FEEDBACK---" in full_res:
                ans_text, ans_feedback = full_res.split("---FEEDBACK---")
                st.write(ans_text.strip())
                
                # TTS for dialogue only
                tts = gTTS(text=ans_text.strip(), lang='es')
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                    tts.save(fp.name)
                    st.audio(fp.name)
                
                with st.expander("📝 Coaching & Feedback"):
                    st.markdown(ans_feedback.strip())
            else:
                st.write(full_res)
            
            st.session_state.messages.append({"role": "assistant", "content": full_res})
