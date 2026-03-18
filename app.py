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
if "feedback_cache" not in st.session_state: st.session_state.feedback_cache = {}

try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("GROQ_API_KEY is missing in secrets.")
    st.stop()

# ================= 3. DYNAMIC PROMPTS =================
def get_sim_prompt():
    role = st.session_state.get('role', 'User as Applicant')
    scenario = st.session_state.get('scenario', 'Job Interview')
    context = f"CONTEXT DOCUMENTS: {st.session_state.kb_content[:3000]}\nUSER DATA: {st.session_state.res_content[:2000]}"
    
    if "AI is Applicant" in role:
        persona = "ACT AS: Rod Salmeo (Job Applicant). Tone: Professional/Polite."
    elif "AI is Interviewer" in role:
        persona = "ACT AS: Professional Interviewer. Tone: Formal/Observant."
    elif "AI is Customer" in role:
        persona = "ACT AS: A Customer. Tone: Realistic/Direct."
    else:
        persona = "ACT AS: A Professional Agent. Tone: Helpful/Efficient."

    return f"""
    {persona}
    SCENARIO: {scenario}
    DOCUMENT CONTEXT: {context}
    STRICT RULE: Respond ONLY in Spanish as the character. Do not provide coaching yet.
    """

def get_coaching_prompt(user_text, ai_text):
    return f"""
    As an Elite Spanish Business Coach, analyze this interaction:
    User said: "{user_text}"
    AI responded: "{ai_text}"

    Provide feedback in English:
    1. **Grammar Correction**: Fix any errors in the User's Spanish.
    2. **Tone & Nuance**: How can the user sound more professional?
    3. **Key Vocabulary**: Explain 1-2 professional terms used in the conversation.
    4. **Scores**: Use exactly this format: G: (1-10), E: (1-10), R: (1-10)
    """

# Helper for API Fallback (Fixes RateLimitError)
def safe_chat_completion(messages, model_70b="llama-3.3-70b-versatile", model_8b="llama-3.1-8b-instant"):
    try:
        return client.chat.completions.create(model=model_70b, messages=messages)
    except Exception:
        # Fallback to faster/smaller model if 70b is rate-limited
        return client.chat.completions.create(model=model_8b, messages=messages)

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
    st.session_state.kb_content = extract_text(kb_files) if kb_files else ""
        
    res_files = st.file_uploader("Your Resume / Bio", accept_multiple_files=True)
    st.session_state.res_content = extract_text(res_files) if res_files else ""

    if st.button("🗑️ Reset Coaching"):
        st.session_state.messages = []
        st.session_state.metrics = {"G": [], "E": [], "R": []}
        st.session_state.feedback_cache = {}
        st.rerun()

# ================= 5. MAIN UI =================
st.title("🇪🇸 Elite Spanish Professional Coach")

# Dashboard
if st.session_state.metrics["G"]:
    m1, m2, m3 = st.columns(3)
    avg = lambda k: sum(st.session_state.metrics[k])/len(st.session_state.metrics[k])
    m1.metric("Grammar Accuracy", f"{avg('G'):.1f}/10")
    m2.metric("Professional Empathy", f"{avg('E'):.1f}/10")
    m3.metric("Result / Outcome", f"{avg('R'):.1f}/10")
    st.divider()

# Message Display Loop
for i, m in enumerate(st.session_state.messages):
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if "audio" in m:
            st.audio(m["audio"], format="audio/mp3")
        
        # Feedback logic for AI messages
        if m["role"] == "assistant" and i > 0:
            if i in st.session_state.feedback_cache:
                st.info(st.session_state.feedback_cache[i])
            else:
                if st.button("📝 Get Coaching", key=f"btn_{i}"):
                    user_msg = st.session_state.messages[i-1]["content"]
                    with st.spinner("Analyzing..."):
                        c_res = safe_chat_completion([{"role": "user", "content": get_coaching_prompt(user_msg, m["content"])}])
                        feedback = c_res.choices[0].message.content
                        st.session_state.feedback_cache[i] = feedback
                        
                        # Extract metrics
                        scores = re.findall(r'[GER]:\s*(\d+)', feedback)
                        if len(scores) >= 3:
                            st.session_state.metrics["G"].append(int(scores[0]))
                            st.session_state.metrics["E"].append(int(scores[1]))
                            st.session_state.metrics["R"].append(int(scores[2]))
                    st.rerun()

# ================= 6. INPUT LOGIC =================
user_input = None
audio_data = st.audio_input("Respond in Spanish")

if audio_data:
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

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    with st.chat_message("assistant"):
        history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-8:]]
        
        try:
            response = safe_chat_completion([{"role": "system", "content": get_sim_prompt()}] + history)
            ans = response.choices[0].message.content
            
            # Generate Audio
            tts = gTTS(text=re.sub(r'[*#_~-]', '', ans), lang='es')
            audio_buf = io.BytesIO()
            tts.write_to_fp(audio_buf)
            audio_bytes = audio_buf.getvalue()
            
            st.session_state.messages.append({"role": "assistant", "content": ans, "audio": audio_bytes})
            st.rerun()
        except Exception as e:
            st.error(f"API Error: {e}")

# ================= 7. STARTUP =================
if not st.session_state.messages:
    if "AI is Applicant" in st.session_state.role:
        start = "Hola, mucho gusto. Gracias por recibirme hoy. ¿Comenzamos la entrevista?"
    elif "AI is Interviewer" in st.session_state.role:
        start = "Bienvenido. He revisado su perfil. ¿Podría comenzar presentándose?"
    else:
        start = "Hola, ¿en qué puedo ayudarle hoy con su orden?"
    
    st.session_state.messages.append({"role": "assistant", "content": start})
    st.rerun()
