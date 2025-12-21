import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. ตั้งค่าพื้นฐาน ---
st.set_page_config(page_title="NU Delivery Pro", layout="wide")

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])
    except Exception as e:
        st.error(f"❌ เชื่อมต่อ Google Sheets ไม่สำเร็จ: {e}")
        return None

@st.cache_data(ttl=2)
def load_data():
    sh = get_sheets()
    if not sh: return pd.DataFrame(), pd.DataFrame()
    
    # โหลด Mapping
    try:
        m_sheet = sh.worksheet("Mapping").get_all_records()
        m_df = pd.DataFrame(m_sheet)
        # ล้างช่องว่างในชื่อคอลัมน์ทั้งหมด (ป้องกัน KeyError)
        m_df.columns = [str(c).strip() for c in m_df.columns]
        m_df = m_df.astype(str).map(lambda x: x.strip())
    except:
        m_df = pd.DataFrame()

    # โหลดประวัติงาน (Sheet1)
    try:
        l_sheet = sh.worksheet("Sheet1").get_all_records()
        l_df = pd.DataFrame(l_sheet)
        l_df.columns = [str(c).strip() for c in l_df.columns]
    except:
        l_df = pd.DataFrame()
    
    return m_df, l_df

mapping_df, log_df = load_data()

# --- 2. ฟังก์ชันช่วยดึงตัวเลือก (แก้ไขป้องกัน KeyError) ---
def get_opts(col, filters={}):
    if mapping_df.empty or col not in mapping_df.columns:
        return ["-- เลือก --"]
    
    tmp = mapping_df.copy()
    for k, v in filters.items():
        # ตรวจสอบว่ามีชื่อคอลัมน์ k อยู่จริงก่อนกรอง
        if k in tmp.columns and v and v != "-- เลือก --":
            tmp = tmp[tmp[k] == v]
            
    if col in tmp.columns:
        res = sorted([x for x in tmp[col].unique() if x and str(x).lower() not in ["nan", "none", ""]])
        return ["-- เลือก --"] + res
    return ["-- เลือก --"]

# --- 3. หน้าเว็บแบบ 3 แถบ (Tabs) ---
st.title("📍 NU Delivery: ระบบบริหารอาณาเขต")

tab1, tab2, tab3 = st.tabs(["📌 บันทึกงานใหม่", "🔍 แผนที่และค้นหา", "⚙️ ตั้งค่าแอดมิน"])

# --- แถบที่ 1: บันทึกงาน ---
with tab1:
    loc = streamlit_geolocation()
    if loc.get('latitude'):
        lat, lon = loc['latitude'], loc['longitude']
        st.success(f"✅ พิกัดพร้อม: {lat}, {lon}")

        # ส่วนกรองตำแหน่ง 6 ระดับ (แสดงผลแบบ 2 คอลัมน์เพื่อให้หน้าเว็บไม่ยาวเกินไป)
        col_a, col_b = st.columns(2)
        g = col_a.selectbox("1. ประตู", get_opts("ประตู"))
        z = col_b.selectbox("2. โซน", get_opts("ฝั่งถนน/โซน", {"ประตู": g}))
        
        main = col_a.selectbox("3. ซอยหลัก", get_opts("ซอยหลัก", {"ประตู": g, "ฝั่งถนน/โซน": z}))
        ms = col_b.selectbox("4. ฝั่งซอยหลัก", get_opts("ฝั่งซอยหลัก", {"ประตู": g, "ฝั่งถนน/โซน": z, "ซอยหลัก": main}))
        
        sub = col_a.selectbox("5. ซอยย่อย", get_opts("ซอยย่อย/ทางเชื่อม", {"ประตู": g, "ฝั่งถนน/โซน": z, "ซอยหลัก": main, "ฝั่งซอยหลัก": ms}))
        det = col_b.selectbox("6. ฝั่งของซอยย่อย", get_opts("ฝั่งของซอยย่อย", {"ประตู": g, "ฝั่งถนน/โซน": z, "ซอยหลัก": main, "ฝั่งซอยหลัก": ms, "ซอยย่อย/ทางเชื่อม": sub}))

        with st.form("main_entry", clear_on_submit=True):
            p_name = st.text_input("🏠 ชื่อสถานที่ / บ้านเลขที่")
            note = st.text_area("📝 หมายเหตุเพิ่มเติม")
            
            if st.form_submit_button("🚀 บันทึกพิกัดลงระบบ", use_container_width=True):
                if g == "-- เลือก --" or not p_name:
                    st.error("⚠️ กรุณาเลือกตำแหน่งให้ครบและระบุชื่อสถานที่")
                else:
                    try:
                        sh = get_sheets()
                        path = f"{g}|{z}|{main}|{ms}|{sub}|{det}"
                        new_data = [datetime.now().strftime("%Y-%m-%d %H:%M"), path, lat, lon, p_name, "", "", "", note, "Incomplete"]
                        sh.worksheet("Sheet1").append_row(new_data)
                        st.balloons()
                        st.success("✅ บันทึกข้อมูลสำเร็จแล้ว!")
                        st.cache_data.clear() # ล้างแคชเพื่อให้ Tab ค้นหาเห็นข้อมูลใหม่ทันที
                    except Exception as e:
                        st.error(f"❌ บันทึกไม่สำเร็จ: {e}")
    else:
        st.info("📡 กำลังดึงพิกัด GPS... (โปรดอนุญาตสิทธิ์เข้าถึงพิกัดในเบราว์เซอร์)")

