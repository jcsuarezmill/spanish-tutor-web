import streamlit as st
from groq import Groq
from gtts import gTTS
import io
import re
import hashlib
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup

# ================= 1. MULTI-FILE PARSING =================
def extract_text_from_multiple(uploaded_files):
    combined_text = ""
    if not uploaded_files: return ""
    for uploaded_file in uploaded_files:
        ext = uploaded_file.name.split('.')[-1].lower()
        try:
            if ext == 'pdf':
                reader = PdfReader(uploaded_file)
                combined_text += f"\n[Document: {uploaded_file.name}]\n"
                combined_text += " ".join([p.extract_text() or "" for p in reader.pages])
            elif ext in ['html', 'htm']:
                combined_text += BeautifulSoup(uploaded_file.read(), 'html.parser').get_text()
            else:
                combined_text += uploaded_file.read().decode("utf-8")
        except Exception as e:
            st.error(f"Error reading {uploaded_file.name}: {e}")
    return combined_text

# ================= 2. SETUP & STATE =================
st.set_page_config(page_title="Elite Spanish Coach v3", layout="wide", page_icon="🏆")

if "messages" not in st.session_state: st.session_state.messages = []
if "metrics" not in st.session_state: st.session_state.metrics = {"G": [], "E": [], "R": []}
if "kb_content" not in st.session_state: st.session_state.kb_content = ""
if "res_content" not in st.session_state: st.session_state.res_content = ""
if "last_processed_hash" not in st.session_state: st.session_state.last_processed_hash = ""
if "audio_store" not in st.session_state: st.session_state.audio_store = {}

try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("API Key missing. Please check Streamlit Secrets.")
    st.stop()

# ================= 3. THE INTERACTION ENGINE (PROMPT) =================
def get_system_prompt():
    role_mode = st.session_state.get('role', 'User as Interviewer (AI is Applicant)')
    scenario = st.session_state.get('scenario', 'Job Interview')
    
    # Context Synthesis
    full_context = f"KNOWLEDGE_BASE: {st.session_state.kb_content[:2000]}\nUSER_RESUME/BIO: {st.session_state.res_content[:2000]}"
    
    # Define AI Character
    if "AI is Applicant" in role_mode:
        ai_persona = f"ACT AS: Rod Salmeo, a Job Applicant. Use the background provided: {full_context}. Your tone is professional, eager, and polite."
    elif "AI is Interviewer" in role_mode:
        ai_persona = f"ACT AS: A Senior Executive Recruiter. Use the company context: {full_context}. Your tone is professional, observant, and demanding."
    elif "AI is Customer" in role_mode:
        ai_persona = f"ACT AS: A frustrated customer. Use context: {full_context}. Your tone is urgent and slightly annoyed."
    else:
        ai_persona = f"ACT AS: A high-level Support Agent. Use context: {full_context}. Your tone is helpful and calm."

    return f"""
    {ai_persona}
    
    SIMULATION GOAL: Engage in a realistic Spanish dialogue for this scenario: {scenario}.
    
    IMPORTANT: You must follow this TWO-PART response format strictly:
    
    PART 1: [Response]
    Respond as your character in Spanish. Do NOT mention coaching or scores in this part. Stay 100% in character.
    
    PART 2: [Coaching]
    Provide a divider '---' followed by a detailed Spanish Language Coaching block.
    Analyze:
    1. The USER'S last message (Grammar, Anglicisms, Professionalism).
    2. YOUR own response (Explain the choice of professional vocabulary used).
    3. Give a 'Pro-Tip' for professional Spanish.
    4. Provide numeric scores for the USER: G: (1-10), E: (1-10), R: (1-10)
    
    STRICT DELIMITER: Use '---' to separate PART 1 and PART 2.
    """

# ================= 4. SIDEBAR =================
with st.sidebar:
    st.title("🏆 Elite Coach Setup")
    new_role = st.selectbox("Current Mode", [
        "User as Interviewer (AI is Applicant)",
        "User as Applicant (AI is Interviewer)",
        "User as Agent (AI is Customer)",
        "User as Customer (AI is Agent)"
    ])
    
    if "role" in st.session_state and st.session_state.role != new_role:
        st.session_state.messages = []
        st.session_state.metrics = {"G": [], "E": [], "R": []}
        st.session_state.audio_store = {}
        st.session_state.role = new_role
        st.rerun()
    st.session_state.role = new_role

    st.session_state.scenario = st.text_input("Custom Scenario", "General Professional Interview")
    
    st.divider()
    st.subheader("📂 Upload Context Files")
    kb_files = st.file_uploader("Company Info/SOPs", accept_multiple_files=True, type=['pdf', 'txt', 'html'])
    if kb_files: st.session_state.kb_content = extract_text_from_multiple(kb_files)
    
    res_files = st.file_uploader("Resumes/Background", accept_multiple_files=True, type=['pdf', 'txt', 'html'])
    if res_files: st.session_state.res_content = extract_text_from_multiple(res_files)

    if st.button("🗑️ Reset All Progress", use_container_width=True):
        st.session_state.messages = []
        st.session_state.metrics = {"G": [], "E": [], "R": []}
        st.session_state.audio_store = {}
        st.rerun()

