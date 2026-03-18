import streamlit as st
from groq import Groq
from gtts import gTTS
import tempfile
import os
import re
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup

# ================= 1. ROBUST FILE PROCESSING =================
def extract_text_from_file(uploaded_file):
    if uploaded_file is None: return ""
    ext = uploaded_file.name.split('.')[-1].lower()
    text = ""
    try:
        if ext == 'pdf':
            pdf_reader = PdfReader(uploaded_file)
            for page in pdf_reader.pages:
                text += page.extract_text() + " "
        elif ext == 'html':
            soup = BeautifulSoup(uploaded_file.read(), 'html.parser')
            text = soup.get_text()
        else:
            text = uploaded_file.read().decode("utf-8")
        
        # Cleanup: Remove excessive newlines and spaces to save tokens
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    except Exception as e:
        st.error(f"Error reading {uploaded_file.name}: {e}")
        return ""

# ================= 2. INITIALIZATION =================
st.set_page_config(page_title="Elite Spanish Pro", page_icon="🎙️", layout="wide")

if "messages" not in st.session_state: st.session_state.messages = []
if "metrics" not in st.session_state: st.session_state.metrics = {"Grammar": 0, "Empathy": 0, "Resolution": 0, "Turns": 0}
if "kb_content" not in st.session_state: st.session_state.kb_content = ""
if "resume_content" not in st.session_state: st.session_state.resume_content = ""

try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("Missing GROQ_API_KEY in Streamlit Secrets.")
    st.stop()

# ================= 3. SYSTEM PROMPT ENGINE =================
def build_system_prompt():
    role = st.session_state.get('role_mode', 'User as Applicant')
    scenario = st.session_state.get('scenario_text', 'General Interview')
    level = st.session_state.get('target_level', 'B2')
    kb = st.session_state.kb_content
    resume = st.session_state.resume_content

    # Structured prompt for high AI attention
    return f"""
    ### CORE CONTEXT
    - **ROLE**: {role}
    - **SPANISH LEVEL**: {level}
    - **SCENARIO**: {scenario}

    ### DATA INJECTION (READ THIS FIRST)
    - **USER RESUME**: {resume if resume else "No resume provided."}
    - **COMPANY/PRODUCT INFO**: {kb if kb else "No company info provided."}

    ### INSTRUCTIONS
    1. If role is 'AI is Interviewer', use the RESUME to ask specific, challenging questions. Mention their past experience.
    2. Respond strictly in character first.
    3. Then provide feedback after the separator '---COACH---'.

    ### OUTPUT SCHEMA
    [Dialogue in Spanish]
    ---COACH---
    **Feedback:** (Mistakes, Better Vocab)
    **Score:** (Grammar: X/10, Empathy: X/10, Resolution: X/10)
    """

# ================= 4. SIDEBAR =================
with st.sidebar:
    st.title("🛡️ Setup Center")
    st.session_state.role_mode = st.selectbox("Roleplay Mode", [
        "User as Applicant (AI is Interviewer)",
        "User as Interviewer (AI is Applicant)",
        "User as Agent (AI is Customer)",
        "User as Customer (AI is Agent)"
    ])
    st.session_state.target_level = st.select_slider("Target Level", ["A2", "B1", "B2", "C1", "C2"])
    st.session_state.scenario_text = st.text_area("Define Scenario", "Practice a job interview for a call center position.")

    st.divider()
    kb_file = st.file_uploader("Upload Company/Product Info (PDF/HTML)", type=['pdf', 'html', 'txt'])
    if kb_file:
        st.session_state.kb_content = extract_text_from_file(kb_file)
        st.success(f"Loaded {len(st.session_state.kb_content)} chars of Company Data")

    res_file = st.file_uploader("Upload Your Resume (PDF/HTML)", type=['pdf', 'html', 'txt'])
    if res_file:
        st.session_state.resume_content = extract_text_from_file(res_file)
        st.success(f"Loaded {len(st.session_state.resume_content)} chars of Resume Data")

    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.session_state.metrics = {"Grammar": 0, "Empathy": 0, "Resolution": 0, "Turns": 0}
        st.rerun()

# ================= 5. MAIN CHAT & FALLBACK LOGIC =================
st.title("🚀 Elite BPO & Interview Coach")

# Display Stats
if st.session_state.metrics["Turns"] > 0:
    t = st.session_state.metrics["Turns"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Grammar", f"{round(st.session_state.metrics['Grammar']/t, 1)}/10")
    c2.metric("Empathy", f"{round(st.session_state.metrics['Empathy']/t, 1)}/10")
    c3.metric("Goal", f"{round(st.session_state.metrics['Resolution']/t, 1)}/10")

# History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "---COACH---" in msg["content"]:
            txt, coach = msg["content"].split("---COACH---")
            st.markdown(txt)
            with st.expander("📝 Feedback"): st.markdown(coach)
        else:
            st.markdown(msg["content"])

# --- INPUT SECTION ---
user_input = None
audio_in = st.audio_input("Speak Spanish")
text_in = st.chat_input("Type your response...")

if audio_in:
    with st.spinner("Listening..."):
        try:
            transcript = client.audio.transcriptions.create(
                file=("audio.wav", audio_in.getvalue()),
                model="whisper-large-v3",
                language="es"
            )
            user_input = transcript.text
        except Exception as e:
            st.error(f"Transcription failed: {e}")

if text_in: user_input = text_in

# --- PROCESSING ---
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"): st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("AI is thinking..."):
            history = [{"role": m["role"], "content": m["content"].split("---COACH---")[0]} for m in st.session_state.messages[-6:]]
            
            # MODEL FALLBACK LOGIC
            full_reply = ""
            models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
            
            for model_name in models:
                try:
                    res = client.chat.completions.create(
                        model=model_name,
                        messages=[{"role": "system", "content": build_system_prompt()}] + history
                    )
                    full_reply = res.choices[0].message.content
                    break # Success!
                except Exception as e:
                    if "rate_limit" in str(e).lower() and model_name != models[-1]:
                        st.warning(f"70B Model Busy. Switching to faster 8B engine...")
                        continue
                    else:
                        st.error(f"Error: {e}")
                        st.stop()

            # UI Rendering
            if "---COACH---" in full_reply:
                dialogue, coach = full_reply.split("---COACH---")
                st.markdown(dialogue.strip())
                
                # Audio out
                try:
                    tts = gTTS(text=re.sub(r'[*#_~-]', '', dialogue), lang='es')
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                        tts.save(fp.name)
                        st.audio(fp.name)
                except: pass
                
                with st.expander("📝 Feedback"): st.markdown(coach)
                
                # Update Score logic
                scores = re.findall(r'\d+', coach)
                if len(scores) >= 3:
                    st.session_state.metrics["Grammar"] += int(scores[0])
                    st.session_state.metrics["Empathy"] += int(scores[1])
                    st.session_state.metrics["Resolution"] += int(scores[2])
                    st.session_state.metrics["Turns"] += 1
            else:
                st.markdown(full_reply)
            
            st.session_state.messages.append({"role": "assistant", "content": full_reply})
            st.rerun()
