import streamlit as st
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
from streamlit_js_eval import streamlit_js_eval

# 1. ตั้งค่าหน้าจอ
st.set_page_config(page_title="Delivery GPS Tracker", layout="centered")
st.title("📍 บันทึกพิกัดส่งของด้วย Gemini")

# 2. เชื่อมต่อ Google AI (Gemini)
try:
    genai.configure(api_key=st.secrets["API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"การเชื่อมต่อ Gemini ล้มเหลว: {e}")

# 3. ฟังก์ชันเชื่อมต่อ Google Sheets
def connect_to_sheet():
    # ดึงค่า Credentials จาก Secrets ที่เราเซฟไว้
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    
    # เปิด Sheet ด้วย ID
    sheet = client.open_by_key(st.secrets["SHEET_ID"]).get_worksheet(0)
    return sheet

# 4. ส่วนดึงพิกัด GPS
st.subheader("ดึงข้อมูลตำแหน่งปัจจุบัน")
location = streamlit_js_eval(data_key='geo', label='คลิกเพื่อดึงตำแหน่ง GPS', request_permissions=True)

if location:
    lat = location['coords']['latitude']
    lon = location['coords']['longitude']
    st.success(f"พิกัดปัจจุบัน: {lat}, {lon}")
    
    # ช่องสำหรับกรอกรายละเอียดเพิ่มเติม
    note = st.text_area("หมายเหตุ/รายละเอียดงาน:", placeholder="เช่น บ้านสีขาว ประตูรั้วสีแดง")

    if st.button("🚀 ประมวลผลและบันทึกลง Google Sheets"):
        with st.spinner('Gemini กำลังวิเคราะห์ข้อมูลและบันทึก...'):
            try:
                # ส่งข้อมูลให้ Gemini ช่วยสรุปหรือแต่งประโยค
                prompt = f"สรุปข้อมูลการส่งของในพิกัด {lat}, {lon} โดยมีรายละเอียดคือ {note} (ตอบเป็นภาษาไทยสั้นๆ)"
                response = model.generate_content(prompt)
                ai_comment = response.text

                # บันทึกข้อมูลลง Google Sheets
                sheet = connect_to_sheet()
                from datetime import datetime
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # ลำดับข้อมูล: เวลา, ละติจูด, ลองจิจูด, หมายเหตุ, สิ่งที่ AI สรุป
                sheet.append_row([now, lat, lon, note, ai_comment])
                
                st.balloons()
                st.success("บันทึกข้อมูลสำเร็จ!")
                st.write("**AI สรุป:**", ai_comment)
                
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาด: {e}")
else:
    st.info("กรุณากดปุ่มด้านบนเพื่อแชร์ตำแหน่งพิกัด")
