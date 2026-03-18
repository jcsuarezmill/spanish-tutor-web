import streamlit as st
from groq import Groq
from gtts import gTTS
import io
import re
import hashlib
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup

# ================= 1. ADVANCED TEXT EXTRACTION =================
@st.cache_data
def process_files(uploaded_files):
    combined_text = ""
    if not uploaded_files: return ""
    for uploaded_file in uploaded_files:
        ext = uploaded_file.name.split('.')[-1].lower()
        combined_text += f"\n\n--- INICIO DE DOCUMENTO: {uploaded_file.name} ---\n"
        try:
            if ext == 'pdf':
                reader = PdfReader(uploaded_file)
                combined_text += " ".join([p.extract_text() or "" for p in reader.pages])
            elif ext in ['html', 'htm']:
                combined_text += BeautifulSoup(uploaded_file.read(), 'html.parser').get_text()
            else:
                combined_text += uploaded_file.read().decode("utf-8")
        except Exception as e:
            combined_text += f"[Error leyendo archivo: {e}]"
        combined_text += f"\n--- FIN DE DOCUMENTO: {uploaded_file.name} ---\n"
    return combined_text

# ================= 2. SETUP & STYLING =================
st.set_page_config(page_title="Elite Spanish Coach Pro", layout="wide", page_icon="🇪🇸")

# Professional UI Tweak
st.markdown("""
    <style>
    .stChatMessage { border-radius: 15px; margin-bottom: 10px; border: 1px solid #303030; }
    .coach-box { background-color: #1a1c23; padding: 20px; border-radius: 10px; border-left: 5px solid #00ffcc; }
    .sim-text { font-size: 1.2rem !important; font-weight: 500; color: #ffffff; }
    </style>
    """, unsafe_allow_html=True)

# Initialize Session State
if "messages" not in st.session_state: st.session_state.messages = []
if "metrics" not in st.session_state: st.session_state.metrics = {"G": [], "E": [], "R": []}
if "audio_cache" not in st.session_state: st.session_state.audio_cache = {}
if "last_processed_audio" not in st.session_state: st.session_state.last_processed_audio = ""

try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("Missing GROQ_API_KEY in Secrets.")
    st.stop()

# ================= 3. SYSTEM BRAIN (PROMPT) =================
def get_system_prompt():
    role_mode = st.session_state.get('role', 'User as Interviewer (AI is Applicant)')
    scenario = st.session_state.get('scenario', 'General Interview')
    
    # Large context window for unlimited files
    kb = st.session_state.get('kb_content', "")[:10000]
    resume = st.session_state.get('res_content', "")[:10000]
    
    # Persona Selection
    if "AI is Applicant" in role_mode:
        persona = f"ACT AS: Rod Salmeo (Job Applicant). BACKGROUND: {resume}. CONTEXT: {kb}."
    elif "AI is Interviewer" in role_mode:
        persona = f"ACT AS: Senior Recruiter. CONTEXT: {kb}. USER PROFILE: {resume}."
    elif "AI is Customer" in role_mode:
        persona = f"ACT AS: Frustrated Customer. CONTEXT: {kb}."
    else:
        persona = f"ACT AS: Elite Support Agent. CONTEXT: {kb}."

    return f"""
    {persona}
    SCENARIO: {scenario}
    LANGUAGE: Professional Spanish.
    
    TASK:
    1. Respond naturally in character. 
    2. After your response, provide an ELITE coaching breakdown.
    
    STRICT FORMAT (Use these tags):
    <SIM>
    [Your response in character, Spanish only]
    </SIM>
    
    <COACH>
    **Análisis de tu respuesta:** (Detailed feedback on User's grammar, tone, and 'False Cognates')
    **Estrategia IA:** (Why I used specific professional phrases in my SIM response)
    **Vocabulario Elite:** (3-5 advanced terms to memorize)
    **Puntuación:** G: (1-10), E: (1-10), R: (1-10)
    </COACH>
    """

# ================= 4. SIDEBAR =================
with st.sidebar:
    st.title("🏆 Elite Dashboard")
    st.session_state.role = st.selectbox("Current Mode", [
        "User as Interviewer (AI is Applicant)",
        "User as Applicant (AI is Interviewer)",
        "User as Agent (AI is Customer)",
        "User as Customer (AI is Agent)"
    ])
    st.session_state.scenario = st.text_input("Scenario Context", "Professional Interaction")
    
    st.divider()
    with st.expander("📚 Context Documents", expanded=True):
        kb_files = st.file_uploader("Company SOPs / Manuals", accept_multiple_files=True)
        if kb_files: st.session_state.kb_content = process_files(kb_files)
        
        res_files = st.file_uploader("Your Resume / Background", accept_multiple_files=True)
        if res_files: st.session_state.res_content = process_files(res_files)

    if st.button("🗑️ Reset All Data", use_container_width=True):
        st.session_state.messages = []
        st.session_state.metrics = {"G": [], "E": [], "R": []}
        st.session_state.audio_cache = {}
        st.rerun()

# ================= 5. MAIN UI & DASHBOARD =================
st.title("🇪🇸 Elite Spanish Professional Coach")

if st.session_state.metrics["G"]:
    m1, m2, m3 = st.columns(3)
    avg = lambda k: sum(st.session_state.metrics[k])/len(st.session_state.metrics[k])
    m1.metric("Grammar", f"{avg('G'):.1f}/10")
    m2.metric("Empathy", f"{avg('E'):.1f}/10")
    m3.metric("Goal Result", f"{avg('R'):.1f}/10")
    st.divider()

