import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import google.generativeai as genai
import re # เพิ่ม regex เพื่อดึงพิกัดจากข้อความ AI

# --- ตั้งค่าหน้าจอ ---
st.set_page_config(page_title="NU Delivery Visualizer", page_icon="🛵", layout="wide")

# --- 1. การเชื่อมต่อ Google Services ---
def get_sheets():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])

# เชื่อมต่อ AI
try:
    genai.configure(api_key=st.secrets["API_KEY"])
    model = genai.GenerativeModel('models/gemini-2.5-flash')
except: st.error("AI Config Error")

# --- 2. ฟังก์ชันโหลดข้อมูล ---
def load_mapping_df():
    try:
        sh = get_sheets()
        sheet = sh.worksheet("Mapping")
        df = pd.DataFrame(sheet.get_all_records())
        df.columns = [str(c).strip() for c in df.columns]
        df = df.map(lambda x: str(x).strip() if isinstance(x, str) else x)
        return df
    except:
        return pd.DataFrame(columns=["ประตู", "ฝั่งถนน/โซน", "ซอยหลัก", "ซอยย่อย/ทางเชื่อม", "ฝั่ง/จุดรายละเอียด"])

# ฟังก์ชันกรองตัวเลือก
def get_options(df, filters):
    temp_df = df.copy()
    for col, val in filters.items():
        if val and val != "-- เลือก --":
            temp_df = temp_df[temp_df[col] == val]
    return sorted([x for x in temp_df.iloc[:, len(filters)].unique() if x and x != "-" and x != ""])

# --- 3. UI หน้าหลัก ---
st.title("🛵 ระบบบันทึกและค้นหาพิกัด มน. (มีภาพจำลอง)")
mapping_df = load_mapping_df()

tab1, tab2, tab3 = st.tabs(["📌 บันทึกงาน", "🔍 ค้นหา+ภาพจำลอง", "⚙️ Admin โครงสร้าง"])

# --- TAB 1: บันทึกงาน (เหมือนเดิม) ---
with tab1:
    location = streamlit_geolocation()
    lat, lon = location.get('latitude'), location.get('longitude')

    if lat and lon:
        st.info(f"📍 พิกัดปัจจุบัน: {lat:.5f}, {lon:.5f}")
        # STEP 1-5: การเลือกโครงสร้าง (ใช้โค้ดเดิมจากเวอร์ชันที่แล้ว)
        gate = st.selectbox("1. เลือกประตู:", ["-- เลือก --"] + sorted(mapping_df['ประตู'].unique().tolist()))
        if gate != "-- เลือก --":
            col1, col2 = st.columns(2)
            with col1:
                zones = get_options(mapping_df, {"ประตู": gate})
                zone = st.selectbox("2. ฝั่งถนน/โซนหลัก:", ["-- เลือก --"] + zones) if zones else "-"
            with col2:
                if zone != "-- เลือก --":
                    main_sois = get_options(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone})
                    main_soi = st.selectbox("3. ซอยหลัก:", ["-- เลือก --"] + main_sois) if main_sois else "-"
                else: main_soi = "-- เลือก --"
            col3, col4 = st.columns(2)
            with col3:
                if main_soi != "-- เลือก --":
                    sub_sois = get_options(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main_soi})
                    sub_soi = st.selectbox("4. ซอยย่อย/ทางเชื่อม (ถ้ามี):", ["-- เลือก --"] + sub_sois) if sub_sois else "-"
                else: sub_soi = "-- เลือก --"
            with col4:
                if sub_soi != "-- เลือก --":
                    details = get_options(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main_soi, "ซอยย่อย/ทางเชื่อม": sub_soi})
                    detail = st.selectbox("5. ฝั่ง/จุดละเอียด:", ["-- เลือก --"] + details) if details else "-"
                else: detail = "-- เลือก --"

            extra = st.text_input("✍️ เลขห้อง/ชื่อหอ/หมายเหตุ:")

            if st.button("🚀 บันทึกพิกัดลง Sheet1"):
                with st.spinner("กำลังบันทึก..."):
                    full_info = f"{gate} | {zone} | {main_soi} | {sub_soi} | {detail} | {extra}"
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    maps_url = f"https://www.google.com/maps?q={lat},{lon}"
                    # บันทึกลง Sheet1 (ต้องมีหัวตาราง: เวลา, บันทึก, ละติจูด, ลองจิจูด, นำทาง)
                    sh = get_sheets()
                    sh.worksheet("Sheet1").append_row([now, full_info, lat, lon, maps_url])
                    st.success(f"บันทึกสำเร็จ: {full_info}")
    else:
        st.warning("📍 กรุณากดปุ่ม GPS")

