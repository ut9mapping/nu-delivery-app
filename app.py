import streamlit as st
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime

# --- ตั้งค่าหน้าจอ ---
st.set_page_config(page_title="GPS Tracker v2", page_icon="📍")
st.title("📍 บันทึกพิกัดแบบจัดระเบียบตาราง")

# --- 1. เชื่อมต่อ Google AI (Gemini 2.5 Flash) ---
try:
    genai.configure(api_key=st.secrets["API_KEY"])
    model = genai.GenerativeModel('models/gemini-2.5-flash')
except Exception as e:
    st.error(f"❌ ตั้งค่า Gemini ไม่สำเร็จ: {e}")

# --- 2. ฟังก์ชันเชื่อมต่อและเช็คหัวตาราง ---
def get_organized_sheet():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(st.secrets["SHEET_ID"]).get_worksheet(0)
        
        # เช็คว่าแถวที่ 1 มีข้อมูลหรือยัง (ถ้าไม่มีให้สร้างหัวข้อ)
        headers = ["วัน-เวลา", "ละติจูด", "ลองจิจูด", "บันทึกเพิ่มเติม", "AI สรุปข้อมูล"]
        first_row = sheet.row_values(1)
        
        if not first_row:
            sheet.insert_row(headers, 1)
            st.info("💡 สร้างหัวตารางใน Google Sheets ให้ใหม่เรียบร้อยแล้ว")
            
        return sheet
    except Exception as e:
        st.error(f"❌ การเชื่อมต่อ Sheet ผิดพลาด: {e}")
        return None

# --- 3. ส่วน GPS ---
st.subheader("ดึงพิกัดปัจจุบัน")
location = streamlit_geolocation()

if location.get('latitude') is not None:
    lat = location['latitude']
    lon = location['longitude']
    st.success(f"✅ ตรวจพบพิกัด: {lat}, {lon}")
    
    # แสดงตารางตัวอย่างที่จะบันทึก
    with st.expander("ดูรูปแบบข้อมูลที่จะบันทึก"):
        st.table({
            "หัวข้อ": ["ละติจูด", "ลองจิจูด"],
            "ข้อมูล": [lat, lon]
        })

    note = st.text_area("✍️ บันทึกรายละเอียดงาน:", placeholder="เช่น ส่งของบ้านคุณเอ / สภาพการจราจร...")

    if st.button("🚀 บันทึกลงตาราง"):
        sheet = get_organized_sheet()
        if sheet:
            with st.spinner('กำลังจัดระเบียบข้อมูลและบันทึก...'):
                try:
                    # ให้ Gemini ช่วยสรุป
                    prompt = f"สรุปพิกัด {lat}, {lon} และบันทึก '{note}' เป็นภาษาไทย 1 ประโยคสั้นๆ"
                    response = model.generate_content(prompt)
                    ai_comment = response.text.strip()

                    # เรียงลำดับข้อมูลให้ตรงกับหัวตาราง (A, B, C, D, E)
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    row_to_add = [now, lat, lon, note, ai_comment]
                    
                    # บันทึกข้อมูล
                    sheet.append_row(row_to_add)
                    
                    st.balloons()
                    st.success("✅ บันทึกข้อมูลสอดคล้องกับคอลัมน์เรียบร้อย!")
                    
                    # แสดงสิ่งที่บันทึกไป
                    st.write("---")
                    st.markdown(f"**🕒 เวลา:** {now}")
                    st.markdown(f"**📝 บันทึก:** {note}")
                    st.markdown(f"**🤖 AI สรุป:** {ai_comment}")
                    
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาด: {e}")
else:
    st.warning("👈 กรุณากดที่ไอคอนวงกลมเพื่อแชร์พิกัด")

# ส่วนแสดงคู่มือเล็กๆ
with st.sidebar:
    st.header("การจัดเรียงคอลัมน์")
    st.write("A: วัน-เวลา")
    st.write("B: ละติจูด")
    st.write("C: ลองจิจูด")
    st.write("D: บันทึก")
    st.write("E: AI สรุป")
