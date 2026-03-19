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
if "phase" not in st.session_state: st.session_state.phase = "simulating" 
if "last_processed_id" not in st.session_state: st.session_state.last_processed_id = ""
if "final_report" not in st.session_state: st.session_state.final_report = None
if "scenario" not in st.session_state: st.session_state.scenario = "Job Interview for Virtual Assistant"

try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("GROQ_API_KEY is missing in secrets.")
    st.stop()

# ================= 3. PROMPTS =================
def get_sim_prompt():
    role = st.session_state.get('role', 'User as Applicant')
    scenario = st.session_state.scenario
    context = f"DOCS: {st.session_state.get('kb_content','')[:2000]}\nUSER: {st.session_state.get('res_content','')[:1500]}"
    
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
    STRICT RULE: Respond ONLY in Spanish. NEVER provide coaching or English during the chat.
    Keep it realistic and concise.
    """

def get_debrief_prompt(messages):
    transcript = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])
    return f"""
    You are the 'Elite Spanish Business Coach'. Analyze this transcript:
    {transcript}
    
    Provide:
    1. Outcome: Did the user succeed in the scenario?
    2. Grammar: Top 3 specific errors and corrections.
    3. Power Words: 5 high-level business terms to use instead.
    4. Scores: G: (1-10), E: (1-10), R: (1-10)
    """

def safe_chat_completion(messages):
    try:
        return client.chat.completions.create(model="llama-3.3-70b-versatile", messages=messages)
    except:
        return client.chat.completions.create(model="llama-3.1-8b-instant", messages=messages)

# ================= 4. SIDEBAR (CONFIG) =================
with st.sidebar:
    st.title("⚙️ Configuration")
    
    # SCENARIO FORM (Pressing Enter here resets the session with the new scenario)
    with st.form("scenario_form"):
        new_role = st.selectbox("Your Role", [
            "User as Interviewer (AI is Applicant)",
            "User as Applicant (AI is Interviewer)",
            "User as Agent (AI is Customer)",
            "User as Customer (AI is Agent)"
        ])
        new_scenario = st.text_input("Scenario (Press Enter to Apply)", st.session_state.scenario)
        submit_scenario = st.form_submit_button("Update & Restart Session")
        
        if submit_scenario:
            st.session_state.role = new_role
            st.session_state.scenario = new_scenario
            st.session_state.messages = []
            st.session_state.phase = "simulating"
            st.session_state.final_report = None
            st.rerun()
    
    st.divider()
    st.subheader("📂 Context Files")
    kb_files = st.file_uploader("Company SOPs", accept_multiple_files=True)
    st.session_state.kb_content = extract_text(kb_files) if kb_files else ""
    res_files = st.file_uploader("Your Resume", accept_multiple_files=True)
    st.session_state.res_content = extract_text(res_files) if res_files else ""

# ================= 5. TOP CONTROL BAR =================
# This is the "Intuitive Area" for ending the call
header_col1, header_col2 = st.columns([4, 1])
with header_col1:
    if st.session_state.phase == "simulating":
        st.markdown(f"### 🟢 Live Session: *{st.session_state.scenario}*")
    else:
        st.markdown("### 📊 Performance Review")

with header_col2:
    if st.session_state.phase == "simulating":
        if st.button("🛑 END CALL", type="primary", use_container_width=True):
            st.session_state.phase = "debrief"
            st.rerun()
    else:
        if st.button("🔄 RESTART", use_container_width=True):
            st.session_state.messages = []
            st.session_state.phase = "simulating"
            st.session_state.final_report = None
            st.rerun()

st.divider()

# ================= 6. MAIN INTERACTION =================
if st.session_state.phase == "simulating":
    # Greeting Logic
    if not st.session_state.messages:
        role_type = st.session_state.get('role', '')
        if "AI is Interviewer" in role_type: greeting = "Bienvenido. He revisado su perfil. ¿Podemos comenzar?"
        elif "AI is Applicant" in role_type: greeting = "Hola, mucho gusto. Gracias por la oportunidad. ¿Gusta empezar?"
        else: greeting = "Hola, ¿en qué puedo ayudarle hoy?"
        st.session_state.messages.append({"role": "assistant", "content": greeting})

    # Display History
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if "audio" in m: st.audio(m["audio"], format="audio/mp3")

    # Input handling
    user_input = None
    
    # Audio Input
    audio_data = st.audio_input("Respond in Spanish")
    if audio_data:
        curr_id = hashlib.md5(audio_data.getvalue()).hexdigest()
        if curr_id != st.session_state.last_processed_id:
            with st.spinner("Transcribing..."):
                res = client.audio.transcriptions.create(file=("f.wav", audio_data.getvalue()), model="whisper-large-v3", language="es")
                user_input = res.text
                st.session_state.last_processed_id = curr_id

    # Text Input
    text_in = st.chat_input("Type your Spanish response...")
    if text_in: user_input = text_in

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("assistant"):
            history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-10:]]
            response = safe_chat_completion([{"role": "system", "content": get_sim_prompt()}] + history)
            ans = response.choices[0].message.content
            
            # Audio Generation
            tts = gTTS(text=re.sub(r'[*#_~-]', '', ans), lang='es')
            buf = io.BytesIO()
            tts.write_to_fp(buf)
            st.session_state.messages.append({"role": "assistant", "content": ans, "audio": buf.getvalue()})
            st.rerun()

# ================= 7. DEBRIEF UI =================
else:
    if not st.session_state.final_report:
        with st.spinner("Coach is reviewing the transcript..."):
            report = safe_chat_completion([{"role": "user", "content": get_debrief_prompt(st.session_state.messages)}])
            st.session_state.final_report = report.choices[0].message.content

    # Metrics
    scores = re.findall(r'[GER]:\s*(\d+)', st.session_state.final_report)
    if len(scores) >= 3:
        m1, m2, m3 = st.columns(3)
        m1.metric("Grammar", f"{scores[0]}/10")
        m2.metric("Tone/Presence", f"{scores[1]}/10")
        m3.metric("Goal Success", f"{scores[2]}/10")
    
    st.markdown("---")
    st.markdown(st.session_state.final_report)
    
    with st.expander("Review Conversation Transcript"):
        for m in st.session_state.messages:
            st.write(f"**{m['role'].upper()}:** {m['content']}")
