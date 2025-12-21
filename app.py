import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import google.generativeai as genai
import re
import pydeck as pdk

# --- 1. การตั้งค่าเบื้องต้น ---
st.set_page_config(page_title="NU Precision Delivery Pro", page_icon="🛵", layout="wide")

def get_sheets():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])

# เชื่อมต่อ AI
try:
    genai.configure(api_key=st.secrets["API_KEY"])
    model = genai.GenerativeModel('models/gemini-1.5-flash')
except:
    st.error("AI Config Error: โปรดเช็ก API_KEY ใน Secrets")

# --- 2. ฟังก์ชันจัดการข้อมูลและแผนที่ละเอียด ---

def load_mapping_df():
    try:
        sh = get_sheets()
        sheet = sh.worksheet("Mapping")
        data = sheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=["ประตู", "ฝั่งถนน/โซน", "ซอยหลัก", "ซอยย่อย/ทางเชื่อม", "ฝั่ง/จุดรายละเอียด"])
        df = pd.DataFrame(data)
        
        # [แก้ปัญหา KeyError/TypeError] ล้างช่องว่างและบังคับเป็น String ทั้งหมด
        df.columns = [str(c).strip() for c in df.columns]
        # บังคับข้อมูลทุกช่องเป็น String เพื่อให้เรียงลำดับ (Sort) ได้ไม่พัง
        df = df.map(lambda x: str(x).strip() if x is not None else "")
        return df
    except Exception as e:
        st.error(f"โหลดข้อมูล Mapping ไม่สำเร็จ: {e}")
        return pd.DataFrame(columns=["ประตู", "ฝั่งถนน/โซน", "ซอยหลัก", "ซอยย่อย/ทางเชื่อม", "ฝั่ง/จุดรายละเอียด"])

def get_options(df, filters):
    temp_df = df.copy()
    for col, val in filters.items():
        if val and val != "-- เลือก --":
            temp_df = temp_df[temp_df[col] == val]
    target_idx = len(filters)
    if target_idx < len(df.columns):
        # ดึงค่าที่ไม่ซ้ำ บังคับเป็น String และกรองค่าว่างออก
        opts = [str(x) for x in temp_df.iloc[:, target_idx].unique() if str(x) not in ["", "-", "None"]]
        return sorted(opts)
    return []

# ฟังก์ชันแสดงแผนที่จุดเล็กละเอียด (เห็นถนนชัด)
def display_precision_map(lat, lon, zoom=18):
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=pd.DataFrame({'lat': [lat], 'lon': [lon]}),
        get_position='[lon, lat]',
        get_color='[255, 75, 75, 230]', # สีแดงสด
        get_radius=3, # ขนาด 3 เมตร (จุดเล็กละเอียด)
        pickable=True,
    )
    view_state = pdk.ViewState(latitude=lat, longitude=lon, zoom=zoom, pitch=0)
    st.pydeck_chart(pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        map_style='carto-positron', # เห็นถนนชัดเจนโดยไม่ต้องใช้ Key
    ))

# --- 3. ส่วน UI หน้าหลัก ---
st.title("🛵 ระบบพิกัดขนส่ง มน. (Fix & Precision)")
mapping_df = load_mapping_df()

tab1, tab2, tab3 = st.tabs(["📌 บันทึกงานส่งของ", "🔍 ค้นหาพิกัด & ภาพจำลอง", "⚙️ Admin Manage"])

