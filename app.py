import streamlit as st
from groq import Groq
from gtts import gTTS
import tempfile
import os
import re

# ================= 1. UI SETUP =================
st.set_page_config(page_title="Elite BPO Coach Pro", page_icon="🎧", layout="wide")

st.markdown("""
    <style>
    .stChatMessage { border-radius: 15px; margin-bottom: 20px; border: 1px solid #e0e0e0; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    .persona-tag { font-weight: bold; text-transform: uppercase; font-size: 0.8rem; padding: 3px 8px; border-radius: 5px; margin-bottom: 10px; display: inline-block; }
    .tag-customer { background-color: #ffebee; color: #c62828; }
    .tag-agent { background-color: #e8f5e9; color: #2e7d32; }
    .tag-interviewer { background-color: #e3f2fd; color: #1565c0; }
    .coach-card { 
        background-color: #fffde7; 
        border-left: 6px solid #fbc02d; 
        padding: 20px; border-radius: 12px; margin-top: 15px;
        color: #333; font-size: 0.95rem; border: 1px solid #fff59d;
    }
    .golden-phrase { color: #e65100; font-weight: bold; background: #fff3e0; padding: 2px 5px; border-radius: 4px; }
    </style>
""", unsafe_allow_html=True)

# API Initialization
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception:
    st.error("🔑 API Key Missing. Please add GROQ_API_KEY to your Streamlit Secrets.")
    st.stop()

# ================= 2. SESSION STATE =================
if "messages" not in st.session_state: st.session_state.messages = []
if "user_role" not in st.session_state: st.session_state.user_role = "Agent (You handle the call)"
if "level" not in st.session_state: st.session_state.level = "B2"
if "scenario" not in st.session_state: st.session_state.scenario = "Billing Complaint"
if "reset_key" not in st.session_state: st.session_state.reset_key = 0

# ================= 3. THE "MEMORY FIREWALL" LOGIC =================

def get_system_prompt():
    """Defines the AI's dual nature: Persona + Invisible Coach."""
    is_user_agent = "Agent" in st.session_state.user_role
    scenario = st.session_state.scenario
    level = st.session_state.level

    if scenario == "BPO/VA Job Interview":
        persona = "A professional Recruiter for a top BPO firm. You are interviewing the user for a high-paying VA position."
        instruction = "Be professional, ask challenging questions about experience and soft skills in Spanish."
    elif is_user_agent:
        persona = "A realistic customer. You have a specific problem related to the scenario."
        instruction = "The user is the Agent. React as a human would—emotional but professional."
    else:
        persona = "An ELITE BPO Professional Agent. You have 10 years of experience."
        instruction = "The user is the customer. Provide world-class service and perfect BPO protocols."

    return f"""
    SYSTEM ROLE: 
    {persona}. {instruction}
    SCENARIO: {scenario}. TARGET LEVEL: {level}.

    STRICT OUTPUT FORMAT:
    [Character Speech in Spanish ONLY]
    ---
    **COACH'S CORNER**
    - **Transcription Accuracy:** (Note any mispronounced or unclear words from the user)
    - **Grammar & Vocab:** (Correct Spanish errors)
    - **Elite Spiel:** (Provide a 'Golden Phrase' alternative that is more professional)
    - **Professionalism Rating:** (Score 1-10 and explain why)
    """

def get_clean_history():
    """
    FOOLPROOF CLEANER: This is the firewall. 
    It removes all 'Coach's Corner' text from the AI's history 
    so it doesn't get confused and think it's a teacher.
    """
    clean = []
    for m in st.session_state.messages[-10:]: # Look back 10 messages
        content = m["content"]
        if "---" in content:
            # We strip out the coaching part before sending it back to the AI brain
            content = content.split("---")[0].strip() 
        clean.append({"role": m["role"], "content": content})
    return clean

def get_ai_response(user_text):
    """Fetches AI response using the Memory Firewall."""
    history = get_clean_history()
    
    # Try high-end model, fallback to fast model
    models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
    
    for model in models:
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": get_system_prompt()}] + history + [{"role": "user", "content": user_text}],
                temperature=0.8
            )
            return completion.choices[0].message.content
        except Exception as e:
            if "429" in str(e) and model != models[-1]: continue
            return f"⚠️ API Error: {str(e)}"

def generate_voice(full_text):
    """Sanitizes only the dialogue part for TTS."""
    try:
        dialogue = full_text.split("---")[0].strip()
        # Clean symbols so voice doesn't say "Asterisk"
        clean_voice_text = re.sub(r'[*#_~-]', '', dialogue)
        tts = gTTS(text=clean_voice_text, lang='es')
        fp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(fp.name)
        return fp.name
    except: return None

