import streamlit as st
import sqlite3
import time
import os
from datetime import date
from groq import Groq
from gtts import gTTS
import tempfile

# ================= CONFIGURATION =================
# Try to get keys from Streamlit Secrets (Cloud) or fallback to config.py (Local)
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except:
    try:
        import config
        GROQ_API_KEY = config.GROQ_API_KEY
    except:
        st.error("⚠️ API Key missing! Set it in .streamlit/secrets.toml or config.py")
        GROQ_API_KEY = ""

client = Groq(api_key=GROQ_API_KEY)

# ================= APP SETUP =================
st.set_page_config(page_title="Spanish BPO Coach", page_icon="🇪🇸", layout="wide")

# Custom CSS for Chat Interface
st.markdown("""
<style>
    .stChatMessage { padding: 10px; border-radius: 10px; }
    .stButton button { width: 100%; border-radius: 5px; }
    .stAudio { width: 100%; }
</style>
""", unsafe_allow_html=True)

# ================= DATABASE =================
def init_db():
    conn = sqlite3.connect("spanish_web.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            level TEXT DEFAULT 'A1',
            xp INTEGER DEFAULT 0)''')
    c.execute("INSERT OR IGNORE INTO users (id, level, xp) VALUES (1, 'A1', 0)")
    c.execute('''CREATE TABLE IF NOT EXISTS vocab (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT,
            translation TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ================= SESSION STATE =================
if "mode" not in st.session_state: st.session_state.mode = "idle"
if "messages" not in st.session_state: st.session_state.messages = []
if "level" not in st.session_state: st.session_state.level = "A1"
if "hangman" not in st.session_state: st.session_state.hangman = None
if "current_lesson" not in st.session_state: st.session_state.current_lesson = None

# ================= HELPERS =================
def add_message(role, content, audio=False):
    st.session_state.messages.append({"role": role, "content": content})
    if audio and role == "assistant":
        try:
            tts = gTTS(text=content.replace("*", "").split("Feedback:")[0], lang='es')
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                tts.save(fp.name)
                st.session_state.messages[-1]["audio"] = fp.name
        except: pass

def get_ai_response(prompt, system_prompt):
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
        )
        return completion.choices[0].message.content
    except Exception as e: return f"Error: {e}"

# ================= LOGIC ENGINES =================
def process_input(user_input):
    mode = st.session_state.mode
    level = st.session_state.level
    
    # 1. HANGMAN LOGIC
    if mode == "hangman":
        game = st.session_state.hangman
        if len(user_input) != 1 or not user_input.isalpha():
            add_message("assistant", "⚠️ Send ONE letter at a time.")
            return

        letter = user_input.lower()
        if letter in game['guessed']:
            add_message("assistant", "You already guessed that!")
            return
            
        game['guessed'].append(letter)
        if letter not in game['word']: game['tries'] -= 1
        
        # Build Display
        display = " ".join([c if c in game['guessed'] else "_" for c in game['word']])
        status = f"📝 Word: `{display}` | ❤️ Lives: {game['tries']} | 🚫 Used: {', '.join(game['guessed'])}"
        
        if "_" not in display:
            add_message("assistant", f"🏆 **VICTORY!** The word was: {game['word']}\n\nStarting new game or click 'Exit' in sidebar.")
            st.session_state.mode = "idle"
        elif game['tries'] <= 0:
            add_message("assistant", f"💀 **GAME OVER.** The word was: {game['word']}")
            st.session_state.mode = "idle"
        else:
            add_message("assistant", status)
        return

    # 2. AI MODES
    sys_msg = f"Role: Spanish Tutor. Level: {level}."
    
    if mode.startswith("sim_"):
        personas = {
            "sim_angry": "Role: ANGRY Customer (Billing).",
            "sim_tech": "Role: Confused Grandma (No WiFi).",
            "sim_medical": "Role: Patient in pain.",
            "sim_insurance": "Role: Driver in car accident.",
            "sim_realestate": "Role: Home Buyer (3 Bedroom).",
            "sim_travel": "Role: Tourist (Missed Flight)."
        }
        sys_msg = f"{personas.get(mode, 'Customer')}. 1. Reply in Spanish. 2. Add '---'. 3. English Feedback."
    
    elif mode == "quiz": sys_msg = f"Generate a Spanish grammar multiple-choice question for Level {level}."
    elif mode == "pronunciation": sys_msg = "Rate the user's Spanish text (0-10) and correct grammar."
    elif mode == "script": sys_msg = "Write a BPO script for this topic."
    elif mode == "translator": sys_msg = "Translate to Spanish/English."
    
    response = get_ai_response(user_input, sys_msg)
    
    # Sim Formatting
    if "---" in response:
        parts = response.split("---")
        clean_resp = f"🗣️ **Customer:** {parts[0].strip()}\n\n👨‍🏫 **Feedback:** _{parts[1].strip()}_"
        add_message("assistant", clean_resp, audio=True)
    else:
        add_message("assistant", response, audio=True)

