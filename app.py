import streamlit as st
import google.generativeai as genai
import pandas as pd

# 1. ตั้งค่าความปลอดภัย
try:
    API_KEY = st.secrets["API_KEY"]
    SHEET_ID = st.secrets["SHEET_ID"]
    genai.configure(api_key=API_KEY)
except:
    st.error("❌ ไม่พบไฟล์ secrets.toml")
    st.stop()

# ฟังก์ชันดักทาง 404: ค้นหาโมเดลที่เครื่องนี้รู้จัก
def find_model():
    models_to_try = ['gemini-1.5-flash', 'models/gemini-1.5-flash', 'gemini-pro']
    for m in models_to_try:
        try:
            temp_model = genai.GenerativeModel(m)
            temp_model.generate_content("test", generation_config={"max_output_tokens": 1})
            return m
        except:
            continue
    return None

if 'model_name' not in st.session_state:
    st.session_state.model_name = find_model()

# 2. ตั้งค่า UI
st.set_page_config(page_title="NU Delivery", page_icon="🛵")
st.title("🛵 NU Delivery Smart Assistant")

if not st.session_state.model_name:
    st.error("❌ ไม่พบโมเดล AI ที่ใช้งานได้ (404) กรุณารัน: pip install -U google-generativeai")
    st.stop()
else:
    st.caption(f"Status: เชื่อมต่อ AI รุ่น {st.session_state.model_name} สำเร็จ")

# 3. ดึงข้อมูล
url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
@st.cache_data(ttl=60)
def load_data():
    try: return pd.read_csv(url)
    except: return pd.DataFrame()

df = load_data()
tab1, tab2 = st.tabs(["🔍 ถามทาง", "✨ สรุปข้อมูล"])

with tab1:
    q = st.text_input("พิมพ์คำถาม:")
    if q and not df.empty:
        model = genai.GenerativeModel(st.session_state.model_name)
        res = model.generate_content(f"ข้อมูล: {df.to_string()}\nคำถาม: {q}")
        st.info(res.text)

with tab2:
    txt = st.text_area("ข้อมูลหน้างาน:")
    if st.button("🪄 สรุป"):
        model = genai.GenerativeModel(st.session_state.model_name)
        res = model.generate_content(f"สรุปสั้นๆ: {txt}")
        st.success(res.text)
