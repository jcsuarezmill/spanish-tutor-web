import streamlit as st
from groq import Groq
from gtts import gTTS
import io
import re
import hashlib
import time
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup

# ================= 1. THE ENGINE: DATA & UTILS =================
@st.cache_data(show_spinner=False)
def extract_text_from_docs(files):
    """Processes multiple files into a structured context string."""
    text_out = ""
    for f in files:
        name = f.name
        ext = name.split('.')[-1].lower()
        text_out += f"\n--- DOCUMENT START: {name} ---\n"
        try:
            if ext == 'pdf':
                reader = PdfReader(f)
                text_out += " ".join([p.extract_text() or "" for p in reader.pages])
            elif ext in ['html', 'htm']:
                text_out += BeautifulSoup(f.read(), 'html.parser').get_text()
            else:
                text_out += f.read().decode("utf-8", errors='ignore')
        except Exception as e:
            text_out += f"[Error processing {name}: {e}]"
        text_out += f"\n--- DOCUMENT END: {name} ---\n"
    return text_out

# ================= 2. SETUP & DESIGN =================
st.set_page_config(page_title="Elite Spanish Coach Pro", layout="wide", page_icon="🏆")

# Custom Professional Theme
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    html, body, [class*="st-"] { font-family: 'Inter', sans-serif; }
    .stMetric { background: #1e2130; padding: 15px; border-radius: 12px; border: 1px solid #3e445e; }
    .chat-row { padding: 20px; border-radius: 15px; margin-bottom: 15px; border: 1px solid #2e324a; }
    .coach-card { background: linear-gradient(135deg, #161b22 0%, #0d1117 100%); border-left: 4px solid #00d4ff; padding: 20px; border-radius: 8px; margin-top: 10px; }
    .sim-header { color: #00d4ff; font-weight: 600; font-size: 1.1rem; margin-bottom: 8px; display: flex; align-items: center; }
    .stAudio { margin-top: 10px; width: 50% !important; }
    </style>
    """, unsafe_allow_html=True)

# Session Initialization
if "messages" not in st.session_state: st.session_state.messages = []
if "metrics" not in st.session_state: st.session_state.metrics = {"G": [], "E": [], "R": []}
if "last_audio_hash" not in st.session_state: st.session_state.last_processed_hash = ""

try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("API Key missing in Streamlit Secrets.")
    st.stop()

# ================= 3. SYSTEM PROMPT (THE BRAIN) =================
def build_elite_prompt():
    role = st.session_state.get('role', 'User as Interviewer')
    scenario = st.session_state.get('scenario', 'Business Meeting')
    kb = st.session_state.get('kb_content', "")[:12000] # Increased context
    res = st.session_state.get('res_content', "")[:12000]

    # Persona Logic
    if "AI is Applicant" in role:
        persona = f"ACT AS: Rod Salmeo, a Job Applicant. PERSONALITY: Professional, Bilingual, Tech-savvy. BACKGROUND: {res}. CONTEXT: {kb}."
    elif "AI is Interviewer" in role:
        persona = f"ACT AS: Executive Recruiter. BEHAVIOR: Probing, Professional, Neutral. CONTEXT: {kb}."
    elif "AI is Customer" in role:
        persona = f"ACT AS: Frustrated Customer. BEHAVIOR: Impatient but articulate. CONTEXT: {kb}."
    else:
        persona = f"ACT AS: Elite Support Specialist. BEHAVIOR: Calm, Empathetic, Efficient. CONTEXT: {kb}."

    return f"""
    {persona}
    SCENARIO: {scenario}
    
    INSTRUCTIONS:
    1. Respond naturally in Spanish dialogue first.
    2. Provide an Elite Coaching block. If the user is an interviewer, coach them on their Spanish questions. If the user is an applicant, coach them on their Spanish answers.
    
    STRICT TAG FORMAT:
    <SIM>
    [Spanish character dialogue only]
    </SIM>
    
    <COACH>
    **Spanish Feedback:** (Correct grammar, specific Anglicisms, and tone)
    **Cultural/Professional Note:** (Nuances of 'Usted' vs 'Tú' or industry terms)
    **Strategy Insight:** (Why the AI chose its specific response)
    **Scores:** G: [score]/10, E: [score]/10, R: [score]/10
    </COACH>
    """

# ================= 4. SIDEBAR SETTINGS =================
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/spanish-flag.png", width=60)
    st.title("Elite Prep Console")
    
    st.session_state.role = st.selectbox("Interaction Mode", [
        "User as Interviewer (AI is Applicant)",
        "User as Applicant (AI is Interviewer)",
        "User as Agent (AI is Customer)",
        "User as Customer (AI is Agent)"
    ])
    
    st.session_state.scenario = st.text_input("Current Scenario", "Job Interview for VA Role")
    
    st.divider()
    st.subheader("📚 Knowledge & Background")
    kb_files = st.file_uploader("Upload Company/Job Specs", accept_multiple_files=True)
    if kb_files: st.session_state.kb_content = extract_text_from_docs(kb_files)
    
    res_files = st.file_uploader("Upload Your Resume/Profile", accept_multiple_files=True)
    if res_files: st.session_state.res_content = extract_text_from_docs(res_files)

    if st.button("🗑️ Reset Session", use_container_width=True):
        st.session_state.messages = []
        st.session_state.metrics = {"G": [], "E": [], "R": []}
        st.session_state.last_processed_hash = ""
        st.rerun()

# ================= 5. DASHBOARD & HISTORY =================
st.title("🇪🇸 Elite Spanish Professional Coach")

# Score Tracker
if st.session_state.metrics["G"]:
    c1, c2, c3 = st.columns(3)
    avg = lambda k: sum(st.session_state.metrics[k])/len(st.session_state.metrics[k])
    c1.metric("Spanish Accuracy", f"{avg('G'):.1f}/10")
    c2.metric("Professional Tone", f"{avg('E'):.1f}/10")
    c3.metric("Business Outcome", f"{avg('R'):.1f}/10")
    st.divider()

# Message Display
for i, m in enumerate(st.session_state.messages):
    with st.chat_message(m["role"]):
        if "<SIM>" in m["content"]:
            sim = re.search(r'<SIM>(.*?)</SIM>', m["content"], re.DOTALL).group(1).strip()
            coach = re.search(r'<COACH>(.*?)</COACH>', m["content"], re.DOTALL).group(1).strip()
            
            st.markdown(f"**{sim}**")
            
            # Persistent Audio tied to message object
            if "audio_bytes" in m:
                st.audio(m["audio_bytes"], format="audio/mp3")
            
            with st.expander("📝 Coaching & Analysis", expanded=(i == len(st.session_state.messages)-1)):
                st.markdown(f"<div class='coach-card'>{coach}</div>", unsafe_allow_html=True)
        else:
            st.write(m["content"])

# ================= 6. INPUT PROCESSING (VOICE/TEXT) =================
user_msg = None

# Voice Input with hash check to prevent loops
audio_input = st.audio_input("Respond in Spanish (Voice)")
if audio_input:
    v_hash = hashlib.md5(audio_input.getvalue()).hexdigest()
    if v_hash != st.session_state.last_processed_hash:
        with st.status("Transcribing..."):
            try:
                res = client.audio.transcriptions.create(
                    file=("file.wav", audio_input.getvalue()),
                    model="whisper-large-v3",
                    language="es",
                    temperature=0.0
                )
                user_msg = res.text
                st.session_state.last_processed_hash = v_hash
            except Exception as e:
                st.error(f"Transcription failed: {e}")

# Text Fallback
text_input = st.chat_input("Type your response here...")
if text_input: user_msg = text_input

# ================= 7. AI RESPONSE GENERATION =================
if user_msg:
    st.session_state.messages.append({"role": "user", "content": user_msg})
    
    with st.chat_message("assistant"):
        # Strip tags for history context
        history = []
        for m in st.session_state.messages[-10:]:
            match = re.search(r'<SIM>(.*?)</SIM>', m["content"], re.DOTALL)
            history.append({"role": m["role"], "content": match.group(1) if match else m["content"]})
        
        with st.spinner("Analyzing and Responding..."):
            try:
                # 70B for Elite Reasoning, fallback to 8B
                try:
                    chat_resp = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "system", "content": build_elite_prompt()}] + history,
                        temperature=0.7
                    )
                except:
                    chat_resp = client.chat.completions.create(
                        model="llama-3.1-8b-instant",
                        messages=[{"role": "system", "content": build_elite_prompt()}] + history
                    )
                
                full_raw = chat_resp.choices[0].message.content
                
                # Parse
                sim_part = re.search(r'<SIM>(.*?)</SIM>', full_raw, re.DOTALL).group(1).strip()
                coach_part = re.search(r'<COACH>(.*?)</COACH>', full_raw, re.DOTALL).group(1).strip()
                
                # TTS
                tts = gTTS(text=re.sub(r'[*#_~-]', '', sim_part), lang='es')
                audio_buf = io.BytesIO()
                tts.write_to_fp(audio_buf)
                audio_bytes = audio_buf.getvalue()
                
                # Display
                st.markdown(f"**{sim_part}**")
                st.audio(audio_bytes, format="audio/mp3")
                with st.expander("📝 Coaching & Analysis", expanded=True):
                    st.markdown(f"<div class='coach-card'>{coach_part}</div>", unsafe_allow_html=True)
                
                # Metric Extraction
                scores = re.findall(r'(\d+)/10', coach_part)
                if len(scores) >= 3:
                    st.session_state.metrics["G"].append(int(scores[0]))
                    st.session_state.metrics["E"].append(int(scores[1]))
                    st.session_state.metrics["R"].append(int(scores[2]))
                
                # Save to State
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": full_raw, 
                    "audio_bytes": audio_bytes
                })
                
                st.rerun()
                
            except Exception as e:
                st.error(f"Error in Simulation: {e}")

# ================= 8. STARTUP LOGIC =================
if not st.session_state.messages:
    if "AI is Applicant" in st.session_state.role:
        start = "<SIM>Hola, mucho gusto. Es un placer estar aquí para la entrevista. Estoy listo cuando usted guste.</SIM><COACH>Interviewer: Ask the applicant to introduce themselves.</COACH>"
    elif "AI is Interviewer" in st.session_state.role:
        start = "<SIM>Hola, bienvenido. He revisado su perfil profesional. Para empezar, ¿podría decirme por qué le interesa este puesto?</SIM><COACH>Applicant: Introduce yourself using professional Spanish.</COACH>"
    else:
        start = "<SIM>Hola, gracias por llamar. ¿En qué puedo asistirle el día de hoy?</SIM><COACH>State your problem clearly in Spanish.</COACH>"
    
    st.session_state.messages.append({"role": "assistant", "content": start})
    st.rerun()
