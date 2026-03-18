import streamlit as st
from groq import Groq
from gtts import gTTS
import tempfile
import os

# ================= 1. UI CONFIGURATION =================
st.set_page_config(page_title="Professional BPO Dual-Coach", page_icon="🎧", layout="wide")

st.markdown("""
    <style>
    .stChatMessage { border-radius: 15px; padding: 15px; margin-bottom: 10px; border: 1px solid #e0e0e0; }
    .persona-label { color: #2e7d32; font-weight: bold; font-size: 1.1rem; margin-bottom: 5px; }
    .coach-card { 
        background-color: #f8f9fa; 
        border-left: 6px solid #ff9800; 
        padding: 18px; 
        border-radius: 12px; 
        margin-top: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    .feedback-header { color: #e65100; font-weight: bold; text-transform: uppercase; font-size: 0.8rem; margin-bottom: 10px; }
    .golden-phrase { color: #2e7d32; font-weight: bold; font-style: italic; background: #e8f5e9; padding: 3px 6px; border-radius: 4px; }
    </style>
""", unsafe_allow_html=True)

# API Initialization
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("🔑 API Key Missing. Check Streamlit Secrets.")
    st.stop()

# ================= 2. SESSION STATE =================
if "messages" not in st.session_state: st.session_state.messages = []
if "level" not in st.session_state: st.session_state.level = "B2"
if "scenario" not in st.session_state: st.session_state.scenario = "Billing Complaint"
if "user_role" not in st.session_state: st.session_state.user_role = "Agent (User handles call)"
if "reset_key" not in st.session_state: st.session_state.reset_key = 0

# ================= 3. LOGIC ENGINES =================

def get_dual_prompt():
    is_agent = "Agent" in st.session_state.user_role
    
    # Define Persona Instructions
    if is_agent:
        persona_instruction = f"ACT AS: A frustrated customer. SCENARIO: {st.session_state.scenario}. React emotionally to the user's service."
        coach_focus = "Focus on the User's professionalism, empathy, and correct BPO spiels."
    else:
        persona_instruction = f"ACT AS: An ELITE BPO Agent. SCENARIO: {st.session_state.scenario}. Use perfect empathy, clear articulation, and professional protocols."
        coach_focus = "Focus on the User's Spanish grammar as a customer and highlight the 'Elite' phrases the AI Agent used."

    return f"""
    SYSTEM ROLE: You are a Dual-Mode AI.
    1. {persona_instruction}
    2. COACHING ROLE: Provide a deep analysis of the interaction.

    STRICT FEEDBACK STRUCTURE:
    [Spanish Dialogue]
    ---
    **COACH'S CORNER**
    - **Spiel & Phrasing:** (Analyze the dialogue and provide a 'Golden Phrase' alternative)
    - **Soft Skills & Tone:** (Rate empathy and professionalism 1-10)
    - **Voice & Pronunciation:** (If the user used audio, note potential clarity issues or 'filler' words like 'este', 'um')
    - **Pro Tip:** (One piece of advice to sound like a native professional)
    """

def get_ai_response(user_input):
    history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-8:]]
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": get_dual_prompt()}] + history + [{"role": "user", "content": user_input}],
            temperature=0.7
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

def speak(text):
    try:
        # Narrate only the part before the coaching
        spanish_dialogue = text.split("---")[0].strip()
        tts = gTTS(text=spanish_dialogue, lang='es')
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            tts.save(fp.name)
            return fp.name
    except: return None

# ================= 4. SIDEBAR =================
with st.sidebar:
    st.title("🎧 Training Center")
    
    # ROLE TOGGLE
    st.subheader("👤 Choose Your Role")
    st.session_state.user_role = st.radio("I want to practice as:", 
                                         ["Agent (User handles call)", "Customer (AI handles call)"])
    
    st.divider()
    
    # SCENARIO SELECTOR
    st.session_state.level = st.select_slider("Goal Level", ["A1", "A2", "B1", "B2", "C1", "C2"], value=st.session_state.level)
    
    choice = st.selectbox("Scenario", ["Billing Complaint", "Tech Support (No Internet)", "Medical Appointment VA", "Real Estate Inquiry", "Hiring Mock Interview", "CUSTOM"])
    if choice == "CUSTOM":
        st.session_state.scenario = st.text_input("Describe custom scenario:")
    else:
        st.session_state.scenario = choice

    if st.button("🗑️ Reset & Start New Call", use_container_width=True):
        st.session_state.messages = []
        st.session_state.reset_key += 1
        st.rerun()

# ================= 5. CHAT UI =================
st.title("🇪🇸 BPO Professional Dual-Coach")
role_text = "AGENT" if "Agent" in st.session_state.user_role else "CUSTOMER"
st.info(f"**MODE:** You are the **{role_text}** | **SCENARIO:** {st.session_state.scenario}")

# Display Chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "---" in msg["content"]:
            parts = msg["content"].split("---")
            label = "👤 Customer" if "Agent" in st.session_state.user_role else "🎧 Elite Agent"
            st.markdown(f"<div class='persona-label'>{label}</div>", unsafe_allow_html=True)
            st.markdown(parts[0])
            st.markdown(f"<div class='coach-card'><div class='feedback-header'>👨‍🏫 Performance Coaching</div>{parts[1]}</div>", unsafe_allow_html=True)
        else:
            st.markdown(msg["content"])
        if "audio" in msg: st.audio(msg["audio"])

# Inputs
final_input = None
audio_data = st.audio_input("Record your voice", key=f"audio_{st.session_state.reset_key}")
if audio_data:
    with st.status("Listening...", expanded=False):
        transcript = client.audio.transcriptions.create(file=("in.wav", audio_data.getvalue()), model="whisper-large-v3", language="es", response_format="text")
        final_input = transcript

text_data = st.chat_input("Type your spiel...")
if text_data: final_input = text_data

# ================= 6. EXECUTION =================
if final_input:
    st.session_state.messages.append({"role": "user", "content": final_input})
    
    with st.chat_message("assistant"):
        with st.spinner("Processing interaction..."):
            full_resp = get_ai_response(final_input)
            audio_path = speak(full_resp)
            
            if "---" in full_resp:
                parts = full_resp.split("---")
                label = "👤 Customer" if "Agent" in st.session_state.user_role else "🎧 Elite Agent"
                st.markdown(f"<div class='persona-label'>{label}</div>", unsafe_allow_html=True)
                st.markdown(parts[0])
                st.markdown(f"<div class='coach-card'><div class='feedback-header'>👨‍🏫 Performance Coaching</div>{parts[1]}</div>", unsafe_allow_html=True)
            else:
                st.markdown(full_resp)
            
            if audio_path: st.audio(audio_path)
            st.session_state.messages.append({"role": "assistant", "content": full_resp, "audio": audio_path})
    
    st.session_state.reset_key += 1
    st.rerun()

# Initial Greeting Logic
if not st.session_state.messages:
    if "Customer" in st.session_state.user_role:
        # AI is Agent, so it greets first
        with st.chat_message("assistant"):
            greeting = "🎧 **Elite Agent:** 'Gracias por llamar a soporte técnico, mi nombre es Juan. ¿Con quién tengo el gusto de hablar?'"
            st.markdown(greeting)
            # Pre-populate history with greeting
            st.session_state.messages.append({"role": "assistant", "content": greeting})
    else:
        st.write("✨ **System:** Call connected. Open with your greeting (e.g., 'Gracias por llamar, ¿en qué puedo ayudarle?')")
