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
if "role" not in st.session_state: st.session_state.role = "User as Applicant (AI is Interviewer)"

try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("GROQ_API_KEY is missing in secrets.")
    st.stop()

# ================= 3. PROMPTS =================
def get_sim_prompt():
    role = st.session_state.role
    scenario = st.session_state.scenario
    context = f"DOCS: {st.session_state.get('kb_content','')[:2000]}\nUSER_BIO: {st.session_state.get('res_content','')[:1500]}"
    
    if "AI is Applicant" in role:
        persona = "ACT AS: Rod (Job Applicant). Tone: Professional/Eager."
    elif "AI is Interviewer" in role:
        persona = "ACT AS: A Senior Executive Interviewer. Tone: Formal/Challenging."
    elif "AI is Customer" in role:
        persona = "ACT AS: A frustrated Business Client. Tone: Demanding/Direct."
    else:
        persona = "ACT AS: A high-end Corporate Liaison."

    return f"""
    {persona}
    SCENARIO: {scenario}
    KNOWLEDGE BASE: {context}
    STRICT RULE: Respond ONLY in Spanish. Stay in character 100%. 
    NEVER explain that you are an AI. NEVER provide translations.
    Keep responses short (1-3 sentences) to maintain conversation flow.
    """

def get_debrief_prompt(messages):
    transcript = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])
    return f"""
    You are the 'Elite Spanish Business Coach'. Analyze this transcript:
    {transcript}
    
    Provide a professional evaluation in English:
    1. **Executive Summary**: Did the user handle the situation effectively?
    2. **Grammar & Tone Corrections**: List specific Spanish mistakes and their professional corrections.
    3. **Sophisticated Alternatives**: Suggest 5 'Elite' business phrases they could have used.
    4. **Metric Scores**: 
       G Score: (number)/10
       E Score: (number)/10
       R Score: (number)/10
    """

def safe_chat_completion(messages):
    try:
        return client.chat.completions.create(model="llama-3.3-70b-versatile", messages=messages, temperature=0.7)
    except:
        return client.chat.completions.create(model="llama-3.1-8b-instant", messages=messages, temperature=0.7)

# ================= 4. SIDEBAR (CONFIG) =================
with st.sidebar:
    st.title("🏆 Coach Settings")
    
    with st.form("config_form"):
        st.subheader("1. Scenario Setup")
        new_role = st.selectbox("Mode", [
            "User as Applicant (AI is Interviewer)",
            "User as Interviewer (AI is Applicant)",
            "User as Agent (AI is Customer)",
            "User as Customer (AI is Agent)"
        ], index=0)
        new_scenario = st.text_area("Scenario Specifics", st.session_state.scenario, help="Type the details and press Update.")
        
        submit = st.form_submit_button("Update & Restart Session")
        if submit:
            st.session_state.role = new_role
            st.session_state.scenario = new_scenario
            st.session_state.messages = []
            st.session_state.phase = "simulating"
            st.session_state.final_report = None
            st.rerun()
    
    st.divider()
    st.subheader("2. Knowledge Upload")
    kb_files = st.file_uploader("Upload Company Info", accept_multiple_files=True)
    st.session_state.kb_content = extract_text(kb_files) if kb_files else ""
    
    res_files = st.file_uploader("Upload Your Resume", accept_multiple_files=True)
    st.session_state.res_content = extract_text(res_files) if res_files else ""

# ================= 5. HEADER CONTROL =================
h_col1, h_col2 = st.columns([3, 1])
with h_col1:
    status = "🟢 LIVE SIMULATION" if st.session_state.phase == "simulating" else "📊 EVALUATION"
    st.subheader(f"{status} | {st.session_state.role.split('(')[0]}")

with h_col2:
    if st.session_state.phase == "simulating":
        if st.button("🛑 END CALL & ANALYZE", type="primary", use_container_width=True):
            st.session_state.phase = "debrief"
            st.rerun()
    else:
        if st.button("🔄 NEW SESSION", use_container_width=True):
            st.session_state.messages = []
            st.session_state.phase = "simulating"
            st.session_state.final_report = None
            st.rerun()

st.divider()

# ================= 6. MAIN SIMULATION =================
if st.session_state.phase == "simulating":
    
    # Auto-Greeting Logic
    if not st.session_state.messages:
        with st.spinner("Connecting to coach..."):
            greeting_prompt = f"Based on the scenario '{st.session_state.scenario}', provide a short 1-sentence opening greeting in Spanish as the character."
            res = safe_chat_completion([{"role": "system", "content": get_sim_prompt()}, {"role": "user", "content": greeting_prompt}])
            st.session_state.messages.append({"role": "assistant", "content": res.choices[0].message.content})
            st.rerun()

    # Display History
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if "audio" in m: st.audio(m["audio"], format="audio/mp3")

    # Input Logic
    user_input = None
    
    # Audio Row
    audio_data = st.audio_input("Speak in Spanish")
    if audio_data:
        curr_id = hashlib.md5(audio_data.getvalue()).hexdigest()
        if curr_id != st.session_state.last_processed_id:
            with st.spinner("Listening..."):
                try:
                    res = client.audio.transcriptions.create(file=("f.wav", audio_data.getvalue()), model="whisper-large-v3", language="es")
                    user_input = res.text
                    st.session_state.last_processed_id = curr_id
                except: st.error("Audio processing failed.")

    # Text Input
    text_in = st.chat_input("Or type your Spanish response...")
    if text_in: user_input = text_in

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("assistant"):
            history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-10:]]
            response = safe_chat_completion([{"role": "system", "content": get_sim_prompt()}] + history)
            ans = response.choices[0].message.content
            
            # Voice Generation
            tts = gTTS(text=re.sub(r'[*#_~-]', '', ans), lang='es')
            buf = io.BytesIO()
            tts.write_to_fp(buf)
            st.session_state.messages.append({"role": "assistant", "content": ans, "audio": buf.getvalue()})
            st.rerun()

# ================= 7. DEBRIEF PHASE =================
else:
    if not st.session_state.final_report:
        with st.spinner("Elite Coach is evaluating your performance..."):
            report = safe_chat_completion([{"role": "user", "content": get_debrief_prompt(st.session_state.messages)}])
            st.session_state.final_report = report.choices[0].message.content

    # Robust Metric Extraction (Handles variations like "G Score: 8" or "G: 8")
    metrics = {"Grammar": 0, "Tone": 0, "Result": 0}
    scores = re.findall(r'(\d+)\s*/\s*10', st.session_state.final_report)
    if len(scores) >= 3:
        m1, m2, m3 = st.columns(3)
        m1.metric("Grammar Accuracy", f"{scores[0]}/10")
        m2.metric("Professional Tone", f"{scores[1]}/10")
        m3.metric("Goal Achievement", f"{scores[2]}/10")
    
    st.markdown("---")
    st.markdown(st.session_state.final_report)
    
    with st.expander("📄 View Full Call Transcript"):
        for m in st.session_state.messages:
            role_name = "COACH / PARTNER" if m["role"] == "assistant" else "YOU"
            st.write(f"**{role_name}:** {m['content']}")