# ================= 5. DASHBOARD =================
st.title("🇪🇸 Elite Spanish Coach")

if st.session_state.metrics["G"]:
    cols = st.columns(3)
    avg = lambda k: sum(st.session_state.metrics[k])/len(st.session_state.metrics[k])
    cols[0].metric("Grammar", f"{avg('G'):.1f}/10")
    cols[1].metric("Empathy", f"{avg('E'):.1f}/10")
    cols[2].metric("Result", f"{avg('R'):.1f}/10")
    st.divider()

# ================= 6. CHAT RENDERER =================
for i, m in enumerate(st.session_state.messages):
    with st.chat_message(m["role"]):
        if "---" in m["content"]:
            char_text, coach_text = m["content"].split("---", 1)
            # Display Simulation Character
            st.markdown(f"### {char_text.strip()}")
            
            # Display Coaching
            with st.expander("📝 Coaching & Professional Analysis", expanded=(i == len(st.session_state.messages)-1)):
                st.markdown(coach_text.strip())
            
            # Persistent Audio Playback
            if i in st.session_state.audio_store:
                st.audio(st.session_state.audio_store[i], format="audio/mp3")
        else:
            st.write(m["content"])

# ================= 7. INPUT HANDLING (NO LOOP) =================
user_input = None

# Voice Input with hash-protection
audio_in = st.audio_input("Respond in Spanish (Voice)")
if audio_in:
    current_hash = hashlib.md5(audio_in.getvalue()).hexdigest()
    if current_hash != st.session_state.last_processed_hash:
        with st.spinner("Transcribing..."):
            try:
                res = client.audio.transcriptions.create(
                    file=("file.wav", audio_in.getvalue()),
                    model="whisper-large-v3",
                    language="es"
                )
                user_input = res.text
                st.session_state.last_processed_hash = current_hash
            except: st.error("Audio processing failed.")

# Text Input
text_in = st.chat_input("Type your response...")
if text_in: user_input = text_in

# ================= 8. SIMULATION ENGINE =================
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    with st.chat_message("assistant"):
        # CLEAN HISTORY: Send only dialogue to AI (prevents it from talking about coaching scores)
        clean_history = []
        for m in st.session_state.messages[-8:]:
            content = m["content"].split("---")[0].strip()
            clean_history.append({"role": m["role"], "content": content})
        
        try:
            # AI Inference
            model = "llama-3.3-70b-versatile"
            try:
                response = client.chat.completions.create(
                    model=model, 
                    messages=[{"role": "system", "content": get_system_prompt()}] + clean_history,
                    temperature=0.7
                )
            except:
                model = "llama-3.1-8b-instant"
                response = client.chat.completions.create(
                    model=model, 
                    messages=[{"role": "system", "content": get_system_prompt()}] + clean_history
                )
            
            full_response = response.choices[0].message.content
            
            if "---" in full_response:
                sim_text, coach_block = full_response.split("---", 1)
                st.markdown(f"### {sim_text.strip()}")
                
                # Audio Generation (Simulation Text Only)
                tts = gTTS(text=re.sub(r'[*#_~-]', '', sim_text), lang='es')
                audio_buffer = io.BytesIO()
                tts.write_to_fp(audio_buffer)
                msg_index = len(st.session_state.messages)
                st.session_state.audio_store[msg_index] = audio_buffer.getvalue()
                st.audio(st.session_state.audio_store[msg_index], format="audio/mp3")
                
                with st.expander("📝 Coaching & Professional Analysis", expanded=True):
                    st.markdown(coach_block.strip())
                
                # Metric Extraction
                scores = re.findall(r'[GER]:\s*(\d+)', coach_block)
                if len(scores) >= 3:
                    st.session_state.metrics["G"].append(int(scores[0]))
                    st.session_state.metrics["E"].append(int(scores[1]))
                    st.session_state.metrics["R"].append(int(scores[2]))
            else:
                st.write(full_response)
            
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            st.rerun()

        except Exception as e:
            st.error(f"Engine Error: {e}")

# ================= 9. AUTO-START =================
if not st.session_state.messages:
    if "AI is Applicant" in st.session_state.role:
        start_text = "Hola, mucho gusto. Gracias por recibirme hoy para la entrevista. Estoy listo para comenzar cuando usted diga. --- COACH: Inicie la entrevista pidiendo una presentación o revisando el CV."
    elif "AI is Interviewer" in st.session_state.role:
        start_text = "Bienvenido. He estado revisando su perfil y documentos. Para comenzar, ¿podría hablarnos un poco sobre su experiencia profesional? --- COACH: Responda presentándose de manera profesional."
    else:
        start_text = "Llamada conectada. ¿En qué puedo ayudarle hoy? --- COACH: Explique su problema o solicite asistencia."
    
    st.session_state.messages.append({"role": "assistant", "content": start_text})
    st.rerun()