# ================= UI: SIDEBAR =================
with st.sidebar:
    st.header(f"🇪🇸 User Level: {st.session_state.level}")
    
    # Level Selector
    new_level = st.selectbox("Change Level", ["A1", "A2", "B1", "B2", "C1", "C2"], index=0)
    if new_level != st.session_state.level: st.session_state.level = new_level
    
    st.divider()
    
    # NAVIGATION
    menu = st.radio("Menu", ["Learning", "Career (BPO)", "Tools", "Games", "Settings"])
    
    if menu == "Learning":
        if st.button("🗣️ Free Chat"): st.session_state.mode = "chat"; add_message("assistant", "Hola! Let's chat.")
        if st.button("📝 Grammar Quiz"): st.session_state.mode = "quiz"; add_message("assistant", get_ai_response("Start quiz", f"Gen question level {st.session_state.level}"))
        if st.button("🎤 Pronunciation"): st.session_state.mode = "pronunciation"; add_message("assistant", "Send text or audio to check pronunciation.")
        
    elif menu == "Career (BPO)":
        st.subheader("Mock Calls")
        if st.button("😡 Angry Customer"): st.session_state.mode = "sim_angry"; add_message("assistant", "Call Started: Angry Customer.")
        if st.button("🏥 Medical Intake"): st.session_state.mode = "sim_medical"; add_message("assistant", "Call Started: Medical.")
        if st.button("🚗 Insurance Claim"): st.session_state.mode = "sim_insurance"; add_message("assistant", "Call Started: Insurance.")
        st.divider()
        if st.button("📜 Script Writer"): st.session_state.mode = "script"; add_message("assistant", "What topic do you need a script for?")

    elif menu == "Tools":
        if st.button("🔄 Translator"): st.session_state.mode = "translator"; add_message("assistant", "Send text to translate.")
        
    elif menu == "Games":
        if st.button("☠️ Hangman"): 
            st.session_state.mode = "hangman"
            word = get_ai_response("Gen 1 word", f"Gen 1 Spanish word level {st.session_state.level}").strip().replace(".","").lower()
            st.session_state.hangman = {'word': word, 'guessed': [], 'tries': 6}
            add_message("assistant", f"🎮 **HANGMAN STARTED**\nWord has {len(word)} letters. Guess a letter!")

    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# ================= UI: MAIN CHAT =================
st.title("🇪🇸 Ultimate Spanish Coach")
st.caption(f"Current Mode: **{st.session_state.mode.upper()}**")

# Display History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "audio" in msg:
            st.audio(msg["audio"])

# Input Area
col1, col2 = st.columns([0.85, 0.15])
with col1:
    user_input = st.chat_input("Type your message here...")

# Audio Input (New Feature)
with col2:
    audio_val = st.audio_input("🎤")

if audio_val:
    # Transcribe if audio is sent
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(audio_val.getvalue())
        try:
            with open(tmp.name, "rb") as f:
                transcription = client.audio.transcriptions.create(file=(tmp.name, f), model="whisper-large-v3", language="es")
            user_input = transcription.text
        except: st.error("Audio transcription failed.")

# Process Input
if user_input:
    add_message("user", user_input)
    process_input(user_input)
    st.rerun()