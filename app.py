import streamlit as st
from groq import Groq
from gtts import gTTS
import tempfile
import os
import re
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup

# ================= 1. ROBUST FILE PROCESSING =================
def extract_text_from_file(uploaded_file):
    if uploaded_file is None: return ""
    ext = uploaded_file.name.split('.')[-1].lower()
    text = ""
    try:
        if ext == 'pdf':
            pdf_reader = PdfReader(uploaded_file)
            for page in pdf_reader.pages:
                text += (page.extract_text() or "") + " "
        elif ext == 'html' or ext == 'htm':
            soup = BeautifulSoup(uploaded_file.read(), 'html.parser')
            text = soup.get_text()
        else:
            text = uploaded_file.read().decode("utf-8")
        
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    except Exception as e:
        st.error(f"Error reading {uploaded_file.name}: {e}")
        return ""

# ================= 2. INITIALIZATION =================
st.set_page_config(page_title="Elite Spanish Pro", page_icon="🎙️", layout="wide")

# Session State Management
if "messages" not in st.session_state: st.session_state.messages = []
if "metrics" not in st.session_state: st.session_state.metrics = {"Grammar": 0, "Empathy": 0, "Resolution": 0, "Turns": 0}
if "kb_content" not in st.session_state: st.session_state.kb_content = ""
if "resume_content" not in st.session_state: st.session_state.resume_content = ""
if "last_processed_input" not in st.session_state: st.session_state.last_processed_input = None

try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("Missing GROQ_API_KEY in Streamlit Secrets.")
    st.stop()

# ================= 3. SYSTEM PROMPT ENGINE =================
def build_system_prompt():
    role = st.session_state.get('role_mode', 'User as Applicant')
    scenario = st.session_state.get('scenario_text', 'General Interview')
    level = st.session_state.get('target_level', 'B2')
    kb = st.session_state.kb_content
    resume = st.session_state.resume_content

    # Enhanced logic to prevent persona inversion
    if "AI is Applicant" in role:
        persona_instructions = f"YOU ARE THE APPLICANT. The user is interviewing you. Your background is: {resume}. Answer questions briefly and professionally."
    elif "AI is Interviewer" in role:
        persona_instructions = f"YOU ARE THE INTERVIEWER. The user is the candidate. Their resume is: {resume}. Use the company info: {kb} to ask questions."
    elif "AI is Customer" in role:
        persona_instructions = f"YOU ARE AN ANGRY/CONFUSED CUSTOMER. The user is an agent. Use this KB: {kb}."
    else:
        persona_instructions = f"YOU ARE AN EXPERT AGENT. The user is a customer. Use this KB: {kb}."

    return f"""
    ### CORE IDENTITY
    {persona_instructions}
    - **LANGUAGE**: Spanish
    - **LEVEL**: {level}
    - **SCENARIO**: {scenario}

    ### DATA
    - **KB**: {kb[:2000]}
    - **RESUME**: {resume[:2000]}

    ### RESPONSE RULE
    Stay in character. After your response, add '---COACH---' and provide:
    1. Feedback on User's Spanish.
    2. Scores out of 10 (Grammar, Empathy, Resolution). Format: 'Scores: G:8, E:9, R:7'
    """

# ================= 4. SIDEBAR =================
with st.sidebar:
    st.title("🛡️ Setup Center")
    role_mode = st.selectbox("Roleplay Mode", [
        "User as Applicant (AI is Interviewer)",
        "User as Interviewer (AI is Applicant)",
        "User as Agent (AI is Customer)",
        "User as Customer (AI is Agent)"
    ], key="role_mode")
    
    st.session_state.target_level = st.select_slider("Target Level", ["A2", "B1", "B2", "C1", "C2"])
    st.session_state.scenario_text = st.text_area("Define Scenario", "Job interview for a Virtual Assistant.")

    st.divider()
    kb_file = st.file_uploader("Upload Company Info (PDF/HTML)", type=['pdf', 'html', 'txt'])
    if kb_file: st.session_state.kb_content = extract_text_from_file(kb_file)

    res_file = st.file_uploader("Upload Resume (PDF/HTML)", type=['pdf', 'html', 'txt'])
    if res_file: st.session_state.resume_content = extract_text_from_file(res_file)

    if st.button("Reset Session"):
        st.session_state.messages = []
        st.session_state.metrics = {"Grammar": 0, "Empathy": 0, "Resolution": 0, "Turns": 0}
        st.session_state.last_processed_input = None
        st.rerun()

