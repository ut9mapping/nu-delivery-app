import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import google.generativeai as genai
import re

# --- ตั้งค่าหน้าจอ ---
st.set_page_config(page_title="NU Smart Tracker Pro", page_icon="🛵", layout="wide")

# --- 1. การเชื่อมต่อ Google Services ---
def get_sheets():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])

# เชื่อมต่อ AI (ใช้ 1.5 Flash เพื่อความเสถียรและ Quota ที่มากกว่า)
try:
    genai.configure(api_key=st.secrets["API_KEY"])
    model = genai.GenerativeModel('models/gemini-1.5-flash')
except: 
    st.error("AI Config Error: กรุณาตรวจสอบ API_KEY ใน Secrets")

# --- 2. ฟังก์ชันโหลดและล้างข้อมูล (ป้องกัน KeyError) ---
def load_mapping_df():
    try:
        sh = get_sheets()
        sheet = sh.worksheet("Mapping")
        data = sheet.get_all_records()
        if not data:
            cols = ["ประตู", "ฝั่งถนน/โซน", "ซอยหลัก", "ซอยย่อย/ทางเชื่อม", "ฝั่ง/จุดรายละเอียด"]
            return pd.DataFrame(columns=cols)
        
        df = pd.DataFrame(data)
        # ตัดช่องว่างที่หัวตารางและข้อมูลทุกช่องป้องกัน KeyError
        df.columns = [str(c).strip() for c in df.columns]
        df = df.map(lambda x: str(x).strip() if isinstance(x, str) else x)
        return df
    except Exception as e:
        st.error(f"Error Loading Mapping: {e}")
        return pd.DataFrame(columns=["ประตู", "ฝั่งถนน/โซน", "ซอยหลัก", "ซอยย่อย/ทางเชื่อม", "ฝั่ง/จุดรายละเอียด"])

# ฟังก์ชันกรองตัวเลือกแบบลำดับชั้น
def get_options(df, filters):
    temp_df = df.copy()
    for col, val in filters.items():
        if val and val != "-- เลือก --":
            temp_df = temp_df[temp_df[col] == val]
    target_col_idx = len(filters)
    if target_col_idx < len(df.columns):
        # กรองเอาค่าที่ไม่ว่างและไม่ใช่เครื่องหมายลบ
        return sorted([str(x) for x in temp_df.iloc[:, target_col_idx].unique() if x and str(x) != "-" and str(x) != ""])
    return []

# --- 3. UI หลัก ---
st.title("📍 ระบบพิกัดขนส่ง มน. (Visual & Robust Search)")
mapping_df = load_mapping_df()

tab1, tab2, tab3 = st.tabs(["📌 บันทึกงานส่งของ", "🔍 ค้นหาพิกัด & ภาพจำลอง", "⚙️ Admin (จัดการซอย)"])

# --- TAB 1: บันทึกงาน (โครงสร้าง 5 ระดับ) ---
with tab1:
    location = streamlit_geolocation()
    lat, lon = location.get('latitude'), location.get('longitude')

    if lat and lon:
        st.success(f"📍 GPS พร้อม: {lat:.6f}, {lon:.6f}")
        
        # คอลัมน์เลือกแบบ Dynamic
        gate = st.selectbox("1. เลือกประตู:", ["-- เลือก --"] + sorted(mapping_df['ประตู'].unique().tolist()))
        
        if gate != "-- เลือก --":
            col1, col2 = st.columns(2)
            with col1:
                zones = get_options(mapping_df, {"ประตู": gate})
                zone = st.selectbox("2. ฝั่งถนน/โซนหลัก:", ["-- เลือก --"] + zones) if zones else "-"
            with col2:
                m_sois = get_options(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone}) if zone != "-- เลือก --" else []
                main_soi = st.selectbox("3. ซอยหลัก:", ["-- เลือก --"] + m_sois) if m_sois else "-"

            col3, col4 = st.columns(2)
            with col3:
                s_sois = get_options(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main_soi}) if main_soi != "-- เลือก --" else []
                sub_soi = st.selectbox("4. ซอยย่อย/ทางเชื่อม:", ["-- เลือก --"] + s_sois) if s_sois else "-"
            with col4:
                dets = get_options(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main_soi, "ซอยย่อย/ทางเชื่อม": sub_soi}) if sub_soi != "-- เลือก --" else []
                detail = st.selectbox("5. ฝั่ง/จุดละเอียด:", ["-- เลือก --"] + dets) if dets else "-"

            extra = st.text_input("✍️ หมายเหตุเพิ่มเติม (เลขห้อง/ชื่อร้าน/ชื่อหอ):")

            if st.button("🚀 บันทึกพิกัดลงฐานข้อมูล"):
                with st.spinner("กำลังบันทึก..."):
                    sh = get_sheets()
                    log_sheet = sh.worksheet("Sheet1")
                    full_info = f"{gate} | {zone} | {main_soi} | {sub_soi} | {detail} | {extra}"
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    maps_url = f"https://www.google.com/maps?q={lat},{lon}"
                    log_sheet.append_row([now, full_info, lat, lon, maps_url])
                    st.balloons()
                    st.success(f"บันทึกสำเร็จ: {full_info}")
    else:
        st.warning("📍 กรุณาเปิด GPS และกดปุ่มเพื่อดึงพิกัด")

