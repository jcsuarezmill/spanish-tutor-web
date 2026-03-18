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
                combined_text += f"\n--- Document: {uploaded_file.name} ---\n"
                combined_text += " ".join([p.extract_text() or "" for p in reader.pages])
            elif ext in ['html', 'htm']:
                combined_text += BeautifulSoup(uploaded_file.read(), 'html.parser').get_text()
            else:
                combined_text += uploaded_file.read().decode("utf-8")
        except Exception as e:
            st.error(f"Error reading {uploaded_file.name}: {e}")
    return combined_text

# ================= 2. SETUP & STATE =================
st.set_page_config(page_title="Elite Spanish Coach", layout="wide", page_icon="🏆")

# Initialize Session States
if "messages" not in st.session_state: st.session_state.messages = []
if "metrics" not in st.session_state: st.session_state.metrics = {"G": [], "E": [], "R": []}
if "kb_content" not in st.session_state: st.session_state.kb_content = ""
if "res_content" not in st.session_state: st.session_state.res_content = ""
if "last_processed_audio_hash" not in st.session_state: st.session_state.last_processed_audio_hash = ""
if "ai_voice_buffer" not in st.session_state: st.session_state.ai_voice_buffer = None

try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("API Key missing. Please check Streamlit Secrets.")
    st.stop()

# ================= 3. SYSTEM PROMPT =================
def get_system_prompt():
    role = st.session_state.get('role', 'AI is Applicant')
    scenario = st.session_state.get('scenario', 'General Interview')
    
    # Combine knowledge base and resume for context
    context = f"COMPANY DATA: {st.session_state.kb_content[:3000]}\nUSER PROFILE: {st.session_state.res_content[:3000]}"
    
    if "AI is Interviewer" in role:
        persona = f"ACT AS: Expert Interviewer. SCENARIO: {scenario}. CONTEXT: {context}"
    elif "AI is Applicant" in role:
        persona = f"ACT AS: Candidate (Rod Salmeo). SCENARIO: {scenario}. BACKGROUND: {context}"
    elif "AI is Customer" in role:
        persona = f"ACT AS: Angry Customer. CONTEXT: {context}"
    else:
        persona = f"ACT AS: Professional Agent. CONTEXT: {context}"

    return f"""
    {persona}
    LANGUAGE: Spanish Dialogue. Feedback in English/Spanish.
    
    STRICT RULE: If the user's input is garbled or clearly a transcription error, 
    ask for clarification politely in character. Do NOT hallucinate.

    FORMAT:
    [Character Response]
    ---
    COACH: (Detailed feedback on Spanish grammar, tone, and professional phrasing)
    SCORES: G: (1-10), E: (1-10), R: (1-10)
    """

# ================= 4. SIDEBAR (MULTI-FILE) =================
with st.sidebar:
    st.title("🚀 Prep Dashboard")
    st.session_state.role = st.selectbox("Current Mode", [
        "User as Interviewer (AI is Applicant)",
        "User as Applicant (AI is Interviewer)",
        "User as Agent (AI is Customer)",
        "User as Customer (AI is Agent)"
    ])
    st.session_state.scenario = st.text_input("Custom Scenario", "Job Interview")
    
    st.divider()
    st.subheader("📚 Knowledge Base")
    kb_files = st.file_uploader("Company SOPs / Manuals", accept_multiple_files=True, type=['pdf', 'txt', 'html'])
    if kb_files: st.session_state.kb_content = extract_text_from_multiple(kb_files)
    
    st.subheader("📄 Your Documents")
    res_files = st.file_uploader("Resumes / Cover Letters", accept_multiple_files=True, type=['pdf', 'txt', 'html'])
    if res_files: st.session_state.res_content = extract_text_from_multiple(res_files)

    if st.button("🗑️ Clear Chat & Reset"):
        st.session_state.messages = []
        st.session_state.metrics = {"G": [], "E": [], "R": []}
        st.session_state.ai_voice_buffer = None
        st.rerun()

# ================= 5. MAIN UI =================
st.title("🇪🇸 Elite Spanish Coach")

