import streamlit as st
from groq import Groq
from gtts import gTTS
import tempfile
import os

# ================= CONFIGURATION =================
st.set_page_config(page_title="Elite Spanish Coach Pro", page_icon="💼", layout="wide")

st.markdown("""
    <style>
    .stChatMessage { border-radius: 12px; margin-bottom: 15px; border: 1px solid #f0f2f6; }
    .coach-box { 
        background-color: #f0f7ff; padding: 18px; border-radius: 10px; 
        border-left: 6px solid #007bff; margin-top: 10px; color: #1e3a8a;
    }
    .golden-phrase { color: #d97706; font-weight: bold; font-style: italic; }
    </style>
""", unsafe_allow_html=True)

# API Setup
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("⚠️ Please set GROQ_API_KEY in Streamlit Secrets.")
    st.stop()

# ================= SESSION STATE =================
if "messages" not in st.session_state: st.session_state.messages = []
if "level" not in st.session_state: st.session_state.level = "B2"
if "track" not in st.session_state: st.session_state.track = "General Support"
if "custom_scenario" not in st.session_state: st.session_state.custom_scenario = ""
if "widget_key" not in st.session_state: st.session_state.widget_key = 0

# ================= PROMPT ENGINE =================

def get_bpo_system_prompt():
    # Use custom scenario if provided, otherwise use the track
    base_scenario = st.session_state.custom_scenario if st.session_state.custom_scenario else st.session_state.track
    
    return (
        f"SCENARIO: {base_scenario}. PROFICIENCY: {st.session_state.level}. "
        "YOUR ROLE: You are the person the user is calling. Respond naturally in Spanish.\n"
        "COACHING ROLE: After your response, provide a professional critique.\n"
        "RULES:\n"
        "1. Dialogue must be 100% Spanish.\n"
        "2. Use '---' as a separator.\n"
        "3. After '---', provide 'COACH'S CORNER' in English with:\n"
        "   - Corrections: [Grammar/Vocabulary fixes]\n"
        "   - Better Way to Say It: [Provide a high-level BPO 'Golden Phrase']\n"
        "   - Tone & Professionalism: [Critique their soft skills]"
    )

def generate_tts(text):
    try:
        spanish_text = text.split("---")[0].strip()
        tts = gTTS(text=spanish_text, lang='es')
        fp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(fp.name)
        return fp.name
    except: return None

# ================= SIDEBAR =================
with st.sidebar:
    st.title("💼 BPO/VA Trainer")
    
    st.session_state.level = st.select_slider("Select Your Goal Level", ["A1", "A2", "B1", "B2", "C1", "C2"], value=st.session_state.level)
    
    st.session_state.track = st.selectbox("Standard Tracks", 
        ["General Support", "Medical VA", "Real Estate VA", "Tech Support", "Executive VA"])
    
    st.divider()
    st.subheader("🛠️ Custom Scenario")
    st.session_state.custom_scenario = st.text_area("Example: 'I am a VA calling to confirm a package delivery'...", height=100)
    
    if st.button("🗑️ Reset Coaching Session", use_container_width=True):
        st.session_state.messages = []
        st.session_state.widget_key += 1
        st.rerun()

# ================= MAIN UI =================
st.title("🇪🇸 Elite Spanish Professional Coach")
st.caption(f"Currently practicing: {st.session_state.custom_scenario if st.session_state.custom_scenario else st.session_state.track}")

# Display Messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "---" in msg["content"]:
            parts = msg["content"].split("---")
            st.markdown(parts[0]) # The Character
            st.markdown(f"<div class='coach-box'><b>👨‍🏫 Coach's Corner</b><br>{parts[1]}</div>", unsafe_allow_html=True)
        else:
            st.markdown(msg["content"])
        if "audio" in msg: st.audio(msg["audio"])

# ================= INPUT PROCESSING =================

# TEXT INPUT
user_query = st.chat_input("Respond in Spanish...")

# AUDIO INPUT
audio_data = st.audio_input("Record your voice", key=f"audio_input_{st.session_state.widget_key}")

final_input = None

if audio_data:
    with st.spinner("🎧 Analyzing Speech..."):
        try:
            transcription = client.audio.transcriptions.create(
                file=("speech.wav", audio_data.getvalue()),
                model="whisper-large-v3",
                language="es",
                response_format="text"
            )
            if transcription.strip():
                final_input = transcription
        except Exception as e:
            st.error(f"Mic Error: {e}")

if user_query:
    final_input = user_query

# PROCESS ENGINE
if final_input:
    st.session_state.messages.append({"role": "user", "content": final_input})
    
    with st.chat_message("assistant"):
        with st.spinner("Coach is reviewing..."):
            # Use 3.1-70b for better rate limit management
            clean_history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-6:]]
            
            try:
                response = client.chat.completions.create(
                    model="llama-3.1-70b-versatile",
                    messages=[{"role": "system", "content": get_bpo_system_prompt()}] + clean_history,
                    temperature=0.7
                )
                ai_text = response.choices[0].message.content
                audio_path = generate_tts(ai_text)
                
                st.session_state.messages.append({"role": "assistant", "content": ai_text, "audio": audio_path})
            except Exception as e:
                st.error(f"Rate Limit or API Error. Please wait 1 minute. Detail: {e}")
            
    st.session_state.widget_key += 1
    st.rerun()
