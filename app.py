import streamlit as st
import google.generativeai as genai
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime

# --- ตั้งค่าหน้าจอ ---
st.set_page_config(page_title="NU Delivery Master", page_icon="🛵", layout="wide")

# --- 1. ข้อมูลพื้นที่ มน. (Knowledge Base) สำหรับ AI ---
NU_MAP_DATA = """
- ประตู 1: หน้า ม. โซนเซเว่น, ซอยติดรั้ว (ฝั่งเดียว), ซอยกลาง (หอนัดดา/ทอรัส), ซอยร้านพี่ฝ้ายไข่เจียว
- ประตู 5-6: ซอย NU Plaza, ซอยน้ำเพชรคอนโด, ซอยโลกีย์ (ฝั่งประชาชื่น/ปังการัญ)
- ประตู 6 (เลียบรั้ว): NU1-3, Pyland1-2, ว่อง, ร้านเกมตึกช้าง, Tea Shake
- ฟินลี่แลนด์: ฝั่งซ้าย (ซอยพันดาว, โลตัส ป.5), ฝั่งขวา (ซอยพรวลัย ป.5)
- ซอยพันดาว/เคียงมอ: ร้านโกฮะ, กะเพราถาด, ชาบูขุนช้าง, หมูกระทะเคียงมอ, ซอยโฟมจ๋า, ลานอีสาน
- ประตู 4-5: หลังร้านเคโระ (ปะป๊า 20, แสงพรหมแลนด์), ข้างเซเว่น ป.4
- ประตู 4 (ขวา): เลียบรั้ว ป.4 (ธิดารัตน์, TK Land), เฟื่องฟ้า, หลังบิ๊กซี, จันทร์สุริยา, K Hall, ร้านชุดแต่งงาน, วินวินช็อป
- ประตู 4 (ซ้าย): หลังร้านเปรียว, ซอยกระบอกวิศวฯ, ซอยหมี่เกี๊ยว
- โครงการแสงพรหมแลนด์ 2: ซอยซักผ้าปลาวาฬ, บุญชู, ทรีไดมอนด์, ทองประเสริฐ, ซอยกลาง (เอวาโฮม)
- ประตู 3: แยกสะพาน, โซนหอพักหัวโค้ง, ฝั่งหอบ้านเรา (ซ้าย/ขวา)
**กฎสำคัญ: ทุกซอยต้องระบุ ฝั่งซ้าย หรือ ฝั่งขวา หรือ สุดซอย เสมอ**
"""

# --- 2. การเชื่อมต่อ ---
try:
    genai.configure(api_key=st.secrets["API_KEY"])
    model = genai.GenerativeModel('models/gemini-2.5-flash')
except: st.error("Gemini Error")

def get_sheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"]).get_worksheet(0)

def save_to_correct_columns(sheet, data_dict):
    headers = sheet.row_values(1)
    new_row = [""] * len(headers)
    for i, h in enumerate(headers):
        h_low = h.lower()
        if "เวลา" in h_low: new_row[i] = data_dict['time']
        elif "ละติจูด" in h_low or "lat" in h_low: new_row[i] = data_dict['lat']
        elif "ลองจิจูด" in h_low or "lon" in h_low: new_row[i] = data_dict['lon']
        elif "บันทึก" in h_low or "รายละเอียด" in h_low: new_row[i] = data_dict['note']
        elif "สรุป" in h_low or "ai" in h_low: new_row[i] = data_dict['ai_summary']
        elif "นำทาง" in h_low or "map" in h_low: new_row[i] = data_dict['map_url']
    sheet.append_row(new_row)

# --- 3. UI ---
tab1, tab2, tab3 = st.tabs(["📌 บันทึกงานส่งของ", "🔍 ถาม AI (ค้นหา)", "✏️ แก้ไข (9999)"])

