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
        text_out += f"\n--- DOCUMENT: {f.name} ---\n"
        try:
            if ext == 'pdf':
                reader = PdfReader(f)
                text_out += " ".join([p.extract_text() or "" for p in reader.pages])
            elif ext in ['html', 'htm']:
                text_out += BeautifulSoup(f.read(), 'html.parser').get_text()
            else:
                text_out += f.read().decode("utf-8", errors='ignore')
        except Exception as e:
            text_out += f"[Parsing Error: {e}]"
    return text_out

# ================= 2. SETUP & STATE =================
st.set_page_config(page_title="Elite Spanish Coach Pro", layout="wide", page_icon="🇪🇸")

# Initialize Session State
state_keys = {
    "messages": [], 
    "metrics": {"G": [], "E": [], "R": []}, 
    "last_processed_id": "",
    "kb_content": "",
    "res_content": ""
}
for key, value in state_keys.items():
    if key not in st.session_state: st.session_state[key] = value

try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("GROQ_API_KEY missing in secrets.")
    st.stop()

# ================= 3. ENHANCED SYSTEM PROMPT =================
def get_system_prompt():
    role = st.session_state.get('role', 'User as Applicant')
    scenario = st.session_state.get('scenario', 'Job Interview')
    context = f"KNOWLEDGE BASE: {st.session_state.kb_content[:6000]}\nUSER DOCUMENTS: {st.session_state.res_content[:6000]}"
    
    if "AI is Applicant" in role:
        persona = "ACT AS: Rod Salmeo (Job Applicant). Personality: Professional, technical, eager."
    elif "AI is Interviewer" in role:
        persona = "ACT AS: High-level Executive Recruiter. Personality: Formal, investigative, fair."
    elif "AI is Customer" in role:
        persona = "ACT AS: A Customer with a specific need. Personality: Direct, realistic, emotional."
    else:
        persona = "ACT AS: Professional Support Lead. Personality: Calm, empathetic, resolution-oriented."

    return f"""
    {persona}
    SCENARIO: {scenario}
    DOCUMENTS: {context}

    INSTRUCTIONS:
    1. Respond naturally in Spanish dialogue first.
    2. Provide an Elite Coaching block. 
    3. If User is Applicant, evaluate if they used the STAR method (Situation, Task, Action, Result).
    4. Focus on 'False Cognates' (e.g., 'asistir' vs 'atender') and 'Subjunctive' usage.

    STRICT FORMAT:
    <SIM>
    [Character response in Spanish - keep it immersive]
    </SIM>
    
    <COACH>
    **Spanish Correction:** (Directly fix user's grammar/vocab mistakes)
    **Executive Vocabulary:** (1 high-level phrase used in the response to learn)
    **Professional Strategy:** (Feedback on their soft skills/tone)
    **Scores:** G: (1-10), E: (1-10), R: (1-10)
    </COACH>
    """

# ================= 4. SIDEBAR & EXPORT =================
with st.sidebar:
    st.title("🏆 Elite Prep Console")
    st.session_state.role = st.selectbox("Role-Play Mode", [
        "User as Interviewer (AI is Applicant)",
        "User as Applicant (AI is Interviewer)",
        "User as Agent (AI is Customer)",
        "User as Customer (AI is Agent)"
    ])
    st.session_state.scenario = st.text_input("Simulation Scenario", "Professional Interview")
    
    st.divider()
    st.subheader("📂 Training Documents")
    kb_up = st.file_uploader("Company Docs/SOPs", accept_multiple_files=True)
    if kb_up: st.session_state.kb_content = extract_text(kb_up)
        
    res_up = st.file_uploader("Your Resume/Background", accept_multiple_files=True)
    if res_up: st.session_state.res_content = extract_text(res_up)

    if st.button("🗑️ Reset All", use_container_width=True):
        for key in state_keys: st.session_state[key] = state_keys[key]
        st.rerun()

    # --- Export Feature ---
    if st.session_state.messages:
        st.divider()
        transcript = ""
        for m in st.session_state.messages:
            transcript += f"{m['role'].upper()}: {m['content']}\n\n"
        st.download_button("📥 Download Transcript", transcript, file_name="coaching_session.txt")

# ================= 5. MAIN UI & DASHBOARD =================
st.title("🇪🇸 Elite Spanish Professional Coach")

if st.session_state.metrics["G"]:
    c1, c2, c3 = st.columns(3)
    avg = lambda k: sum(st.session_state.metrics[k])/len(st.session_state.metrics[k])
    c1.metric("Grammar Accuracy", f"{avg('G'):.1f}/10")
    c2.metric("Professional Tone", f"{avg('E'):.1f}/10")
    c3.metric("Result Efficiency", f"{avg('R'):.1f}/10")
    st.divider()

