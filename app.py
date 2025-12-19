import streamlit as st
import google.generativeai as genai
import pandas as pd

# --- 1. ตั้งค่าความปลอดภัย ---
try:
    API_KEY = st.secrets["API_KEY"]
    SHEET_ID = st.secrets["SHEET_ID"]
    genai.configure(api_key=API_KEY)
except Exception as e:
    st.error(f"❌ ไม่พบ Secrets: {e}")
    st.stop()

# --- 2. ฟังก์ชันแก้ปัญหา 404 (ค้นหาชื่อรุ่นที่ถูกต้องให้เอง) ---
def get_available_model():
    try:
        # ดึงรายชื่อโมเดลทั้งหมดที่ API Key นี้เข้าถึงได้
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # ลำดับความสำคัญของรุ่นที่เราอยากได้
        priority_models = [
            'models/gemini-1.5-flash',
            'models/gemini-1.5-flash-latest',
            'models/gemini-1.5-pro',
            'models/gemini-pro'
        ]
        
        for p in priority_models:
            if p in models:
                return p
        return models[0] if models else None
    except Exception as e:
        st.error(f"ไม่สามารถดึงรายชื่อโมเดลได้: {e}")
        return None

# เก็บชื่อรุ่นที่ใช้ได้ไว้ใน Session
if 'valid_model_name' not in st.session_state:
    st.session_state.valid_model_name = get_available_model()

# --- 3. ตั้งค่า UI ---
st.set_page_config(page_title="NU Delivery", page_icon="🛵")
st.title("🛵 NU Delivery Smart Assistant")

if not st.session_state.valid_model_name:
    st.error("❌ ไม่พบโมเดล AI ที่ใช้งานได้ในบัญชีของคุณ กรุณาตรวจสอบ API Key ใน Google AI Studio")
    st.stop()
else:
    st.caption(f"✅ เชื่อมต่อสำเร็จ: ใช้รุ่น {st.session_state.valid_model_name}")

# --- 4. ดึงข้อมูลจาก Sheets ---
url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
@st.cache_data(ttl=60)
def load_data():
    try:
        return pd.read_csv(url)
    except:
        return pd.DataFrame()

df = load_data()
tab1, tab2 = st.tabs(["🔍 สอบถามทาง", "✨ สรุปข้อมูลด่วน"])

# ฟังก์ชันเรียก AI
def call_gemini(prompt):
    try:
        model = genai.GenerativeModel(st.session_state.valid_model_name)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ เกิดข้อผิดพลาด: {e}"

with tab1:
    q = st.text_input("ถามทาง / หาจุดส่ง:")
    if q:
        if not df.empty:
            with st.spinner("AI กำลังหาคำตอบ..."):
                context = df.to_string(index=False)
                res = call_gemini(f"ข้อมูลอ้างอิง:\n{context}\n\nคำถาม: {q}\nตอบสั้นๆ กระชับ")
                st.info(res)
        else:
            st.warning("ไม่มีข้อมูลใน Sheets")

with tab2:
    txt = st.text_area("วางข้อมูลหน้างาน:")
    if st.button("🪄 สรุป"):
        if txt:
            with st.spinner("กำลังสรุป..."):
                res = call_gemini(f"สรุปข้อมูลนี้เป็นหัวข้อสั้นๆ: {txt}")
                st.success(res)
