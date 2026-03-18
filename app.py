import streamlit as st
from groq import Groq
from gtts import gTTS
import io
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
st.set_page_config(page_title="Elite Spanish Coach", layout="wide", page_icon="🇪🇸")

# Initialize session state keys
if "messages" not in st.session_state: st.session_state.messages = []
if "metrics" not in st.session_state: st.session_state.metrics = {"G": [], "E": [], "R": []}
if "kb" not in st.session_state: st.session_state.kb = ""
if "resume" not in st.session_state: st.session_state.resume = ""
if "last_audio" not in st.session_state: st.session_state.last_audio = None

try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("API Key missing in Secrets.")
    st.stop()

# ================= 3. ENHANCED SYSTEM PROMPT =================
def get_system_prompt():
    role = st.session_state.get('role', 'User as Applicant')
    scenario = st.session_state.get('scenario', 'Job Interview')
    
    if "AI is Interviewer" in role:
        persona = f"ACT AS: Professional Recruiter. GOAL: Interview user for {scenario}. RESUME: {st.session_state.resume[:1500]}."
    elif "AI is Applicant" in role:
        persona = f"ACT AS: Rod Salmeo (Job Applicant). RESUME: {st.session_state.resume[:1500]}. User is interviewing you."
    elif "AI is Customer" in role:
        persona = f"ACT AS: Frustrated Customer. KB: {st.session_state.kb[:1500]}. User is support agent."
    else:
        persona = f"ACT AS: Elite Support Agent. KB: {st.session_state.kb[:1500]}. User is customer."

    return f"""
    {persona}
    LANGUAGE: Spanish ONLY for dialogue.
    
    INSTRUCTIONS:
    1. Stay in character.
    2. Provide a 'COACH' section in English or Spanish evaluating the user's last Spanish response.
    3. Focus on: Grammar (G), Empathy/Tone (E), and Professional Result (R).
    
    STRICT FORMAT:
    [Character response in Spanish]
    ---
    COACH: (Specific feedback on user's Spanish grammar and professional vocabulary)
    SCORES: G: (1-10), E: (1-10), R: (1-10)
    """

# ================= 4. SIDEBAR =================
with st.sidebar:
    st.title("⚙️ Coach Settings")
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

    st.session_state.scenario = st.text_input("Scenario", "General Interview")
    
    st.divider()
    kb_up = st.file_uploader("Upload Company SOPs", type=['pdf', 'html', 'txt'])
    if kb_up: st.session_state.kb = extract_text(kb_up)
    
    res_up = st.file_uploader("Upload Resume", type=['pdf', 'html', 'txt'])
    if res_up: st.session_state.resume = extract_text(res_up)

    if st.button("Reset Chat"):
        st.session_state.messages = []
        st.session_state.metrics = {"G": [], "E": [], "R": []}
        st.session_state.last_audio = None
        st.rerun()

# ================= 5. DASHBOARD =================
st.title("🇪🇸 Elite Spanish Professional Coach")

if st.session_state.metrics["G"]:
    cols = st.columns(3)
    avg_g = sum(st.session_state.metrics['G'])/len(st.session_state.metrics['G'])
    avg_e = sum(st.session_state.metrics['E'])/len(st.session_state.metrics['E'])
    avg_r = sum(st.session_state.metrics['R'])/len(st.session_state.metrics['R'])
    cols[0].metric("Grammar", f"{avg_g:.1f}/10")
    cols[1].metric("Empathy", f"{avg_e:.1f}/10")
    cols[2].metric("Result", f"{avg_r:.1f}/10")
    st.divider()

# ================= 6. CHAT HISTORY =================
for i, m in enumerate(st.session_state.messages):
    with st.chat_message(m["role"]):
        if "---" in m["content"]:
            parts = m["content"].split("---")
            text = parts[0].strip()
            coach = parts[1].strip()
            st.write(text)
            with st.expander("📝 Coaching & Scores"):
                st.write(coach)
            
            # If this is the most recent assistant message, show the audio player
            if i == len(st.session_state.messages) - 1 and m["role"] == "assistant" and st.session_state.last_audio:
                st.audio(st.session_state.last_audio, format="audio/mp3")
        else:
            st.write(m["content"])

# ================= 7. INPUT HANDLING =================
user_msg = None

# Audio Input Section
audio_input = st.audio_input("Respond in Spanish (Voice)")
if audio_input:
    # Check if this audio has already been processed to avoid loops
    audio_data = audio_input.getvalue()
    with st.spinner("Transcribing..."):
        try:
            # We use whisper-large-v3 for best Spanish accuracy
            res = client.audio.transcriptions.create(
                file=("speech.wav", audio_data), 
                model="whisper-large-v3", 
                language="es"
            )
            user_msg = res.text
        except Exception as e:
            st.error(f"Transcription failed: {e}")

# Text Input Fallback
text_input = st.chat_input("Type your response here...")
if text_input:
    user_msg = text_input

# ================= 8. AI PROCESSING =================
if user_msg:
    st.session_state.messages.append({"role": "user", "content": user_msg})
    
    with st.chat_message("assistant"):
        # Create history (clean out coaching for the LLM's memory)
        history = [{"role": m["role"], "content": m["content"].split("---")[0]} for m in st.session_state.messages[-6:]]
        
        try:
            # AI Logic
            model = "llama-3.3-70b-versatile"
            response = client.chat.completions.create(
                model=model, 
                messages=[{"role": "system", "content": get_system_prompt()}] + history
            )
            full_res = response.choices[0].message.content
            
            # Parsing Text and Coaching
            if "---" in full_res:
                txt_part, coach_part = full_res.split("---", 1)
            else:
                txt_part = full_res
                coach_part = "Coach: No specific feedback provided this turn."

            # UI Display
            st.write(txt_part.strip())
            
            # Generate TTS immediately
            tts_text = re.sub(r'[*#_~-]', '', txt_part) # Clean markdown
            tts = gTTS(text=tts_text, lang='es')
            audio_buffer = io.BytesIO()
            tts.write_to_fp(audio_buffer)
            st.session_state.last_audio = audio_buffer.getvalue()
            
            # Show the audio player immediately
            st.audio(st.session_state.last_audio, format="audio/mp3")
            
            with st.expander("📝 Coaching & Scores"):
                st.write(coach_part.strip())
            
            # Update metrics
            scores = re.findall(r'[GER]:\s*(\d+)', coach_part)
            if len(scores) >= 3:
                st.session_state.metrics["G"].append(int(scores[0]))
                st.session_state.metrics["E"].append(int(scores[1]))
                st.session_state.metrics["R"].append(int(scores[2]))
            
            # Save to history
            st.session_state.messages.append({"role": "assistant", "content": full_res})
            st.rerun()

        except Exception as e:
            st.error(f"Simulation Error: {e}")

# ================= 9. AUTO-START =================
if not st.session_state.messages:
    if "AI is Interviewer" in st.session_state.role:
        start = "Hola, bienvenido. He revisado su currículum. Para empezar, ¿por qué le interesa este puesto? --- COACH: Waiting for your response. | SCORES: G: 0, E: 0, R: 0"
    elif "AI is Customer" in st.session_state.role:
        start = "¡Hola! Estoy llamando porque tengo un problema grave y nadie me ayuda. ¿Me puede atender? --- COACH: Waiting for your response. | SCORES: G: 0, E: 0, R: 0"
    else:
        start = "Llamada conectada. El sistema está listo. --- COACH: Inicie la conversación. | SCORES: G: 0, E: 0, R: 0"
    
    st.session_state.messages.append({"role": "assistant", "content": start})
    st.rerun()