# Render Messages
for i, m in enumerate(st.session_state.messages):
    with st.chat_message(m["role"]):
        sim_m = re.search(r'<SIM>(.*?)</SIM>', m["content"], re.DOTALL)
        coach_m = re.search(r'<COACH>(.*?)</COACH>', m["content"], re.DOTALL)
        
        if sim_m:
            st.markdown(f"#### {sim_m.group(1).strip()}")
            if "audio" in m:
                st.audio(m["audio"], format="audio/mp3")
            if coach_m:
                with st.expander("📝 Coaching Analysis", expanded=(i == len(st.session_state.messages)-1)):
                    st.markdown(coach_m.group(1).strip())
        else:
            st.write(m["content"])

# ================= 6. INPUT LOGIC =================
user_msg = None

# Audio input with anti-loop hash
audio_in = st.audio_input("Speak in Spanish")
if audio_in:
    aud_hash = hashlib.md5(audio_in.getvalue()).hexdigest()
    if aud_hash != st.session_state.last_processed_id:
        with st.status("Transcribing..."):
            try:
                res = client.audio.transcriptions.create(
                    file=("file.wav", audio_in.getvalue()),
                    model="whisper-large-v3",
                    language="es"
                )
                user_msg = res.text
                st.session_state.last_processed_id = aud_hash
            except: st.error("Transcription Error.")

text_in = st.chat_input("Type your response here...")
if text_in: user_msg = text_in

# ================= 7. AI ENGINE =================
if user_msg:
    st.session_state.messages.append({"role": "user", "content": user_msg})
    
    with st.chat_message("assistant"):
        # Create history for AI context (Dialogue only)
        history = []
        for m in st.session_state.messages[-10:]:
            match = re.search(r'<SIM>(.*?)</SIM>', m["content"], re.DOTALL)
            history.append({"role": m["role"], "content": match.group(1) if match else m["content"]})
        
        try:
            # Inference (Llama 70B for high-quality coaching)
            try:
                model = "llama-3.3-70b-versatile"
                response = client.chat.completions.create(model=model, messages=[{"role": "system", "content": get_system_prompt()}] + history, temperature=0.7)
            except:
                response = client.chat.completions.create(model="llama-3.1-8b-instant", messages=[{"role": "system", "content": get_system_prompt()}] + history)
            
            answer = response.choices[0].message.content
            
            # Parsing SIM and COACH
            sim_block = re.search(r'<SIM>(.*?)</SIM>', answer, re.DOTALL)
            coach_block = re.search(r'<COACH>(.*?)</COACH>', answer, re.DOTALL)
            
            if sim_block:
                clean_sim = sim_block.group(1).strip()
                st.markdown(f"#### {clean_sim}")
                
                # TTS Generation (Dialogue only)
                tts = gTTS(text=re.sub(r'[*#_~-]', '', clean_sim), lang='es')
                buf = io.BytesIO()
                tts.write_to_fp(buf)
                aud_bytes = buf.getvalue()
                st.audio(aud_bytes, format="audio/mp3")
                
                if coach_block:
                    coach_data = coach_block.group(1).strip()
                    with st.expander("📝 Coaching Analysis", expanded=True):
                        st.markdown(coach_data)
                    
                    # Robust Metric Extraction
                    s_g = re.search(r'G:\s*(\d+)', coach_data)
                    s_e = re.search(r'E:\s*(\d+)', coach_data)
                    s_r = re.search(r'R:\s*(\d+)', coach_data)
                    if s_g and s_e and s_r:
                        st.session_state.metrics["G"].append(int(s_g.group(1)))
                        st.session_state.metrics["E"].append(int(s_e.group(1)))
                        st.session_state.metrics["R"].append(int(s_r.group(1)))
                
                # Final Persistence
                st.session_state.messages.append({"role": "assistant", "content": answer, "audio": aud_bytes})
                st.rerun()
            else:
                st.write(answer)
        
        except Exception as e:
            st.error(f"Engine Error: {e}")

# ================= 8. INITIAL TRIGGER =================
if not st.session_state.messages:
    # No Coaching on start message
    if "AI is Applicant" in st.session_state.role:
        start = "<SIM>Hola, mucho gusto. Es un placer estar aquí. He traído mi currículum y estoy listo para comenzar cuando usted diga.</SIM>"
    elif "AI is Interviewer" in st.session_state.role:
        start = "<SIM>Bienvenido. He revisado su perfil y documentos. Para comenzar, ¿podría presentarse y hablarme de su experiencia?</SIM>"
    else:
        start = "<SIM>Llamada conectada. Hola, buenos días. ¿En qué puedo ayudarle hoy?</SIM>"
    
    st.session_state.messages.append({"role": "assistant", "content": start})
    st.rerun()
