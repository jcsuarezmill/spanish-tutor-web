import streamlit as st
from groq import Groq
from gtts import gTTS
import tempfile
import re
import io
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
st.set_page_config(page_title="Elite Spanish Coach", layout="wide", page_icon="🇪🇸")

# Professional Styling
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #4e5d6c; }
    .coach-box { background-color: #262730; border-left: 5px solid #ff4b4b; padding: 15px; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

if "messages" not in st.session_state: st.session_state.messages = []
if "metrics" not in st.session_state: st.session_state.metrics = {"G": [], "E": [], "R": []}
if "kb" not in st.session_state: st.session_state.kb = ""
if "resume" not in st.session_state: st.session_state.resume = ""
if "processing" not in st.session_state: st.session_state.processing = False

try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("⚠️ Groq API Key missing in secrets.")
    st.stop()

# ================= 3. THE BRAIN (ENHANCED PROMPT) =================
def get_system_prompt():
    role = st.session_state.get('role', 'User as Applicant')
    scenario = st.session_state.get('scenario', 'Job Interview')
    
    # Specific Persona Logic
    if "AI is Interviewer" in role:
        persona = f"ACT AS: A high-level Executive Recruiter. SCENARIO: Interviewing user for {scenario}. USE RESUME: {st.session_state.resume[:2000]}."
    elif "AI is Applicant" in role:
        persona = f"ACT AS: A job candidate named Rod Salmeo. USE BACKGROUND: {st.session_state.resume[:2000]}. User is the Interviewer for {scenario}."
    elif "AI is Customer" in role:
        persona = f"ACT AS: A frustrated but professional customer using this knowledge base: {st.session_state.kb[:2000]}. User is Support Agent."
    else:
        persona = f"ACT AS: Elite Customer Success Agent. USE SOP: {st.session_state.kb[:2000]}. User is the customer."

    return f"""
    {persona}
    LANGUAGE: Spanish ONLY for dialogue. English/Spanish mix for COACH section.
    
    TASK:
    1. Respond naturally to the user's last statement in Spanish.
    2. Provide a "COACH" section correcting specific Spanish grammar, word choice, or cultural nuances.
    3. Provide numeric scores (1-10) for Grammar (G), Empathy (E), and Professional Result (R).

    STRICT FORMAT:
    [Character Response in Spanish]
    ---
    COACH: (Brief feedback on their Spanish and professional tone)
    SCORES: G: (1-10), E: (1-10), R: (1-10)
    """

# ================= 4. SIDEBAR =================
with st.sidebar:
    st.title("🏆 Coach Settings")
    new_role = st.selectbox("Simulation Mode", [
        "User as Applicant (AI is Interviewer)",
        "User as Interviewer (AI is Applicant)",
        "User as Agent (AI is Customer)",
        "User as Customer (AI is Agent)"
    ])
    
    if "role" in st.session_state and st.session_state.role != new_role:
        st.session_state.messages = []
        st.session_state.metrics = {"G": [], "E": [], "R": []}
        st.session_state.role = new_role
        st.rerun()
    st.session_state.role = new_role

    st.session_state.scenario = st.text_input("Context/Scenario", "General Business Discussion")
    
    with st.expander("📂 Context Documents", expanded=True):
        kb_up = st.file_uploader("Upload Company Data/SOP", type=['pdf', 'html', 'txt'])
        if kb_up: st.session_state.kb = extract_text(kb_up)
        
        res_up = st.file_uploader("Upload Resume/Profile", type=['pdf', 'html', 'txt'])
        if res_up: st.session_state.resume = extract_text(res_up)

    if st.button("🗑️ Reset All Progress", use_container_width=True):
        st.session_state.messages = []
        st.session_state.metrics = {"G": [], "E": [], "R": []}
        st.rerun()

# ================= 5. MAIN UI & DASHBOARD =================
st.title("🇪🇸 Elite Spanish Professional Coach")

# Visual Score Dashboard
if st.session_state.metrics["G"]:
    avg_g = sum(st.session_state.metrics['G'])/len(st.session_state.metrics['G'])
    avg_e = sum(st.session_state.metrics['E'])/len(st.session_state.metrics['E'])
    avg_r = sum(st.session_state.metrics['R'])/len(st.session_state.metrics['R'])
    
    m_cols = st.columns(3)
    m_cols[0].metric("Grammar Accuracy", f"{avg_g:.1f}/10")
    m_cols[0].progress(avg_g/10)
    m_cols[1].metric("Professional Empathy", f"{avg_e:.1f}/10")
    m_cols[1].progress(avg_e/10)
    m_cols[2].metric("Business Result", f"{avg_r:.1f}/10")
    m_cols[2].progress(avg_r/10)
    st.divider()

# Render Chat
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        if "---" in m["content"]:
            text, coach = m["content"].split("---")
            st.markdown(f"#### {text.strip()}")
            with st.expander("📝 Coaching & Corrections"):
                st.markdown(f"<div class='coach-box'>{coach.strip()}</div>", unsafe_allow_html=True)
        else:
            st.write(m["content"])

# ================= 6. INPUT LOGIC =================
audio_key = f"audio_{len(st.session_state.messages)}"
c1, c2 = st.columns([1, 4])
with c1:
    audio_input = st.audio_input("🎤 Voice", key=audio_key)
with c2:
    text_input = st.chat_input("Type your response in Spanish...")

user_msg = None
if audio_input and not st.session_state.processing:
    st.session_state.processing = True
    with st.spinner("Transcribing Spanish..."):
        try:
            # Use Whisper-3 for high accuracy Spanish transcription
            res = client.audio.transcriptions.create(
                file=("a.wav", audio_input.getvalue()), 
                model="whisper-large-v3", 
                language="es"
            )
            user_msg = res.text
        except Exception as e:
            st.error(f"Transcription error: {e}")
    st.session_state.processing = False

if text_input:
    user_msg = text_input

# ================= 7. AI RESPONSE ENGINE =================
if user_msg:
    st.session_state.messages.append({"role": "user", "content": user_msg})
    
    with st.chat_message("assistant"):
        # Create sliding window history (last 8 messages) to keep context without hitting token limits
        clean_history = [{"role": m["role"], "content": m["content"].split("---")[0]} for m in st.session_state.messages[-8:]]
        
        with st.spinner("Analizando y respondiendo..."):
            try:
                # Main Model logic
                try:
                    model_name = "llama-3.3-70b-versatile"
                    response = client.chat.completions.create(
                        model=model_name, 
                        messages=[{"role": "system", "content": get_system_prompt()}] + clean_history,
                        temperature=0.7
                    )
                except:
                    model_name = "llama-3.1-8b-instant"
                    response = client.chat.completions.create(
                        model=model_name, 
                        messages=[{"role": "system", "content": get_system_prompt()}] + clean_history
                    )
                
                full_res = response.choices[0].message.content
                
                if "---" in full_res:
                    txt, coach = full_res.split("---")
                    st.markdown(f"#### {txt.strip()}")
                    
                    # Optimized Audio Generation
                    tts = gTTS(text=re.sub(r'[*#_~-]', '', txt), lang='es', slow=False)
                    audio_fp = io.BytesIO()
                    tts.write_to_fp(audio_fp)
                    st.audio(audio_fp, format="audio/mp3")
                    
                    with st.expander("📝 Coaching & Corrections", expanded=True):
                        st.markdown(f"<div class='coach-box'>{coach.strip()}</div>", unsafe_allow_html=True)
                    
                    # Enhanced Metric Extraction (Handles "G: 8/10" or "G:8")
                    g_score = re.search(r'G:\s*(\d+)', coach)
                    e_score = re.search(r'E:\s*(\d+)', coach)
                    r_score = re.search(r'R:\s*(\d+)', coach)
                    
                    if g_score: st.session_state.metrics["G"].append(int(g_score.group(1)))
                    if e_score: st.session_state.metrics["E"].append(int(e_score.group(1)))
                    if r_score: st.session_state.metrics["R"].append(int(r_score.group(1)))
                else:
                    st.write(full_res)
                
                st.session_state.messages.append({"role": "assistant", "content": full_res})
                st.rerun()

            except Exception as e:
                st.error(f"AI Error: {e}")

# ================= 8. SESSION INITIALIZER =================
if not st.session_state.messages:
    init_msg = ""
    if "AI is Interviewer" in st.session_state.role:
        init_msg = "Hola. Gracias por venir. He revisado su perfil profesional y me gustaría comenzar. ¿Cómo describiría su mayor logro en su último trabajo?"
    elif "AI is Customer" in st.session_state.role:
        init_msg = "¡Oiga! He estado esperando una respuesta por horas. Mi sistema no funciona y esto me está costando dinero. ¿Qué va a hacer usted?"
    else:
        init_msg = "Conexión establecida. Estoy listo para la simulación. Puede comenzar cuando guste."
    
    st.session_state.messages.append({"role": "assistant", "content": init_msg})
    st.rerun()
