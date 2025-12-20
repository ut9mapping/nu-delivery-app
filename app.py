import streamlit as st
from google import genai  # ใช้ Library ตัวใหม่ล่าสุดตามคำแนะนำใน Logs
import gspread
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime

# --- การตั้งค่าหน้าจอ ---
st.set_page_config(page_title="GPS Delivery Tracker", page_icon="📍")
st.title("📍 บันทึกพิกัดส่งของ (เวอร์ชันอัปเดต)")

# --- 1. เชื่อมต่อ Gemini (ระบบใหม่) ---
try:
    # สร้างการเชื่อมต่อด้วย Client ตัวใหม่
    client = genai.Client(api_key=st.secrets["API_KEY"])
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
# ปุ่มดึงพิกัดจะแสดงเป็นไอคอนหมุดหรือวงกลม
location = streamlit_geolocation()

# ตรวจสอบว่าได้พิกัดหรือยัง
if location.get('latitude') is not None:
    lat = location['latitude']
    lon = location['longitude']
    
    st.success(f"✅ ตรวจพบพิกัด: {lat}, {lon}")
    
    note = st.text_area("✍️ บันทึกเพิ่มเติม:", placeholder="ใส่รายละเอียดที่นี่...")

    if st.button("🚀 บันทึกข้อมูล"):
        sheet = connect_to_sheet()
        if sheet:
            with st.spinner('AI กำลังสรุปและบันทึกข้อมูล...'):
                try:
                    # การเรียกใช้ Gemini แบบใหม่ (แก้ปัญหา 404)
                    prompt = f"สรุปพิกัด {lat}, {lon} และข้อมูล '{note}' เป็นบันทึกสั้นๆ 1 ประโยค"
                    response = client.models.generate_content(
                        model="gemini-1.5-flash",
                        contents=prompt
                    )
                    ai_comment = response.text

                    # บันทึกข้อมูล (เวลา, Lat, Lon, Note, AI)
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    sheet.append_row([now, lat, lon, note, ai_comment])
                    
                    st.balloons()
                    st.success("บันทึกสำเร็จ!")
                    st.info(f"🤖 AI สรุปให้ว่า: {ai_comment}")
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาดขณะบันทึก: {e}")
else:
    st.warning("👈 โปรดคลิกที่ 'ไอคอนหมุด' หรือ 'ปุ่มวงกลม' ด้านบนเพื่อแชร์พิกัด")
    st.info("หากปุ่มไม่ขึ้น: ตรวจสอบว่าแก้ไขไฟล์ requirements.txt แล้ว และกด Refresh หน้าเว็บ")
