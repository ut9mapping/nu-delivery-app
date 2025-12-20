import streamlit as st
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime

# --- การตั้งค่าหน้าจอ ---
st.set_page_config(page_title="GPS Delivery Tracker", page_icon="📍")
st.title("📍 บันทึกพิกัดส่งของ (Final Version)")

# --- 1. เชื่อมต่อ Google AI (Gemini) ---
try:
    genai.configure(api_key=st.secrets["API_KEY"])
    # ระบุชื่อรุ่นแบบมาตรฐานที่สุดเพื่อแก้ปัญหา 404
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"❌ ตั้งค่า Gemini ไม่สำเร็จ: {e}")

# --- 2. ฟังก์ชันเชื่อมต่อ Google Sheets ---
def connect_to_sheet():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(st.secrets["SHEET_ID"]).get_worksheet(0)
        return sheet
    except Exception as e:
        st.error(f"❌ เชื่อมต่อ Google Sheets ไม่สำเร็จ: {e}")
        return None

# --- 3. ส่วน GPS ---
st.subheader("ดึงข้อมูลตำแหน่ง")
st.info("กรุณากดที่ไอคอนวงกลม/หมุด เพื่อแชร์พิกัด")

location = streamlit_geolocation()

if location.get('latitude') is not None:
    lat = location['latitude']
    lon = location['longitude']
    
    st.success(f"✅ ตรวจพบพิกัด: {lat}, {lon}")
    
    note = st.text_area("✍️ บันทึกเพิ่มเติม:", placeholder="ระบุรายละเอียดงานที่นี่...")

    if st.button("🚀 บันทึกข้อมูลลง Google Sheets"):
        sheet = connect_to_sheet()
        if sheet:
            with st.spinner('AI กำลังประมวลผล...'):
                try:
                    # ส่ง Prompt ให้ AI สรุปข้อมูล
                    prompt = f"สรุปพิกัด {lat}, {lon} และข้อมูล '{note}' เป็นบันทึกสั้นๆ ภาษาไทย 1 ประโยค"
                    response = model.generate_content(prompt)
                    ai_comment = response.text.strip()

                    # บันทึกข้อมูลลง Sheet
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    sheet.append_row([now, lat, lon, note, ai_comment])
                    
                    st.balloons()
                    st.success("บันทึกข้อมูลสำเร็จ!")
                    st.info(f"🤖 AI สรุป: {ai_comment}")
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาดขณะบันทึก: {e}")
else:
    st.warning("👈 หากปุ่มดึงพิกัดไม่ขึ้น หรือกดแล้วไม่มีอะไรเกิดขึ้น โปรดเช็กการอนุญาต Location ในเบราว์เซอร์")