# --- TAB 2: ค้นหา (AI + Fallback Search + Map) ---
with tab2:
    st.header("🔍 ค้นหาประวัติด้วย AI และภาพจำลอง")
    query = st.text_input("ค้นหา เช่น 'หอนริศา', 'ร้านปลาวาฬ', 'ประตู 4 ซอยว่องเคยไปไหม'")
    
    if st.button("เริ่มการค้นหา"):
        if query:
            with st.spinner("กำลังค้นหาพิกัด..."):
                try:
                    sh = get_sheets()
                    history_df = pd.DataFrame(sh.worksheet("Sheet1").get_all_records())
                    history_df.columns = [str(c).strip() for c in history_df.columns]

                    m_lat, m_lon, found_text = None, None, ""

                    # 1. พยายามใช้ AI (Gemini 1.5 Flash)
                    try:
                        prompt = f"""
                        ข้อมูลประวัติ: {history_df.tail(40).to_string()}
                        คำถาม: {query}
                        ตอบคำถาม และถ้าเจอพิกัดให้ใส่ "COORD_FOUND: lat,lon"
                        """
                        response = model.generate_content(prompt).text
                        coord_match = re.search(r"COORD_FOUND:\s*([0-9.]+),\s*([0-9.]+)", response)
                        
                        if coord_match:
                            m_lat, m_lon = float(coord_match.group(1)), float(coord_match.group(2))
                            found_text = response.split("COORD_FOUND")[0]
                        else:
                            found_text = response
                    except Exception as ai_err:
                        st.warning("⚠️ AI โควตาเต็ม กำลังใช้ระบบค้นหาสำรอง...")
                        # 2. ระบบสำรอง (Keyword Search)
                        results = history_df[history_df['บันทึก'].str.contains(query, case=False, na=False)]
                        if not results.empty:
                            last_hit = results.iloc[-1]
                            m_lat, m_lon = float(last_hit['ละติจูด']), float(last_hit['ลองจิจูด'])
                            found_text = f"เจอข้อมูลล่าสุดจากระบบค้นหาปกติ: {last_hit['บันทึก']}"
                        else:
                            found_text = "ขออภัย ไม่พบข้อมูลสถานที่นี้ในประวัติ"

                    # แสดงผล
                    st.markdown(f"**🤖 ผลการค้นหา:** {found_text}")
                    if m_lat and m_lon:
                        st.write("---")
                        st.subheader("📸 ภาพจำลองแผนที่")
                        st.map(pd.DataFrame({'lat': [m_lat], 'lon': [m_lon]}), zoom=17)
                        st.write(f"🔗 [เปิด Google Maps นำทาง](https://www.google.com/maps?q={m_lat},{m_lon})")

                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาดในการเข้าถึงข้อมูล: {e}")
        else:
            st.warning("กรุณาพิมพ์ชื่อสถานที่เพื่อค้นหา")

# --- TAB 3: Admin (ปุ่มบวกจัดการ Database) ---
with tab3:
    st.header("⚙️ จัดการโครงสร้างซอย (Admin)")
    if st.text_input("รหัสผ่าน Admin:", type="password") == "9999":
        st.subheader("➕ เพิ่มข้อมูลโครงสร้าง 5 ระดับ")
        st.info("ใช้เครื่องหมายลบ '-' หากไม่มีข้อมูลในระดับนั้น")
        with st.form("admin_add"):
            c1, c2, c3, c4, c5 = st.columns(5)
            a_gate = c1.text_input("1. ประตู")
            a_zone = c2.text_input("2. ฝั่งถนน/โซน")
            a_soi = c3.text_input("3. ซอยหลัก")
            a_sub = c4.text_input("4. ซอยย่อย/เชื่อม")
            a_det = c5.text_input("5. ฝั่ง/จุดละเอียด")
            
            if st.form_submit_button("➕ บันทึกโครงสร้างใหม่"):
                if a_gate and a_soi:
                    sh = get_sheets()
                    sh.worksheet("Mapping").append_row([a_gate, a_zone, a_soi, a_sub, a_det])
                    st.cache_data.clear()
                    st.success("เพิ่มข้อมูลสำเร็จ!")
                    st.rerun()
                else:
                    st.error("กรุณากรอกข้อมูล 'ประตู' และ 'ซอยหลัก' เป็นอย่างน้อย")