# ================= 4. SIDEBAR (CONFIG) =================
with st.sidebar:
    st.title("🚀 Career Training Center")
    
    role_choice = st.radio("Choose Your Practice Role:", 
                          ["Agent (You handle the call)", "Customer (AI handles the call)"])
    if role_choice != st.session_state.user_role:
        st.session_state.user_role = role_choice
        st.session_state.messages = [] # Reset on role change
        st.rerun()

    st.divider()
    st.session_state.level = st.select_slider("Target Spanish Level:", ["A1", "A2", "B1", "B2", "C1", "C2"], value=st.session_state.level)
    
    scenario_list = ["Billing Complaint", "BPO/VA Job Interview", "Medical VA (Scheduling)", "Real Estate (Lead Gen)", "Tech Support Agent", "CUSTOM SCENARIO"]
    st.session_state.scenario = st.selectbox("Scenario:", scenario_list)
    if st.session_state.scenario == "CUSTOM SCENARIO":
        st.session_state.scenario = st.text_area("Describe your custom scenario:", placeholder="Ex: I am a travel agent helping with a cancellation...")

    if st.button("🗑️ Reset Session", use_container_width=True):
        st.session_state.messages = []
        st.session_state.reset_key += 1
        st.rerun()

# ================= 5. MAIN INTERFACE =================
st.title("🇪🇸 Elite Spanish BPO Coach")
mode_label = "AGENT" if "Agent" in st.session_state.user_role else "CUSTOMER"
st.info(f"**MODE:** You are practicing as the **{mode_label}** | **SCENARIO:** {st.session_state.scenario}")

# Display Messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "---" in msg["content"]:
            parts = msg["content"].split("---")
            
            # Label selection
            if st.session_state.scenario == "BPO/VA Job Interview":
                tag_label, tag_class = "👔 Interviewer", "tag-interviewer"
            elif "Agent" in st.session_state.user_role:
                tag_label, tag_class = "👤 Customer", "tag-customer"
            else:
                tag_label, tag_class = "🎧 Elite Agent", "tag-agent"
            
            st.markdown(f"<div class='persona-tag {tag_class}'>{tag_label}</div>", unsafe_allow_html=True)
            st.markdown(parts[0]) # Dialogue
            st.markdown(f"<div class='coach-card'><b>👨‍🏫 Coach's Corner</b><br>{parts[1]}</div>", unsafe_allow_html=True)
        else:
            st.markdown(msg["content"])
        if "audio" in msg: st.audio(msg["audio"])

# ================= 6. INPUT PIPELINE =================
user_input = None

# Audio Handler
audio_data = st.audio_input("Speak to the AI Coach", key=f"audio_{st.session_state.reset_key}")
if audio_data:
    with st.status("Transcribing...", expanded=False):
        transcript = client.audio.transcriptions.create(
            file=("speech.wav", audio_data.getvalue()), 
            model="whisper-large-v3", 
            language="es", 
            response_format="text"
        )
        user_input = transcript

# Text Fallback
text_input = st.chat_input("Or type your response here...")
if text_input: user_input = text_input

# ================= 7. PROCESSING =================
if user_input:
    # 1. Save User Message
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # 2. Get Response
    with st.chat_message("assistant"):
        with st.spinner("AI is thinking..."):
            ai_raw = get_ai_response(user_input)
            audio_path = generate_voice(ai_raw)
            
            # Display immediately
            if "---" in ai_raw:
                parts = ai_raw.split("---")
                if st.session_state.scenario == "BPO/VA Job Interview":
                    tag_label, tag_class = "👔 Interviewer", "tag-interviewer"
                elif "Agent" in st.session_state.user_role:
                    tag_label, tag_class = "👤 Customer", "tag-customer"
                else:
                    tag_label, tag_class = "🎧 Elite Agent", "tag-agent"
                
                st.markdown(f"<div class='persona-tag {tag_class}'>{tag_label}</div>", unsafe_allow_html=True)
                st.markdown(parts[0])
                st.markdown(f"<div class='coach-card'><b>👨‍🏫 Coach's Corner</b><br>{parts[1]}</div>", unsafe_allow_html=True)
            else:
                st.markdown(ai_raw)
                
            if audio_path: st.audio(audio_path)
            
            # 3. Save to History
            st.session_state.messages.append({"role": "assistant", "content": ai_raw, "audio": audio_path})
    
    st.session_state.reset_key += 1
    st.rerun()

# Initial Greet Logic
if not st.session_state.messages:
    if "Customer" in st.session_state.user_role:
        initial = "🎧 **Elite Agent:** 'Gracias por llamar a soporte técnico, mi nombre es Juan. ¿Con quién tengo el gusto de hablar?'"
        if st.session_state.scenario == "BPO/VA Job Interview":
            initial = "👔 **Interviewer:** 'Hola, bienvenido a la entrevista para la posición de Asistente Virtual. Para comenzar, ¿podría presentarse y decirme por qué le interesa este trabajo?'"
        st.session_state.messages.append({"role": "assistant", "content": initial})
        st.rerun()