# --- แถบที่ 2: แผนที่และค้นหา (ใช้ Fragment เพื่อ No-Refresh) ---
@st.fragment
def search_and_map():
    st.subheader("🔍 ค้นหาและตรวจสอบพื้นที่")
    q = st.text_input("พิมพ์ชื่อสถานที่ หรือชื่อซอย เพื่อค้นหา (หน้าเพจจะไม่รีเฟรช)")
    
    # โหลดข้อมูลล่าสุด
    _, current_log = load_data()
    
    if not current_log.empty:
        current_log['lat'] = pd.to_numeric(current_log['lat'], errors='coerce')
        current_log['lon'] = pd.to_numeric(current_log['lon'], errors='coerce')
        df = current_log.dropna(subset=['lat', 'lon'])

        if q:
            mask = df.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)
            df = df[mask]

        if not df.empty:
            # วาดแผนที่
            st.pydeck_chart(pdk.Deck(
                initial_view_state=pdk.ViewState(latitude=df['lat'].mean(), longitude=df['lon'].mean(), zoom=14, pitch=45),
                layers=[pdk.Layer("ScatterplotLayer", df, get_position='[lon, lat]', get_color='[0, 200, 0, 160]', get_radius=20, pickable=True)],
                tooltip={"text": "สถานที่: {place_name}\nสถานะ: {status}\nข้อมูล: {location_path}"}
            ))
            st.dataframe(df[["timestamp", "place_name", "location_path", "status"]], use_container_width=True)
        else:
            st.warning("ไม่พบข้อมูลที่ตรงกับการค้นหา")
    else:
        st.info("ยังไม่มีข้อมูลพิกัดในระบบ")

with tab2:
    search_and_map()

# --- แถบที่ 3: แอดมิน ---
with tab3:
    if 'admin_ok' not in st.session_state: st.session_state.admin_ok = False
    
    if not st.session_state.admin_ok:
        pw = st.text_input("กรอกรหัส Admin เพื่อตั้งค่า", type="password")
        if pw == "9999": 
            st.session_state.admin_ok = True
            st.rerun()
    else:
        st.success("✅ เข้าสู่โหมดแอดมินแล้ว")
        st.write("คุณสามารถจัดการโครงสร้าง Mapping ได้โดยตรงผ่าน Google Sheets")
        if st.button("ออกจากโหมดแอดมิน"):
            st.session_state.admin_ok = False
            st.rerun()