# ================= 6. CHAT DISPLAY LOGIC =================
for i, m in enumerate(st.session_state.messages):
    with st.chat_message(m["role"]):
        content = m["content"]
        
        # Regex to find tags
        sim_match = re.search(r'<SIM>(.*?)</SIM>', content, re.DOTALL)
        coach_match = re.search(r'<COACH>(.*?)</COACH>', content, re.DOTALL)
        
        if sim_match:
            sim_text = sim_match.group(1).strip()
            st.markdown(f"<div class='sim-text'>{sim_text}</div>", unsafe_allow_html=True)
            
            # Show Audio if cached
            msg_id = f"audio_{i}"
            if msg_id in st.session_state.audio_cache:
                st.audio(st.session_state.audio_cache[msg_id], format="audio/mp3")
            
            if coach_match:
                with st.expander("📝 Elite Coaching & Analysis", expanded=(i == len(st.session_state.messages)-1)):
                    st.markdown(f"<div class='coach-box'>{coach_match.group(1).strip()}</div>", unsafe_allow_html=True)
        else:
            # Fallback for simple messages (like initial start)
            st.write(content.replace("<SIM>", "").replace("</SIM>", ""))

# ================= 7. INPUT PROCESSING (FIXED LOGIC) =================
user_input = None

# Voice Input with Loop Protection
voice_data = st.audio_input("Respond in Spanish (Voice)")
if voice_data:
    v_hash = hashlib.md5(voice_data.getvalue()).hexdigest()
    if v_hash != st.session_state.last_processed_audio:
        with st.status("Transcribing Spanish..."):
            try:
                res = client.audio.transcriptions.create(
                    file=("file.wav", voice_data.getvalue()),
                    model="whisper-large-v3",
                    language="es"
                )
                user_input = res.text
                st.session_state.last_processed_audio = v_hash
            except Exception as e:
                st.error(f"Transcription error: {e}")

# Text Input
text_in = st.chat_input("Type your response here...")
if text_in: user_input = text_in

# ================= 8. RESPONSE ENGINE =================
if user_input:
    # 1. Add User message
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    with st.chat_message("assistant"):
        # 2. Prepare History (Clean of tags for AI reasoning)
        history = []
        for m in st.session_state.messages[-8:]:
            m_sim = re.search(r'<SIM>(.*?)</SIM>', m["content"], re.DOTALL)
            clean_text = m_sim.group(1) if m_sim else m["content"]
            history.append({"role": m["role"], "content": clean_text})
        
        try:
            # 3. AI Inference
            with st.spinner("Generando respuesta..."):
                model = "llama-3.3-70b-versatile"
                try:
                    resp = client.chat.completions.create(
                        model=model, 
                        messages=[{"role": "system", "content": get_system_prompt()}] + history,
                        temperature=0.6
                    )
                except: # Fallback
                    resp = client.chat.completions.create(
                        model="llama-3.1-8b-instant", 
                        messages=[{"role": "system", "content": get_system_prompt()}] + history
                    )
            
            full_resp = resp.choices[0].message.content
            
            # 4. Parse & Display
            sim_match = re.search(r'<SIM>(.*?)</SIM>', full_resp, re.DOTALL)
            coach_match = re.search(r'<COACH>(.*?)</COACH>', full_resp, re.DOTALL)
            
            if sim_match:
                sim_text = sim_match.group(1).strip()
                st.markdown(f"<div class='sim-text'>{sim_text}</div>", unsafe_allow_html=True)
                
                # 5. Audio Generation
                tts = gTTS(text=re.sub(r'[*#_~-]', '', sim_text), lang='es')
                buf = io.BytesIO()
                tts.write_to_fp(buf)
                
                # Assign ID based on NEW length
                new_idx = len(st.session_state.messages) 
                st.session_state.audio_cache[f"audio_{new_idx}"] = buf.getvalue()
                st.audio(buf.getvalue(), format="audio/mp3")
                
                if coach_match:
                    coach_text = coach_match.group(1).strip()
                    with st.expander("📝 Elite Coaching & Analysis", expanded=True):
                        st.markdown(f"<div class='coach-box'>{coach_text}</div>", unsafe_allow_html=True)
                    
                    # 6. Metrics
                    scores = re.findall(r'[GER]:\s*(\d+)', coach_text)
                    if len(scores) >= 3:
                        st.session_state.metrics["G"].append(int(scores[0]))
                        st.session_state.metrics["E"].append(int(scores[1]))
                        st.session_state.metrics["R"].append(int(scores[2]))
            else:
                st.write(full_resp)

            # 7. Final State Save
            st.session_state.messages.append({"role": "assistant", "content": full_resp})
            st.rerun()

        except Exception as e:
            st.error(f"Critical Engine Failure: {e}")

# ================= 9. AUTO-START =================
if not st.session_state.messages:
    if "AI is Applicant" in st.session_state.role:
        start = "<SIM>Hola, mucho gusto. Gracias por la invitación. Estoy listo para comenzar la entrevista.</SIM>"
    elif "AI is Interviewer" in st.session_state.role:
        start = "<SIM>Bienvenido. He revisado su perfil. Para comenzar, cuéntenos sobre su experiencia profesional.</SIM>"
    else:
        start = "<SIM>Llamada conectada. ¿En qué puedo asistirle hoy?</SIM>"
    
    st.session_state.messages.append({"role": "assistant", "content": start})
    st.rerun()
