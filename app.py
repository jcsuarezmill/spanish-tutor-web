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

# Initialize Session States
if "messages" not in st.session_state: st.session_state.messages = []
if "phase" not in st.session_state: st.session_state.phase = "simulating" # Options: simulating, debrief
if "last_processed_id" not in st.session_state: st.session_state.last_processed_id = ""
if "final_report" not in st.session_state: st.session_state.final_report = None

try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("GROQ_API_KEY is missing in secrets.")
    st.stop()

# ================= 3. PROMPTS =================
def get_sim_prompt():
    role = st.session_state.get('role', 'User as Applicant')
    scenario = st.session_state.get('scenario', 'Job Interview')
    context = f"DOCS: {st.session_state.get('kb_content','')[:2000]}\nUSER: {st.session_state.get('res_content','')[:1500]}"
    
    # Persona mapping
    if "AI is Applicant" in role:
        persona = "ACT AS: Rod Salmeo (Job Applicant). Tone: Professional/Polite."
    elif "AI is Interviewer" in role:
        persona = "ACT AS: A strict but fair Professional Interviewer."
    elif "AI is Customer" in role:
        persona = "ACT AS: A frustrated but reasonable Customer."
    else:
        persona = "ACT AS: A high-end Corporate Agent."

    return f"""
    {persona}
    SCENARIO: {scenario}
    DOCUMENT CONTEXT: {context}
    STRICT RULE: You are in a LIVE conversation. Respond ONLY in Spanish as this character. 
    NEVER provide coaching, English translations, or feedback during this phase.
    Keep responses concise and realistic to a spoken conversation.
    """

def get_debrief_prompt(messages):
    # Format the transcript for the coach
    transcript = ""
    for m in messages:
        role_label = "Student" if m["role"] == "user" else "AI Partner"
        transcript += f"{role_label}: {m['content']}\n"

    return f"""
    You are the 'Elite Spanish Business Coach'. Analyze this full transcript:
    ---
    {transcript}
    ---
    Provide a high-end Executive Debrief in English:
    
    1. **Outcome**: Did the student achieve the goal? (e.g., Did they get the job / solve the customer issue?)
    2. **Grammar & Syntax**: Identify the 3 most frequent or critical Spanish errors. Provide the correction.
    3. **Tone & Executive Presence**: Evaluate if their Spanish sounded 'Professional' vs 'Casual'. 
    4. **Vocabulary Expansion**: List 5 'Power Words' in Spanish they could have used to sound more sophisticated.
    5. **Final Scores**: 
       G: (1-10) - Grammar
       E: (1-10) - Professional Empathy/Tone
       R: (1-10) - Results/Communication Effectiveness
    """

def safe_chat_completion(messages, model="llama-3.3-70b-versatile"):
    try:
        return client.chat.completions.create(model=model, messages=messages)
    except Exception:
        # Fallback to smaller model if rate limited
        return client.chat.completions.create(model="llama-3.1-8b-instant", messages=messages)

# ================= 4. SIDEBAR =================
with st.sidebar:
    st.title("🏆 Coach Settings")
    
    if st.session_state.phase == "simulating":
        st.session_state.role = st.selectbox("Your Role", [
            "User as Interviewer (AI is Applicant)",
            "User as Applicant (AI is Interviewer)",
            "User as Agent (AI is Customer)",
            "User as Customer (AI is Agent)"
        ])
        st.session_state.scenario = st.text_input("Scenario", "Job Interview for Virtual Assistant")
        
        st.divider()
        kb_files = st.file_uploader("Upload SOPs / Job Desc", accept_multiple_files=True)
        st.session_state.kb_content = extract_text(kb_files) if kb_files else ""
            
        res_files = st.file_uploader("Upload Your Resume", accept_multiple_files=True)
        st.session_state.res_content = extract_text(res_files) if res_files else ""
        
        st.divider()
        if st.button("🛑 END CALL & ANALYZE", type="primary", use_container_width=True):
            st.session_state.phase = "debrief"
            st.rerun()
    else:
        st.success("Simulation Ended")
        if st.button("🔄 Start New Session", use_container_width=True):
            st.session_state.messages = []
            st.session_state.phase = "simulating"
            st.session_state.final_report = None
            st.rerun()

# ================= 5. MAIN UI (SIMULATION) =================
st.title("🇪🇸 Elite Spanish Professional Coach")

if st.session_state.phase == "simulating":
    # Show Chat History
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if "audio" in m: st.audio(m["audio"], format="audio/mp3")

    # Input Handling
    user_input = None
    
    # Audio Row
    audio_data = st.audio_input("Speak Spanish")
    if audio_data:
        current_id = hashlib.md5(audio_data.getvalue()).hexdigest()
        if current_id != st.session_state.last_processed_id:
            with st.spinner("Transcribing..."):
                try:
                    res = client.audio.transcriptions.create(
                        file=("file.wav", audio_data.getvalue()),
                        model="whisper-large-v3", language="es"
                    )
                    user_input = res.text
                    st.session_state.last_processed_id = current_id
                except: st.error("Transcription failed.")

    # Text Input
    text_in = st.chat_input("Type your response in Spanish...")
    if text_in: user_input = text_in

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("assistant"):
            # Only send the last 10 messages for context to keep it fast
            history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-10:]]
            
            try:
                response = safe_chat_completion([{"role": "system", "content": get_sim_prompt()}] + history)
                ans = response.choices[0].message.content
                
                # TTS
                tts = gTTS(text=re.sub(r'[*#_~-]', '', ans), lang='es')
                audio_buf = io.BytesIO()
                tts.write_to_fp(audio_buf)
                
                st.session_state.messages.append({"role": "assistant", "content": ans, "audio": audio_buf.getvalue()})
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

# ================= 6. MAIN UI (DEBRIEF) =================
else:
    st.header("📊 Executive Performance Report")
    
    if not st.session_state.final_report:
        with st.spinner("Analyzing your entire conversation..."):
            report_res = safe_chat_completion([
                {"role": "user", "content": get_debrief_prompt(st.session_state.messages)}
            ])
            st.session_state.final_report = report_res.choices[0].message.content
    
    # Visual metrics extraction
    scores = re.findall(r'[GER]:\s*(\d+)', st.session_state.final_report)
    if len(scores) >= 3:
        c1, c2, c3 = st.columns(3)
        c1.metric("Grammar Accuracy", f"{scores[0]}/10")
        c2.metric("Professional Tone", f"{scores[1]}/10")
        c3.metric("Goal Achievement", f"{scores[2]}/10")
    
    st.markdown("---")
    st.markdown(st.session_state.final_report)
    
    with st.expander("See Full Transcript"):
        for m in st.session_state.messages:
            st.write(f"**{m['role'].upper()}:** {m['content']}")

# ================= 7. STARTUP =================
if not st.session_state.messages:
    # Set the initial greeting based on mode
    greeting = "Hola. ¿Podemos comenzar?" 
    if "AI is Interviewer" in st.session_state.get('role', ''):
        greeting = "Bienvenido. Gracias por venir. Para empezar, ¿podría hablarme un poco de su experiencia?"
    elif "AI is Applicant" in st.session_state.get('role', ''):
        greeting = "Hola, mucho gusto. Soy el candidato para el puesto. ¿Gusta que comencemos con la entrevista?"
    
    st.session_state.messages.append({"role": "assistant", "content": greeting})
    st.rerun()
