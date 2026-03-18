import streamlit as st
from groq import Groq
from gtts import gTTS
import tempfile
import re
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup

# ================= 1. UTILS & PARSING =================
def extract_text(uploaded_file):
    if not uploaded_file: return ""
    ext = uploaded_file.name.split('.')[-1].lower()
    try:
        if ext == 'pdf':
            return " ".join([p.extract_text() or "" for p in PdfReader(uploaded_file).pages])
        if ext in ['html', 'htm']:
            return BeautifulSoup(uploaded_file.read(), 'html.parser').get_text()
        return uploaded_file.read().decode("utf-8")
    except Exception as e:
        return f"Error: {e}"

# ================= 2. SETUP & STATE =================
st.set_page_config(page_title="Elite Spanish Coach", layout="wide")

# Critical: Initialize session state keys
if "messages" not in st.session_state: st.session_state.messages = []
if "metrics" not in st.session_state: st.session_state.metrics = {"G": [], "E": [], "R": []}
if "kb" not in st.session_state: st.session_state.kb = ""
if "resume" not in st.session_state: st.session_state.resume = ""
if "processing" not in st.session_state: st.session_state.processing = False

try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("API Key missing.")
    st.stop()

# ================= 3. THE BRAIN (PROMPT) =================
def get_system_prompt():
    role = st.session_state.get('role', 'User as Applicant')
    scenario = st.session_state.get('scenario', 'Job Interview')
    
    # Strictly define who is who
    if "AI is Interviewer" in role:
        persona = f"ACT AS: Professional Recruiter. GOAL: Interview the user for {scenario}. Use their RESUME: {st.session_state.resume[:1500]}."
    elif "AI is Applicant" in role:
        persona = f"ACT AS: Job Applicant named Rod Salmeo (based on this RESUME: {st.session_state.resume[:1500]}). The user is interviewing you for {scenario}."
    elif "AI is Customer" in role:
        persona = f"ACT AS: Angry Customer. Use this Company Data: {st.session_state.kb[:1500]}. The user is a support agent."
    else:
        persona = f"ACT AS: Elite Agent. Use Company Data: {st.session_state.kb[:1500]}. The user is a customer."

    return f"""
    {persona}
    LANGUAGE: Spanish ONLY for dialogue.
    STRICT FORMAT:
    [Character Response]
    ---
    COACH: (Grammar/Vocab feedback)
    SCORES: G: (1-10), E: (1-10), R: (1-10)
    """

# ================= 4. SIDEBAR =================
with st.sidebar:
    st.title("⚙️ Simulation Settings")
    new_role = st.selectbox("Current Mode", [
        "User as Applicant (AI is Interviewer)",
        "User as Interviewer (AI is Applicant)",
        "User as Agent (AI is Customer)",
        "User as Customer (AI is Agent)"
    ])
    
    # If role changes, reset chat to prevent confusion
    if "role" in st.session_state and st.session_state.role != new_role:
        st.session_state.messages = []
        st.session_state.role = new_role
        st.rerun()
    st.session_state.role = new_role

    st.session_state.scenario = st.text_input("Custom Scenario", "General Job Interview")
    
    st.divider()
    kb_up = st.file_uploader("Company SOPs/Details (PDF/HTML)", type=['pdf', 'html', 'txt'])
    if kb_up: st.session_state.kb = extract_text(kb_up)
    
    res_up = st.file_uploader("Your Resume (PDF/HTML)", type=['pdf', 'html', 'txt'])
    if res_up: st.session_state.resume = extract_text(res_up)

    if st.button("Reset Session"):
        st.session_state.messages = []
        st.session_state.metrics = {"G": [], "E": [], "R": []}
        st.rerun()

# ================= 5. MAIN UI =================
st.title("🇪🇸 Elite Spanish Professional Coach")

# Show Score Averages
if st.session_state.metrics["G"]:
    cols = st.columns(3)
    cols[0].metric("Grammar", f"{sum(st.session_state.metrics['G'])/len(st.session_state.metrics['G']):.1f}/10")
    cols[1].metric("Empathy", f"{sum(st.session_state.metrics['E'])/len(st.session_state.metrics['E']):.1f}/10")
    cols[2].metric("Result", f"{sum(st.session_state.metrics['R'])/len(st.session_state.metrics['R']):.1f}/10")

# Render Chat
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        if "---" in m["content"]:
            text, coach = m["content"].split("---")
            st.write(text.strip())
            with st.expander("📝 Coaching"): st.write(coach.strip())
        else:
            st.write(m["content"])

# ================= 6. INPUT LOGIC (THE GATE) =================
# Use a dynamic key based on message count to force-reset the audio widget
audio_key = f"audio_{len(st.session_state.messages)}"
audio_input = st.audio_input("Respond in Spanish", key=audio_key)
text_input = st.chat_input("Type your response...")

user_msg = None

if audio_input and not st.session_state.processing:
    st.session_state.processing = True
    with st.status("Transcribing..."):
        try:
            res = client.audio.transcriptions.create(file=("a.wav", audio_input.getvalue()), model="whisper-large-v3", language="es")
            user_msg = res.text
        except: st.error("Transcription error.")
    st.session_state.processing = False

if text_input:
    user_msg = text_input

# ================= 7. AI RESPONSE =================
if user_msg:
    st.session_state.messages.append({"role": "user", "content": user_msg})
    
    with st.chat_message("assistant"):
        # Create history for AI, cleaning out coaching
        clean_history = [{"role": m["role"], "content": m["content"].split("---")[0]} for m in st.session_state.messages[-6:]]
        
        try:
            # Attempt 70B, fallback to 8B on rate limit
            try:
                model = "llama-3.3-70b-versatile"
                response = client.chat.completions.create(model=model, messages=[{"role": "system", "content": get_system_prompt()}] + clean_history)
            except:
                model = "llama-3.1-8b-instant"
                response = client.chat.completions.create(model=model, messages=[{"role": "system", "content": get_system_prompt()}] + clean_history)
            
            full_res = response.choices[0].message.content
            
            # Display & Parse
            if "---" in full_res:
                txt, coach = full_res.split("---")
                st.write(txt.strip())
                # Audio out
                tts = gTTS(text=re.sub(r'[*#_~-]', '', txt), lang='es')
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                    tts.save(fp.name)
                    st.audio(fp.name)
                with st.expander("📝 Coaching"): st.write(coach.strip())
                
                # Metric Extraction
                scores = re.findall(r'[GER]:\s*(\d+)', coach)
                if len(scores) >= 3:
                    st.session_state.metrics["G"].append(int(scores[0]))
                    st.session_state.metrics["E"].append(int(scores[1]))
                    st.session_state.metrics["R"].append(int(scores[2]))
            else:
                st.write(full_res)
            
            st.session_state.messages.append({"role": "assistant", "content": full_res})
            st.rerun()

        except Exception as e:
            st.error(f"AI Error: {e}")

# ================= 8. INITIAL TRIGGER =================
if not st.session_state.messages:
    # If the user is the applicant, the AI starts the interview
    if "AI is Interviewer" in st.session_state.role:
        start_text = "Hola, bienvenido. He revisado su currículum. Para empezar, ¿por qué le interesa este puesto?"
    # If the user is the agent, the AI customer starts the call
    elif "AI is Customer" in st.session_state.role:
        start_text = "¡Hola! Estoy llamando porque tengo un problema grave con mi servicio y nadie me ayuda."
    # Otherwise, wait for the user to speak
    else:
        start_text = "Llamada conectada. El sistema está listo para que usted comience."
    
    st.session_state.messages.append({"role": "assistant", "content": start_text})
    st.rerun()
