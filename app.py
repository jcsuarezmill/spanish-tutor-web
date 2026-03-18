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

if "messages" not in st.session_state: st.session_state.messages = []
if "metrics" not in st.session_state: st.session_state.metrics = {"G": [], "E": [], "R": []}
if "last_processed_id" not in st.session_state: st.session_state.last_processed_id = ""

try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("GROQ_API_KEY is missing in secrets.")
    st.stop()

# ================= 3. DYNAMIC PROMPT =================
def get_system_prompt():
    role = st.session_state.get('role', 'User as Applicant')
    scenario = st.session_state.get('scenario', 'Job Interview')
    context = f"CONTEXT DOCUMENTS: {st.session_state.kb_content[:5000]}\nUSER DATA: {st.session_state.res_content[:5000]}"
    
    # Determine who the AI is based on selected role
    if "AI is Applicant" in role:
        persona = f"ACT AS: A job applicant named Rod Salmeo. Tone: Professional/Polite."
    elif "AI is Interviewer" in role:
        persona = f"ACT AS: A high-level Professional Interviewer. Tone: Formal/Observant."
    elif "AI is Customer" in role:
        persona = f"ACT AS: A Customer. Tone: Realistic/Direct."
    else:
        persona = f"ACT AS: A Professional Agent. Tone: Helpful/Efficient."

    return f"""
    {persona}
    SCENARIO: {scenario}
    DOCUMENT CONTEXT: {context}

    STRICT RULES:
    1. Stay in character for the dialogue.
    2. Respond in Spanish ONLY for the character part.
    3. Use the following XML tags for every response:
    
    <SIM>
    [Character response in Spanish]
    </SIM>
    
    <COACH>
    **Feedback on User's Spanish:** (Correct their grammar, vocabulary, and professional tone)
    **Learning Point:** (Explain 1-2 professional Spanish words you used in your response)
    **Scores:** G: (1-10), E: (1-10), R: (1-10)
    </COACH>
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

    if st.button("🗑️ Reset Coaching"):
        st.session_state.messages = []
        st.session_state.metrics = {"G": [], "E": [], "R": []}
        st.session_state.last_processed_id = ""
        st.rerun()

# ================= 5. MAIN UI =================
st.title("🇪🇸 Elite Spanish Professional Coach")

# Performance Dashboard
if st.session_state.metrics["G"]:
    m1, m2, m3 = st.columns(3)
    avg = lambda k: sum(st.session_state.metrics[k])/len(st.session_state.metrics[k])
    m1.metric("Grammar Accuracy", f"{avg('G'):.1f}/10")
    m2.metric("Professional Empathy", f"{avg('E'):.1f}/10")
    m3.metric("Result / Outcome", f"{avg('R'):.1f}/10")
    st.divider()

# Message Display
for i, m in enumerate(st.session_state.messages):
    with st.chat_message(m["role"]):
        # Use Regex to separate SIM and COACH
        sim_match = re.search(r'<SIM>(.*?)</SIM>', m["content"], re.DOTALL)
        coach_match = re.search(r'<COACH>(.*?)</COACH>', m["content"], re.DOTALL)
        
        if sim_match:
            st.markdown(f"#### {sim_match.group(1).strip()}")
            # Play audio stored specifically for THIS message
            if "audio" in m:
                st.audio(m["audio"], format="audio/mp3")
                
            if coach_match:
                with st.expander("📝 View Coaching Analysis", expanded=(i == len(st.session_state.messages)-1)):
                    st.info(coach_match.group(1).strip())
        else:
            # Fallback for system or start messages
            st.write(m["content"])

# ================= 6. INPUT LOGIC (ANTI-LOOP) =================
user_input = None

audio_data = st.audio_input("Respond in Spanish")
if audio_data:
    # Checksum to prevent reprocessing the same audio on rerun
    current_id = hashlib.md5(audio_data.getvalue()).hexdigest()
    if current_id != st.session_state.last_processed_id:
        with st.spinner("Transcribing..."):
            try:
                res = client.audio.transcriptions.create(
                    file=("file.wav", audio_data.getvalue()),
                    model="whisper-large-v3",
                    language="es"
                )
                user_input = res.text
                st.session_state.last_processed_id = current_id
            except: st.error("Transcription failed.")

text_in = st.chat_input("Type your response...")
if text_in: user_input = text_in

# ================= 7. AI BRAIN =================
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    with st.chat_message("assistant"):
        # Build clean history (strip coaching tags)
        history = []
        for m in st.session_state.messages[-8:]:
            sim_only = re.search(r'<SIM>(.*?)</SIM>', m["content"], re.DOTALL)
            history.append({"role": m["role"], "content": sim_only.group(1) if sim_only else m["content"]})
        
        try:
            # AI Inference
            model = "llama-3.3-70b-versatile"
            try:
                response = client.chat.completions.create(model=model, messages=[{"role": "system", "content": get_system_prompt()}] + history)
            except:
                response = client.chat.completions.create(model="llama-3.1-8b-instant", messages=[{"role": "system", "content": get_system_prompt()}] + history)
            
            full_text = response.choices[0].message.content
            
            # Parse Simulation Text
            sim_text = re.search(r'<SIM>(.*?)</SIM>', full_text, re.DOTALL)
            coach_text = re.search(r'<COACH>(.*?)</COACH>', full_text, re.DOTALL)
            
            if sim_text:
                clean_sim = sim_text.group(1).strip()
                st.markdown(f"#### {clean_sim}")
                
                # Generate Audio
                tts = gTTS(text=re.sub(r'[*#_~-]', '', clean_sim), lang='es')
                audio_buf = io.BytesIO()
                tts.write_to_fp(audio_buf)
                audio_bytes = audio_buf.getvalue()
                
                st.audio(audio_bytes, format="audio/mp3")
                
                if coach_text:
                    with st.expander("📝 View Coaching Analysis", expanded=True):
                        st.info(coach_text.group(1).strip())
                    # Scores
                    scores = re.findall(r'[GER]:\s*(\d+)', coach_text.group(1))
                    if len(scores) >= 3:
                        st.session_state.metrics["G"].append(int(scores[0]))
                        st.session_state.metrics["E"].append(int(scores[1]))
                        st.session_state.metrics["R"].append(int(scores[2]))
                
                # SAVE MESSAGE WITH AUDIO BYTES
                st.session_state.messages.append({"role": "assistant", "content": full_text, "audio": audio_bytes})
            else:
                st.write(full_text)
            
            st.rerun()

        except Exception as e:
            st.error(f"Error: {e}")

# ================= 8. STARTUP =================
if not st.session_state.messages:
    if "AI is Applicant" in st.session_state.role:
        start = "<SIM>Hola, mucho gusto. Gracias por recibirme hoy. Estoy listo para comenzar la entrevista cuando usted diga.</SIM>"
    elif "AI is Interviewer" in st.session_state.role:
        start = "<SIM>Bienvenido. He revisado su perfil y estoy interesado en conocer más sobre usted. ¿Podría comenzar presentándose?</SIM>"
    else:
        start = "<SIM>Llamada conectada. Hola, ¿en qué puedo ayudarle hoy?</SIM>"
    
    st.session_state.messages.append({"role": "assistant", "content": start})
    st.rerun()
