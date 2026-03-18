import streamlit as st
from groq import Groq
from gtts import gTTS
import tempfile
import os

# ================= 1. UI CONFIGURATION =================
st.set_page_config(page_title="Elite Spanish Coach", page_icon="🇪🇸", layout="wide")

# Professional Styling
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stChatMessage { border-radius: 15px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .coach-card { 
        background-color: #ffffff; 
        border-left: 6px solid #10a37f; 
        padding: 20px; 
        border-radius: 10px; 
        margin-top: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .golden-phrase { color: #d97706; font-weight: 700; font-size: 1.1rem; }
    .status-text { font-size: 0.85rem; color: #666; font-style: italic; }
    </style>
""", unsafe_allow_html=True)

# API Initialization
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("🔑 API Key Missing. Please add GROQ_API_KEY to your Secrets.")
    st.stop()

# ================= 2. SESSION STATE (MEMORY) =================
if "messages" not in st.session_state: st.session_state.messages = []
if "level" not in st.session_state: st.session_state.level = "B2"
if "scenario" not in st.session_state: st.session_state.scenario = "General BPO Support"
if "reset_key" not in st.session_state: st.session_state.reset_key = 0

# ================= 3. CORE ENGINES =================

def get_ai_response(user_input):
    """Fetches response from Groq with high-level BPO prompting."""
    
    # Sanitize history for API (Only role and content)
    history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-6:]]
    
    system_prompt = f"""
    ROLE: You are a professional Spanish BPO/VA Coach. 
    SCENARIO: {st.session_state.scenario}. 
    USER LEVEL: {st.session_state.level}.

    STRICT OUTPUT FORMAT:
    [Spanish Response]
    ---
    ### 👨‍🏫 COACH'S FEEDBACK
    **Grammar Fix:** (Correct the user's Spanish)
    **The Golden Phrase:** (The professional BPO/VA industry-standard way to say that)
    **Soft Skills Tip:** (Advice on tone, empathy, or professional pace)
    """

    try:
        # Fallback logic: Try 70b first, then 8b if rate limited
        model_to_use = "llama-3.1-70b-versatile" 
        completion = client.chat.completions.create(
            model=model_to_use,
            messages=[{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": user_input}],
            temperature=0.7
        )
        return completion.choices[0].message.content
    except Exception as e:
        if "429" in str(e):
            return "⚠️ **COACH BUSY:** Rate limit reached. Please wait 30 seconds or refresh."
        return f"⚠️ **Error:** {str(e)}"

def speak(text):
    """Converts the Spanish dialogue to audio."""
    try:
        spanish_dialogue = text.split("---")[0].strip()
        tts = gTTS(text=spanish_dialogue, lang='es')
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            tts.save(fp.name)
            return fp.name
    except: return None

# ================= 4. SIDEBAR (CONTROLS) =================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3898/3898834.png", width=80)
    st.title("Spanish BPO Pro")
    
    st.subheader("🎯 Training Setup")
    st.session_state.level = st.select_slider("My Level", ["A1", "A2", "B1", "B2", "C1", "C2"], value=st.session_state.level)
    
    st.session_state.scenario = st.selectbox("Industry Track", 
        ["General BPO Support", "Medical VA", "Real Estate VA", "Tech Support Call", "Hiring Interview", "CUSTOM SCENARIO"])
    
    if st.session_state.scenario == "CUSTOM SCENARIO":
        st.session_state.scenario = st.text_area("Describe your scenario:", "I am a travel agent helping a client with a missed flight.")

    st.divider()
    if st.button("🔄 Restart Training Session", use_container_width=True):
        st.session_state.messages = []
        st.session_state.reset_key += 1
        st.rerun()

    st.warning("💡 **Ad-Blocker Detected?** If you don't hear audio, please disable ad-blockers for this site.")

# ================= 5. MAIN CHAT INTERFACE =================
st.title("💼 Elite Spanish BPO & VA Coach")
st.info(f"**Current Task:** {st.session_state.scenario} | **Level:** {st.session_state.level}")

# Display Chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "---" in msg["content"]:
            parts = msg["content"].split("---")
            st.markdown(f"**🗣️ Persona:** {parts[0]}")
            st.markdown(f"<div class='coach-card'>{parts[1]}</div>", unsafe_allow_html=True)
        else:
            st.markdown(msg["content"])
        if "audio" in msg: st.audio(msg["audio"])

# Input Section
input_col, mic_col = st.columns([0.8, 0.2])

with mic_col:
    # Key-switching forces the mic to reset and prevents the infinite loop bug
    audio_val = st.audio_input("Record", key=f"mic_{st.session_state.reset_key}")

with input_col:
    text_val = st.chat_input("Or type your response here...")

final_user_input = None

# Handle Audio Transcription
if audio_val:
    with st.status("👂 Listening and Transcribing...", expanded=False):
        try:
            transcript = client.audio.transcriptions.create(
                file=("input.wav", audio_val.getvalue()),
                model="whisper-large-v3",
                language="es",
                response_format="text"
            )
            final_user_input = transcript
        except Exception as e:
            st.error(f"Mic Error: {e}")

# Handle Text Input
if text_val:
    final_user_input = text_val

# ================= 6. THE RESPONSE ENGINE =================
if final_user_input:
    # 1. Add User input to UI
    st.session_state.messages.append({"role": "user", "content": final_user_input})
    
    # 2. Process AI
    with st.chat_message("assistant"):
        with st.spinner("👨‍🏫 Coach is analyzing your response..."):
            raw_ai_response = get_ai_response(final_user_input)
            audio_file = speak(raw_ai_response)
            
            # Display immediately
            if "---" in raw_ai_response:
                parts = raw_ai_response.split("---")
                st.markdown(f"**🗣️ Persona:** {parts[0]}")
                st.markdown(f"<div class='coach-card'>{parts[1]}</div>", unsafe_allow_html=True)
            else:
                st.markdown(raw_ai_response)
                
            if audio_file:
                st.audio(audio_file)
            
            # Save to Memory
            st.session_state.messages.append({
                "role": "assistant", 
                "content": raw_ai_response, 
                "audio": audio_file
            })
    
    # Reset mic for next turn
    st.session_state.reset_key += 1
    st.rerun()
