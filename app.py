import streamlit as st
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime

# --- ตั้งค่าหน้าจอ ---
st.set_page_config(page_title="GPS Tracker", page_icon="📍")
st.title("📍 บันทึกพิกัด (เวอร์ชันอัปเดต Model 2.5)")

# --- 1. เชื่อมต่อ Google AI (Gemini) ---
try:
    genai.configure(api_key=st.secrets["API_KEY"])
    # เปลี่ยนเป็นรุ่นที่บัญชีคุณรองรับ (2.5-flash)
    model = genai.GenerativeModel('models/gemini-2.5-flash')
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
st.subheader("ดึงพิกัดปัจจุบัน")
location = streamlit_geolocation()

if location.get('latitude') is not None:
    lat = location['latitude']
    lon = location['longitude']
    st.success(f"✅ ตรวจพบพิกัด: {lat}, {lon}")
    
    note = st.text_area("✍️ บันทึกเพิ่มเติม:", placeholder="ระบุรายละเอียดที่นี่...")

    if st.button("🚀 บันทึกข้อมูล"):
        sheet = connect_to_sheet()
        if sheet:
            with st.spinner('AI กำลังสรุปข้อมูลด้วยรุ่น 2.5-flash...'):
                try:
                    # ส่ง Prompt ให้ AI
                    prompt = f"สรุปพิกัด {lat}, {lon} และบันทึก '{note}' เป็นภาษาไทยสั้นๆ 1 ประโยค"
                    response = model.generate_content(prompt)
                    ai_comment = response.text.strip()

                    # บันทึกข้อมูลลง Sheet
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    sheet.append_row([now, lat, lon, note, ai_comment])
                    
                    st.balloons()
                    st.success("บันทึกข้อมูลสำเร็จ!")
                    st.info(f"🤖 AI สรุป: {ai_comment}")
                    
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาด: {e}")
else:
    st.warning("👈 กรุณากดปุ่ม **ไอคอนวงกลม** เพื่ออนุญาตพิกัด")
    st.info("หากปุ่มไม่ขึ้น ให้กด Refresh หน้าเว็บ 1 ครั้งครับ")
