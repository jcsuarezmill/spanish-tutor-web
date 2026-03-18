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
                combined_text += f"\n[DOC: {uploaded_file.name}]\n"
                combined_text += " ".join([p.extract_text() or "" for p in reader.pages])
            elif ext in ['html', 'htm']:
                combined_text += BeautifulSoup(uploaded_file.read(), 'html.parser').get_text()
            else:
                combined_text += uploaded_file.read().decode("utf-8")
        except Exception as e:
            st.error(f"Error reading {uploaded_file.name}: {e}")
    return combined_text

# ================= 2. SETUP & STATE =================
st.set_page_config(page_title="Elite Spanish Coach v2", layout="wide", page_icon="🇪🇸")

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

# ================= 3. ELITE DUAL-COACH PROMPT =================
def get_system_prompt():
    role = st.session_state.get('role', 'AI is Applicant')
    scenario = st.session_state.get('scenario', 'Job Interview')
    context = f"DOCS: {st.session_state.kb_content[:2000]}\nUSER_DATA: {st.session_state.res_content[:2000]}"
    
    return f"""
    ACT AS: A Professional Spanish Language Coach and {role}.
    SCENARIO: {scenario}
    CONTEXT: {context}

    YOUR GOAL: 
    1. Respond naturally in Spanish to the user.
    2. Provide a 'DUAL COACHING' block.
    
    DUAL COACHING RULES:
    - USER ANALYSIS: Correct the user's Spanish. Point out 'Anglicisms' (English-style phrasing). Check if they mixed 'Tú' and 'Usted'.
    - AI ANALYSIS: Explain why the AI's response used specific professional vocabulary. 
    - PHONETIC TIP: Give one tip on how to pronounce a difficult word in the response.

    STRICT FORMAT:
    [Character Response in Spanish]
    ---
    ### 🧠 COACHING INSIGHTS
    **Your Spanish:** (Detailed corrections of user's last message)
    **AI Strategy:** (Explanation of professional terms used in the response)
    **Vocabulary Boost:** (3 key words/phrases to learn from this turn)
    **SCORES:** G: (1-10), E: (1-10), R: (1-10)
    """

# ================= 4. SIDEBAR =================
with st.sidebar:
    st.title("🏆 Coaching Settings")
    st.session_state.role = st.selectbox("Role-play Mode", [
        "User as Interviewer (AI is Applicant)",
        "User as Applicant (AI is Interviewer)",
        "User as Agent (AI is Customer)",
        "User as Customer (AI is Agent)"
    ])
    st.session_state.scenario = st.text_input("Scenario Context", "Standard Interview")
    
    with st.expander("📂 Import Documents (Unlimited)"):
        kb_files = st.file_uploader("Upload SOPs/Company Data", accept_multiple_files=True, type=['pdf', 'txt', 'html'])
        if kb_files: st.session_state.kb_content = extract_text_from_multiple(kb_files)
        
        res_files = st.file_uploader("Upload Resumes/Background", accept_multiple_files=True, type=['pdf', 'txt', 'html'])
        if res_files: st.session_state.res_content = extract_text_from_multiple(res_files)

    if st.button("🗑️ Reset Coaching Session", use_container_width=True):
        st.session_state.messages = []
        st.session_state.metrics = {"G": [], "E": [], "R": []}
        st.session_state.audio_store = {}
        st.rerun()

# ================= 5. MAIN DASHBOARD =================
st.title("🇪🇸 Elite Spanish Professional Coach")

if st.session_state.metrics["G"]:
    m1, m2, m3 = st.columns(3)
    avg = lambda x: sum(st.session_state.metrics[x])/len(st.session_state.metrics[x])
    m1.metric("Grammar Accuracy", f"{avg('G'):.1f}/10")
    m2.metric("Professional Empathy", f"{avg('E'):.1f}/10")
    m3.metric("Goal Result", f"{avg('R'):.1f}/10")

# Render Chat with Persistent Audio
for i, m in enumerate(st.session_state.messages):
    with st.chat_message(m["role"]):
        if "---" in m["content"]:
            txt, coach = m["content"].split("---", 1)
            st.markdown(f"#### {txt.strip()}")
            with st.expander("📝 View Detailed Coaching", expanded=True):
                st.markdown(coach.strip())
            
            # Retrieve persistent audio from store
            if i in st.session_state.audio_store:
                st.audio(st.session_state.audio_store[i], format="audio/mp3")
        else:
            st.write(m["content"])

# ================= 6. INPUT ENGINE =================
user_input = None

# Audio Checksum to prevent looping
audio_data = st.audio_input("Speak in Spanish")
if audio_data:
    current_hash = hashlib.md5(audio_data.getvalue()).hexdigest()
    if current_hash != st.session_state.last_processed_hash:
        with st.spinner("Analyzing audio..."):
            try:
                res = client.audio.transcriptions.create(
                    file=("file.wav", audio_data.getvalue()),
                    model="whisper-large-v3",
                    language="es"
                )
                user_input = res.text
                st.session_state.last_processed_hash = current_hash
            except: st.error("Transcription error.")

text_in = st.chat_input("Type your response...")
if text_in: user_input = text_in

# ================= 7. RESPONSE & DUAL COACHING ENGINE =================
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    with st.chat_message("assistant"):
        # Create history (strip coaching for AI context)
        history = [{"role": m["role"], "content": m["content"].split("---")[0]} for m in st.session_state.messages[-10:]]
        
        try:
            # AI logic with fallback
            try:
                model = "llama-3.3-70b-versatile"
                resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": get_system_prompt()}] + history, temperature=0.5)
            except:
                model = "llama-3.1-8b-instant"
                resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": get_system_prompt()}] + history)
            
            full_res = resp.choices[0].message.content
            
            if "---" in full_res:
                txt_only, coach_only = full_res.split("---", 1)
                st.markdown(f"#### {txt_only.strip()}")
                
                # Generate & Store Audio
                tts = gTTS(text=re.sub(r'[*#_~-]', '', txt_only), lang='es')
                buf = io.BytesIO()
                tts.write_to_fp(buf)
                msg_idx = len(st.session_state.messages)
                st.session_state.audio_store[msg_idx] = buf.getvalue()
                st.audio(st.session_state.audio_store[msg_idx], format="audio/mp3")
                
                with st.expander("📝 View Detailed Coaching", expanded=True):
                    st.markdown(coach_only.strip())
                
                # Metric tracking
                scores = re.findall(r'[GER]:\s*(\d+\.?\d*)', coach_only)
                if len(scores) >= 3:
                    st.session_state.metrics["G"].append(float(scores[0]))
                    st.session_state.metrics["E"].append(float(scores[1]))
                    st.session_state.metrics["R"].append(float(scores[2]))
            else:
                st.write(full_res)
            
            st.session_state.messages.append({"role": "assistant", "content": full_res})
            st.rerun()

        except Exception as e:
            st.error(f"Error: {e}")

# ================= 8. STARTUP = : No Initial Coaching =================
if not st.session_state.messages:
    intro = "Llamada conectada. El sistema está listo. Por favor, inicie la conversación cuando guste."
    st.session_state.messages.append({"role": "assistant", "content": intro})
    st.rerun()