# Performance Metrics
if st.session_state.metrics["G"]:
    m1, m2, m3 = st.columns(3)
    avg = lambda x: sum(st.session_state.metrics[x])/len(st.session_state.metrics[x])
    m1.metric("Grammar Accuracy", f"{avg('G'):.1f}/10")
    m2.metric("Professional Empathy", f"{avg('E'):.1f}/10")
    m3.metric("Goal Result", f"{avg('R'):.1f}/10")

# Chat Container
for i, m in enumerate(st.session_state.messages):
    with st.chat_message(m["role"]):
        if "---" in m["content"]:
            txt, coach = m["content"].split("---", 1)
            st.write(txt.strip())
            with st.expander("📝 Coaching & Analysis"):
                st.info(coach.strip())
            # Persistent Audio for the latest response
            if i == len(st.session_state.messages)-1 and st.session_state.ai_voice_buffer:
                st.audio(st.session_state.ai_voice_buffer, format="audio/mp3")
        else:
            st.write(m["content"])

# ================= 6. INPUT LOGIC (ANTI-LOOP) =================
user_input = None

# 1. Voice Input with Hash Checking to prevent looping
audio_data = st.audio_input("Speak in Spanish")
if audio_data:
    # Generate a unique ID for this audio chunk
    current_hash = hashlib.md5(audio_data.getvalue()).hexdigest()
    
    if current_hash != st.session_state.last_processed_audio_hash:
        with st.status("Transcribing Spanish..."):
            try:
                transcription = client.audio.transcriptions.create(
                    file=("file.wav", audio_data.getvalue()),
                    model="whisper-large-v3",
                    language="es"
                )
                user_input = transcription.text
                st.session_state.last_processed_audio_hash = current_hash
            except Exception as e:
                st.error("Transcription Error. Please try again.")

# 2. Text Input
text_input = st.chat_input("Or type your response...")
if text_input:
    user_input = text_input

# ================= 7. AI ENGINE (WITH FALLBACK) =================
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    with st.chat_message("assistant"):
        # Memory Management (Last 10 messages, clean history)
        history = [{"role": m["role"], "content": m["content"].split("---")[0]} for m in st.session_state.messages[-10:]]
        
        try:
            # Model Attempt 1: 70B
            try:
                model = "llama-3.3-70b-versatile"
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": get_system_prompt()}] + history,
                    temperature=0.6
                )
            except Exception as e:
                # Fallback to 8B if Rate Limited
                st.warning("Switching to High-Speed Engine (Rate Limit Reached)")
                model = "llama-3.1-8b-instant"
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": get_system_prompt()}] + history
                )
            
            answer = response.choices[0].message.content
            st.session_state.messages.append({"role": "assistant", "content": answer})
            
            # Parsing and Audio
            if "---" in answer:
                txt_only = answer.split("---")[0].strip()
                coach_only = answer.split("---")[1]
                
                st.write(txt_only)
                
                # Metric Extraction
                scores = re.findall(r'[GER]:\s*(\d+)', coach_only)
                if len(scores) >= 3:
                    st.session_state.metrics["G"].append(int(scores[0]))
                    st.session_state.metrics["E"].append(int(scores[1]))
                    st.session_state.metrics["R"].append(int(scores[2]))
                
                # TTS Generation
                tts = gTTS(text=re.sub(r'[*#_~-]', '', txt_only), lang='es')
                audio_buf = io.BytesIO()
                tts.write_to_fp(audio_buf)
                st.session_state.ai_voice_buffer = audio_buf.getvalue()
                st.audio(st.session_state.ai_voice_buffer, format="audio/mp3")
                
                with st.expander("📝 Coaching & Analysis"):
                    st.info(coach_only.strip())
            else:
                st.write(answer)
            
            st.rerun()

        except Exception as e:
            st.error(f"System Error: {e}")

# ================= 8. STARTUP =================
if not st.session_state.messages:
    intro = "Llamada conectada. El sistema está listo. ¿En qué puedo ayudarle hoy? --- COACH: Simulation ready. Please begin. | SCORES: G: 5, E: 5, R: 5"
    st.session_state.messages.append({"role": "assistant", "content": intro})
    st.rerun()