with tab1:
    st.header("🛵 ลงบันทึกการส่งของ (โซน มน.)")
    location = streamlit_geolocation()
    lat, lon = location.get('latitude'), location.get('longitude')

    if lat and lon:
        if 'step' not in st.session_state: st.session_state.step = "input"
        
        if st.session_state.step == "input":
            note = st.text_input("📍 ป้อนสถานที่ (เช่น ประตู 4 ซอยหมี่เกี๊ยว):")
            if st.button("ตรวจสอบความถูกต้อง"):
                prompt = f"""
                ข้อมูลแผนที่ มน.: {NU_MAP_DATA}
                ข้อมูลผู้ใช้: {note}
                ภารกิจ: 
                1. ตรวจสอบว่าระบุ 'ประตู', 'ชื่อซอย' และ 'ฝั่ง (ซ้าย/ขวา/สุดซอย)' ครบหรือยัง
                2. ถ้าไม่ครบ ให้ถามคำถามที่เจาะจงตามข้อมูลแผนที่ มน. เช่น "อยู่ฝั่งร้านโกฮะหรือกะเพราถาดครับ?"
                3. ถ้าครบแล้วให้ตอบแค่ 'OK'
                """
                res = model.generate_content(prompt).text
                if "OK" in res.upper():
                    st.session_state.temp_data = {'lat': lat, 'lon': lon, 'note': note}
                    st.session_state.step = "save"
                    st.rerun()
                else:
                    st.session_state.temp_data = {'lat': lat, 'lon': lon, 'note': note, 'ask': res}
                    st.session_state.step = "clarify"
                    st.rerun()

        elif st.session_state.step == "clarify":
            st.warning(f"🤖 AI ตรวจสอบพื้นที่: {st.session_state.temp_data['ask']}")
            extra = st.text_input("ระบุข้อมูลเพิ่มเติม:")
            if st.button("บันทึกข้อมูลเสริม"):
                st.session_state.temp_data['note'] += f" ({extra})"
                st.session_state.step = "save"
                st.rerun()

        if st.session_state.step == "save":
            st.success(f"✅ ข้อมูลครบถ้วน: {st.session_state.temp_data['note']}")
            if st.button("🚀 ยืนยันบันทึกลง Sheet"):
                sheet = get_sheet()
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                maps_url = f"https://www.google.com/maps?q={lat},{lon}"
                ai_sum = model.generate_content(f"สรุปบันทึกส่งของที่ มน. สั้นๆ: {st.session_state.temp_data['note']}").text
                save_to_correct_columns(sheet, {'time': now, 'lat': lat, 'lon': lon, 'note': st.session_state.temp_data['note'], 'ai_summary': ai_sum, 'map_url': maps_url})
                st.balloons()
                st.session_state.step = "input"
                st.success("บันทึกเรียบร้อย!")
    else: st.info("รอพิกัด GPS...")

with tab2:
    st.header("🔍 ระบบค้นหาอัจฉริยะ")
    q = st.text_input("ถาม AI เช่น 'ร้านวินวินอยู่ประตูไหน?' หรือ 'เมื่อวานไปซอยโลกีย์กี่ครั้ง?'")
    if st.button("ค้นหา"):
        sheet = get_sheet()
        df = pd.DataFrame(sheet.get_all_records())
        ans = model.generate_content(f"ข้อมูลพื้นที่ มน.: {NU_MAP_DATA}\nประวัติใน Sheet:\n{df.to_string()}\nคำถาม: {q}").text
        st.markdown(ans)

with tab3:
    st.header("✏️ แก้ไขข้อมูล (PIN: 9999)")
    pin = st.text_input("ใส่รหัส PIN เพื่อดูข้อมูลและแก้ไข:", type="password")
    if pin == "9999":
        sheet = get_sheet()
        df = pd.DataFrame(sheet.get_all_records())
        st.dataframe(df)
        row = st.number_input("แถวที่จะแก้ (Index):", min_value=0, step=1)
        col = st.selectbox("คอลัมน์ที่จะแก้:", df.columns)
        val = st.text_input("ข้อมูลใหม่:")
        if st.button("💾 เซฟการแก้ไข"):
            headers = sheet.row_values(1)
            sheet.update_cell(row + 2, headers.index(col) + 1, val)
            st.success("แก้ไขสำเร็จ!")