# ================= 5. MAIN CHAT LOGIC =================
st.title("🚀 Elite BPO & Interview Coach")

# Dashboard
if st.session_state.metrics["Turns"] > 0:
    t = st.session_state.metrics["Turns"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Grammar", f"{round(st.session_state.metrics['Grammar']/t, 1)}/10")
    c2.metric("Empathy", f"{round(st.session_state.metrics['Empathy']/t, 1)}/10")
    c3.metric("Goal", f"{round(st.session_state.metrics['Resolution']/t, 1)}/10")

# History Display
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "---COACH---" in msg["content"]:
            txt, coach = msg["content"].split("---COACH---")
            st.markdown(txt.strip())
            with st.expander("📝 Elite Coaching"): st.markdown(coach.strip())
        else:
            st.markdown(msg["content"])

# --- INPUT HANDLING ---
user_input = None
# Unique keys prevent double-triggering
audio_val = st.audio_input("Respond via Voice", key=f"audio_in_{len(st.session_state.messages)}")
text_val = st.chat_input("Type your response...")

if audio_val and audio_val != st.session_state.last_processed_input:
    with st.spinner("Transcribing..."):
        try:
            transcript = client.audio.transcriptions.create(
                file=("audio.wav", audio_val.getvalue()),
                model="whisper-large-v3", language="es"
            )
            user_input = transcript.text
            st.session_state.last_processed_input = audio_val # Lock this input
        except: st.error("Transcription failed.")

if text_val:
    user_input = text_val

# --- AI RESPONSE GENERATION ---
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"): st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("AI is thinking..."):
            history = [{"role": m["role"], "content": m["content"].split("---COACH---")[0]} for m in st.session_state.messages[-6:]]
            
            full_reply = ""
            for model_name in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
                try:
                    res = client.chat.completions.create(
                        model=model_name,
                        messages=[{"role": "system", "content": build_system_prompt()}] + history
                    )
                    full_reply = res.choices[0].message.content
                    break
                except Exception as e:
                    if "rate_limit" in str(e).lower(): continue
                    st.error(f"Error: {e}"); st.stop()

            # Process Output
            if "---COACH---" in full_reply:
                dialogue, coach = full_reply.split("---COACH---")
                st.markdown(dialogue.strip())
                
                # Audio Synthesis
                try:
                    tts = gTTS(text=re.sub(r'[*#_~-]', '', dialogue), lang='es')
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                        tts.save(fp.name); st.audio(fp.name)
                except: pass
                
                with st.expander("📝 Elite Coaching"): st.markdown(coach.strip())
                
                # Score parsing
                scores = re.findall(r'\d+', coach)
                if len(scores) >= 3:
                    st.session_state.metrics["Grammar"] += int(scores[0])
                    st.session_state.metrics["Empathy"] += int(scores[1])
                    st.session_state.metrics["Resolution"] += int(scores[2])
                    st.session_state.metrics["Turns"] += 1
            else:
                st.markdown(full_reply)
            
            st.session_state.messages.append({"role": "assistant", "content": full_reply})
            st.rerun()

# Initial Prompting
if not st.session_state.messages:
    if "AI is Interviewer" in role_mode:
        init_msg = "Hola. Gracias por venir hoy. He revisado su currículum. ¿Podría empezar hablándome un poco sobre usted?"
        st.session_state.messages.append({"role": "assistant", "content": init_msg})
        st.rerun()
    elif "AI is Customer" in role_mode:
        init_msg = "*(El teléfono suena)* ¡Hola! Necesito ayuda con mi cuenta ahora mismo, estoy muy frustrado."
        st.session_state.messages.append({"role": "assistant", "content": init_msg})
        st.rerun()
