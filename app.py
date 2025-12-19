import streamlit as st
import google.generativeai as genai
import pandas as pd

# 1. ตั้งค่าความปลอดภัย
try:
    API_KEY = st.secrets["API_KEY"]
    SHEET_ID = st.secrets["SHEET_ID"]
    genai.configure(api_key=API_KEY)
except Exception as e:
    st.error(f"❌ ปัญหาเรื่อง Secrets: {e}")
    st.stop()

# 2. ตั้งค่า UI
st.set_page_config(page_title="NU Delivery", page_icon="🛵")
st.title("🛵 NU Delivery Smart Assistant")

# 3. ดึงข้อมูลจาก Sheets
url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
@st.cache_data(ttl=60)
def load_data():
    try:
        return pd.read_csv(url)
    except Exception as e:
        st.error(f"เชื่อมต่อ Sheets ไม่ได้: {e}")
        return pd.DataFrame()

df = load_data()
tab1, tab2 = st.tabs(["🔍 ถามทาง", "✨ สรุปข้อมูล"])

# ส่วนการเรียกใช้ AI
def ask_gemini(prompt_text):
    try:
        # ใช้ชื่อรุ่นมาตรฐานที่ Google รองรับในปัจจุบัน
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt_text)
        return response.text
    except Exception as e:
        return f"❌ เกิดข้อผิดพลาดจาก Google API: {e}"

with tab1:
    q = st.text_input("พิมพ์คำถาม (เช่น ตึกวิศวะจอดรถตรงไหน):")
    if q:
        if not df.empty:
            with st.spinner("AI กำลังค้นหา..."):
                context = df.to_string(index=False)
                answer = ask_gemini(f"ข้อมูลอ้างอิง:\n{context}\n\nคำถาม: {q}")
                st.info(answer)
        else:
            st.warning("ไม่มีข้อมูลในระบบ")

with tab2:
    txt = st.text_area("ข้อมูลที่ต้องการให้กลั่นกรอง:")
    if st.button("🪄 สรุปข้อมูล"):
        if txt:
            with st.spinner("กำลังสรุป..."):
                summary = ask_gemini(f"สรุปข้อมูลนี้เป็นหัวข้อสั้นๆ: {txt}")
                st.success(summary)