# --- TAB 2: ค้นหา + ภาพจำลองแผนที่ (ส่วนที่อัปเกรดใหม่!) ---
with tab2:
    st.header("🔍 ค้นหาประวัติการส่ง")
    query = st.text_input("พิมพ์คำค้นหา (เช่น 'ร้านปลาวาฬอยู่ไหน', 'เคยไปส่งหอนริศาไหม'):")
    
    if st.button("ค้นหาและแสดงแผนที่"):
        with st.spinner("AI กำลังค้นหาและสร้างภาพจำลอง..."):
            try:
                # 1. ดึงข้อมูลประวัติจาก Sheet1
                sh = get_sheets()
                history_df = pd.DataFrame(sh.worksheet("Sheet1").get_all_records())
                
                # 2. สั่ง AI ให้หาคำตอบ และบังคับให้ส่งพิกัดกลับมาด้วยถ้ารู้
                prompt = f"""
                ข้อมูลประวัติการส่งของ:
                {history_df.to_string()}
                
                คำถามผู้ใช้: {query}
                
                ภารกิจ:
                1. ตอบคำถามผู้ใช้จากข้อมูลที่มี
                2. **สำคัญมาก**: หากพบสถานที่ที่ตรงกับคำถาม ให้ดึงค่า 'ละติจูด' และ 'ลองจิจูด' ของบรรทัดนั้นมา แล้วเขียนต่อท้ายคำตอบในรูปแบบนี้เป๊ะๆ: "COORD_FOUND: ละติจูด,ลองจิจูด" (ตัวอย่าง: COORD_FOUND: 16.7554,100.1234)
                3. ถ้าหาไม่เจอ หรือไม่แน่ใจ ไม่ต้องเขียนบรรทัด COORD_FOUND
                """
                
                response_text = model.generate_content(prompt).text
                
                # 3. ใช้ Regex ดึงพิกัดออกจากข้อความที่ AI ตอบมา
                map_lat, map_lon = None, None
                coord_match = re.search(r"COORD_FOUND:\s*([0-9.]+),\s*([0-9.]+)", response_text)
                
                final_answer = response_text
                if coord_match:
                    map_lat = float(coord_match.group(1))
                    map_lon = float(coord_match.group(2))
                    # ลบบรรทัดรหัส COORD_FOUND ออกจากข้อความที่จะโชว์ผู้ใช้
                    final_answer = response_text.replace(coord_match.group(0), "").strip()

                # 4. แสดงผลลัพธ์
                st.markdown(f"**🤖 AI ตอบ:** {final_answer}")
                
                # 5. ถ้าเจอพิกัด ให้แสดงแผนที่จำลอง
                if map_lat and map_lon:
                    st.write("---")
                    st.subheader("📸 ภาพจำลองพิกัด (Street Level)")
                    # สร้าง DataFrame เล็กๆ สำหรับแสดงจุดเดียว
                    map_data = pd.DataFrame({'lat': [map_lat], 'lon': [map_lon]})
                    # zoom=17 คือซูมเข้าไปลึกๆ เห็นระดับถนน
                    st.map(map_data, zoom=17, use_container_width=True)
                else:
                    st.info("ℹ️ (ไม่พบพิกัดที่ชัดเจนสำหรับแสดงภาพจำลอง)")

            except Exception as e:
                st.error(f"เกิดข้อผิดพลาดในการค้นหา: {e}")
                st.write("เช็กว่า Sheet1 มีหัวตาราง 'ละติจูด' และ 'ลองจิจูด' ถูกต้องหรือไม่")

# --- TAB 3: Admin (เหมือนเดิม) ---
with tab3:
    if st.text_input("รหัส Admin (แก้ไขโครงสร้าง):", type="password") == "9999":
        st.header("➕ เพิ่มโครงสร้างพื้นที่ (5 ระดับ)")
        with st.form("add_form_5lvl"):
            c1, c2, c3, c4, c5 = st.columns(5)
            a_gate = c1.text_input("1.ประตู")
            a_zone = c2.text_input("2.ฝั่งถนน/โซน")
            a_soi = c3.text_input("3.ซอยหลัก")
            a_sub = c4.text_input("4.ซอยย่อย/ทางเชื่อม (ถ้าไม่มีใส่ -)")
            a_det = c5.text_input("5.ฝั่ง/จุดละเอียด")
            
            if st.form_submit_button("➕ เพิ่มข้อมูล"):
                sh = get_sheets()
                sh.worksheet("Mapping").append_row([a_gate, a_zone, a_soi, a_sub, a_det])
                st.cache_data.clear()
                st.success("เพิ่มข้อมูลโครงสร้างเรียบร้อย!")
                st.rerun()