# --- TAB 1: บันทึกงาน ---
with tab1:
    location = streamlit_geolocation()
    lat, lon = location.get('latitude'), location.get('longitude')

    if lat and lon:
        st.success(f"📍 GPS พร้อม (พิกัด: {lat:.6f}, {lon:.6f})")
        display_precision_map(lat, lon, zoom=17) 
        
        # [แก้ไขจุดที่ทำให้เกิด TypeError] บังคับค่าใน List เป็น String ก่อน Sort
        gate_list = [str(x) for x in mapping_df['ประตู'].unique() if str(x) not in ["", "None"]]
        gate = st.selectbox("1. เลือกประตู:", ["-- เลือก --"] + sorted(gate_list))
        
        if gate != "-- เลือก --":
            c1, c2 = st.columns(2)
            with c1:
                zones = get_options(mapping_df, {"ประตู": gate})
                zone = st.selectbox("2. ฝั่งถนน/โซนหลัก:", ["-- เลือก --"] + zones) if zones else "-"
            with c2:
                m_sois = get_options(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone}) if zone != "-- เลือก --" else []
                main_soi = st.selectbox("3. ซอยหลัก:", ["-- เลือก --"] + m_sois) if m_sois else "-"

            c3, c4 = st.columns(2)
            with c3:
                s_sois = get_options(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main_soi}) if main_soi != "-- เลือก --" else []
                sub_soi = st.selectbox("4. ซอยย่อย/ทางเชื่อม:", ["-- เลือก --"] + s_sois) if s_sois else "-"
            with c4:
                dets = get_options(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main_soi, "ซอยย่อย/ทางเชื่อม": sub_soi}) if sub_soi != "-- เลือก --" else []
                detail = st.selectbox("5. ฝั่ง/จุดรายละเอียด:", ["-- เลือก --"] + dets) if dets else "-"

            extra = st.text_input("✍️ หมายเหตุเพิ่มเติม (เลขห้อง/ชื่อหอ):")

            if st.button("🚀 ยืนยันบันทึกพิกัด"):
                with st.spinner("กำลังบันทึก..."):
                    try:
                        sh = get_sheets()
                        full_info = f"{gate} | {zone} | {main_soi} | {sub_soi} | {detail} | {extra}"
                        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        maps_url = f"https://www.google.com/maps?q={lat},{lon}"
                        sh.worksheet("Sheet1").append_row([now, full_info, lat, lon, maps_url])
                        st.balloons()
                        st.success(f"บันทึกสำเร็จ: {full_info}")
                    except Exception as e:
                        st.error(f"บันทึกไม่สำเร็จ: {e}")
    else:
        st.warning("📍 กรุณาเปิด GPS และกดปุ่มดึงพิกัดเพื่อเริ่มบันทึก")

# --- TAB 2: ค้นหา ---
with tab2:
    st.header("🔍 ค้นหาประวัติจุดส่ง")
    query = st.text_input("ค้นหา เช่น 'หอนริศา', 'ร้านปลาวาฬ'")
    
    if st.button("เริ่มการค้นหา"):
        if query:
            with st.spinner("กำลังค้นหา..."):
                try:
                    sh = get_sheets()
                    history_df = pd.DataFrame(sh.worksheet("Sheet1").get_all_records())
                    history_df.columns = [str(c).strip() for c in history_df.columns]

                    m_lat, m_lon, found_text = None, None, ""

                    try:
                        prompt = f"ข้อมูลประวัติ: {history_df.tail(40).to_string()}\nคำถาม: {query}\nตอบคำถาม และถ้าเจอพิกัดให้แสดง COORD_FOUND: lat,lon"
                        response = model.generate_content(prompt).text
                        coord_match = re.search(r"COORD_FOUND:\s*([0-9.]+),\s*([0-9.]+)", response)
                        if coord_match:
                            m_lat, m_lon = float(coord_match.group(1)), float(coord_match.group(2))
                            found_text = response.split("COORD_FOUND")[0].strip()
                        else: found_text = response
                    except:
                        st.warning("⚠️ ค้นหาด้วยระบบสำรอง...")
                        results = history_df[history_df['บันทึก'].str.contains(query, case=False, na=False)]
                        if not results.empty:
                            last_hit = results.iloc[-1]
                            m_lat, m_lon = float(last_hit['ละติจูด']), float(last_hit['ลองจิจูด'])
                            found_text = f"เจอข้อมูลล่าสุด: {last_hit['บันทึก']}"
                        else: found_text = "ไม่พบข้อมูล"

                    st.markdown(f"**🤖 ผลการค้นหา:** {found_text}")
                    if m_lat and m_lon:
                        display_precision_map(m_lat, m_lon, zoom=19)
                        st.write(f"🔗 [นำทาง Google Maps](https://www.google.com/maps?q={m_lat},{m_lon})")
                except Exception as e:
                    st.error(f"Error: {e}")

# --- TAB 3: Admin ---
with tab3:
    if st.text_input("Admin PIN:", type="password") == "9999":
        st.subheader("➕ เพิ่มข้อมูลโครงสร้าง 5 ระดับ")
        with st.form("admin_add"):
            c1, c2, c3, c4, c5 = st.columns(5)
            a_gate = c1.text_input("1.ประตู")
            a_zone = c2.text_input("2.ฝั่งถนน")
            a_soi = c3.text_input("3.ซอยหลัก")
            a_sub = c4.text_input("4.ซอยย่อย (-)")
            a_det = c5.text_input("5.จุดย่อย (-)")
            if st.form_submit_button("บันทึกโครงสร้าง"):
                if a_gate and a_soi:
                    sh = get_sheets()
                    sh.worksheet("Mapping").append_row([str(a_gate), str(a_zone), str(a_soi), str(a_sub), str(a_det)])
                    st.cache_data.clear()
                    st.success("บันทึกสำเร็จ!")
                    st.rerun()
