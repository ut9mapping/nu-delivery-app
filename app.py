import streamlit as st
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime

# --- การตั้งค่าหน้าจอ ---
st.set_page_config(page_title="GPS Delivery Tracker", page_icon="📍")

st.title("📍 บันทึกพิกัดส่งของด้วย Gemini")

# --- 1. เชื่อมต่อ Google AI (Gemini) ---
try:
    genai.configure(api_key=st.secrets["API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"❌ Gemini เชื่อมต่อไม่ได้: {e}")

# --- 2. ฟังก์ชันเชื่อมต่อ Google Sheets ---
def connect_to_sheet():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(st.secrets["SHEET_ID"]).get_worksheet(0)
        return sheet
    except Exception as e:
        st.error(f"❌ Google Sheets เชื่อมต่อไม่ได้: {e}")
        return None

# --- 3. ส่วน GPS (ใช้ตัวใหม่ที่เสถียรกว่า) ---
st.subheader("ดึงข้อมูลตำแหน่งปัจจุบัน")
st.info("กรุณากดปุ่มด้านล่างเพื่อแชร์ตำแหน่งพิกัด")

# เรียกใช้งานปุ่มดึงพิกัด
location = streamlit_geolocation()

# ตรวจสอบว่าได้ค่าละติจูด/ลองจิจูดมาหรือยัง
if location.get('latitude') is not None:
    lat = location['latitude']
    lon = location['longitude']
    
    st.success(f"✅ ตรวจพบพิกัด: {lat}, {lon}")
    
    # ส่วนกรอกข้อมูล
    note = st.text_area("✍️ บันทึกเพิ่มเติม (เช่น ชื่อลูกค้า/บ้านเลขที่):", placeholder="ใส่รายละเอียดที่นี่...")

    if st.button("🚀 บันทึกข้อมูลลง Google Sheets"):
        sheet = connect_to_sheet()
        if sheet:
            with st.spinner('กำลังประมวลผล...'):
                try:
                    # ให้ Gemini สรุป
                    prompt = f"สรุปพิกัด {lat}, {lon} และข้อมูล '{note}' เป็นบันทึกสั้นๆ 1 ประโยค"
                    response = model.generate_content(prompt)
                    ai_comment = response.text.strip()

                    # เตรียมข้อมูลบันทึก (เวลา, Lat, Lon, Note, AI)
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    sheet.append_row([now, lat, lon, note, ai_comment])
                    
                    st.balloons()
                    st.success("บันทึกข้อมูลเรียบร้อยแล้ว!")
                    st.info(f"🤖 AI สรุปให้ว่า: {ai_comment}")
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาดขณะบันทึก: {e}")
else:
    st.warning("👈 โปรดคลิกที่ปุ่มวงกลมสีดำด้านบน เพื่ออนุญาตการเข้าถึงพิกัด")
