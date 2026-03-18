import streamlit as st
from groq import Groq
from gtts import gTTS
import io
import re
import hashlib
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup

# ================= 1. CORE UTILS =================
def extract_text(files):
    text_out = ""
    if not files: return ""
    for f in files:
        ext = f.name.split('.')[-1].lower()
        text_out += f"\n--- DOC: {f.name} ---\n"
        try:
            if ext == 'pdf':
                reader = PdfReader(f)
                text_out += " ".join([p.extract_text() or "" for p in reader.pages])
            elif ext in ['html', 'htm']:
                text_out += BeautifulSoup(f.read(), 'html.parser').get_text()
            else:
                text_out += f.read().decode("utf-8", errors='ignore')
        except Exception as e:
            text_out += f"[Error: {e}]"
    return text_out

# ================= 2. SETUP & STATE =================
st.set_page_config(page_title="Elite Spanish Coach", layout="wide", page_icon="🇪🇸")

# Initialize session states
if "messages" not in st.session_state: st.session_state.messages = []
if "metrics" not in st.session_state: st.session_state.metrics = {"G": [], "E": [], "R": []}
if "last_processed_id" not in st.session_state: st.session_state.last_processed_id = ""
if "feedback_data" not in st.session_state: st.session_state.feedback_data = {}

try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("GROQ_API_KEY is missing in secrets.")
    st.stop()

# ================= 3. PROMPTS =================

def get_sim_prompt():
    """Focuses purely on character immersion."""
    role = st.session_state.get('role', 'User as Applicant')
    scenario = st.session_state.get('scenario', 'Job Interview')
    context = f"DOCS: {st.session_state.kb_content[:3000]}\nUSER BIO: {st.session_state.res_content[:2000]}"
    
    if "AI is Applicant" in role:
        persona = "ACT AS: Rod Salmeo (Job Applicant). Tone: Professional, slightly nervous but capable."
    elif "AI is Interviewer" in role:
        persona = "ACT AS: Senior Hiring Manager. Tone: Formal, probing, observant."
    elif "AI is Customer" in role:
        persona = "ACT AS: Frustrated but reasonable customer. Tone: Realistic."
    else:
        persona = "ACT AS: Professional Service Agent."

    return f"{persona}\nSCENARIO: {scenario}\nCONTEXT: {context}\nRULE: Respond ONLY in Spanish. Keep it brief and conversational."

def get_coaching_prompt(user_msg, ai_res):
    """Dedicated prompt for high-quality linguistic analysis."""
    return f"""
    Analyze this Spanish professional interaction:
    User said: "{user_msg}"
    AI responded: "{ai_res}"

    Provide feedback in English using this format:
    **Grammar & Vocabulary:** (Specific corrections)
    **Professional Tone:** (How to sound more like a native professional)
    **Key Vocabulary:** (Explain 2-3 advanced words used)
    **Scores:** G: (1-10), E: (1-10), R: (1-10)
    """

# ================= 4. SIDEBAR =================
with st.sidebar:
    st.title("🏆 Coach Settings")
    st.session_state.role = st.selectbox("Current Mode", [
        "User as Interviewer (AI is Applicant)",
        "User as Applicant (AI is Interviewer)",
        "User as Agent (AI is Customer)",
        "User as Customer (AI is Agent)"
    ])
    st.session_state.scenario = st.text_input("Custom Scenario", "Job Interview for Virtual Assistant")
    
    st.divider()
    st.subheader("📂 Upload Context")
    kb_files = st.file_uploader("Company SOPs / Details", accept_multiple_files=True)
    if kb_files: st.session_state.kb_content = extract_text(kb_files)
    else: st.session_state.kb_content = ""
        
    res_files = st.file_uploader("Your Resume / Bio", accept_multiple_files=True)
    if res_files: st.session_state.res_content = extract_text(res_files)
    else: st.session_state.res_content = ""

    if st.button("🗑️ Reset Practice"):
        st.session_state.messages = []
        st.session_state.metrics = {"G": [], "E": [], "R": []}
        st.session_state.feedback_data = {}
        st.rerun()

# ================= 5. COACHING LOGIC =================
def generate_feedback(idx):
    """Triggered when user clicks 'Generate Feedback' on a specific message."""
    user_text = st.session_state.messages[idx-1]["content"]
    ai_text = st.session_state.messages[idx]["content"]
    
    with st.spinner("Analyzing your Spanish..."):
        try:
            res = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": "You are an expert Spanish Business Coach."},
                          {"role": "user", "content": get_coaching_prompt(user_text, ai_text)}]
            )
            feedback = res.choices[0].message.content
            st.session_state.feedback_data[idx] = feedback
            
            # Update Metrics
            scores = re.findall(r'[GER]:\s*(\d+)', feedback)
            if len(scores) >= 3:
                st.session_state.metrics["G"].append(int(scores[0]))
                st.session_state.metrics["E"].append(int(scores[1]))
                st.session_state.metrics["R"].append(int(scores[2]))
        except Exception as e:
            st.error(f"Coaching failed: {e}")

# ================= 6. MAIN UI =================
st.title("🇪🇸 Elite Spanish Professional Coach")

# Metrics Dashboard
if st.session_state.metrics["G"]:
    cols = st.columns(3)
    avg = lambda k: sum(st.session_state.metrics[k])/len(st.session_state.metrics[k])
    cols[0].metric("Grammar", f"{avg('G'):.1f}/10")
    cols[1].metric("Empathy", f"{avg('E'):.1f}/10")
    cols[2].metric("Result", f"{avg('R'):.1f}/10")

# Message Display
for i, m in enumerate(st.session_state.messages):
    with st.chat_message(m["role"]):
        st.write(m["content"])
        
        if "audio" in m:
            st.audio(m["audio"], format="audio/mp3")
        
        # Add feedback button to AI messages (except the very first greeting)
        if m["role"] == "assistant" and i > 0:
            if i in st.session_state.feedback_data:
                st.info(st.session_state.feedback_data[i])
            else:
                if st.button("📝 Get Feedback on this exchange", key=f"feed_{i}"):
                    generate_feedback(i)
                    st.rerun()

# ================= 7. INPUT HANDLING =================
user_input = None
audio_data = st.audio_input("Respond in Spanish")
if audio_data:
    current_id = hashlib.md5(audio_data.getvalue()).hexdigest()
    if current_id != st.session_state.last_processed_id:
        with st.spinner("Transcribing..."):
            res = client.audio.transcriptions.create(file=("f.wav", audio_data.getvalue()), model="whisper-large-v3", language="es")
            user_input = res.text
            st.session_state.last_processed_id = current_id

text_in = st.chat_input("Type your response...")
if text_in: user_input = text_in

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    with st.chat_message("assistant"):
        # We only send text history to the AI (not audio bytes)
        history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-6:]]
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": get_sim_prompt()}] + history
        )
        ans = response.choices[0].message.content
        
        # Audio Generation
        tts = gTTS(text=ans, lang='es')
        audio_buf = io.BytesIO()
        tts.write_to_fp(audio_buf)
        
        st.session_state.messages.append({"role": "assistant", "content": ans, "audio": audio_buf.getvalue()})
        st.rerun()

# Greeting
if not st.session_state.messages:
    greeting = "Hola. ¿En qué puedo ayudarle hoy?" if "Customer" in st.session_state.role else "Hola, mucho gusto. ¿Comenzamos?"
    st.session_state.messages.append({"role": "assistant", "content": greeting})
    st.rerun()
