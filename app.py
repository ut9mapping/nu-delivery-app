import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. ตั้งค่าการเชื่อมต่อ ---
st.set_page_config(page_title="NU Delivery Pro", layout="wide")

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])
    except Exception as e:
        st.error(f"❌ เชื่อมต่อไม่ได้: {e}")
        return None

@st.cache_data(ttl=2)
def load_data():
    sh = get_sheets()
    if not sh: return pd.DataFrame(), pd.DataFrame()
    
    # ดึงข้อมูล Mapping
    try:
        m_sheet = sh.worksheet("Mapping")
        m_df = pd.DataFrame(m_sheet.get_all_records())
        # 🔥 แก้ KeyError: ล้างช่องว่างในชื่อคอลัมน์และข้อมูลทั้งหมด
        m_df.columns = [str(c).strip() for c in m_df.columns]
        m_df = m_df.astype(str).map(lambda x: x.strip())
    except:
        m_df = pd.DataFrame(columns=["ประตู", "ฝั่งถนน/โซน", "ซอยหลัก", "ฝั่งซอยหลัก", "ซอยย่อย/ทางเชื่อม", "ฝั่งของซอยย่อย"])

    # ดึงข้อมูลการบันทึก (Sheet1)
    try:
        l_sheet = sh.worksheet("Sheet1")
        l_df = pd.DataFrame(l_sheet.get_all_records())
        l_df.columns = [str(c).strip() for c in l_df.columns]
    except:
        l_df = pd.DataFrame(columns=["timestamp", "location_path", "lat", "lon", "place_name", "img1", "img2", "img3", "note", "status"])
    
    return m_df, l_df

mapping_df, log_df = load_data()

# --- 2. ฟังก์ชันช่วยเลือก (Helper) ---
def get_opts(col, filters={}):
    if mapping_df.empty or col not in mapping_df.columns:
        return ["-- ไม่มีข้อมูล --"]
    tmp = mapping_df.copy()
    for k, v in filters.items():
        if v and v != "-- เลือก --":
            tmp = tmp[tmp[k] == v]
    res = sorted([x for x in tmp[col].unique() if x and x not in ["nan", "None", ""]])
    return ["-- เลือก --"] + res

# --- 3. ส่วนแสดงผลหลัก ---
st.title("📍 NU Delivery: Territory System")

# ใช้พื้นที่ Sidebar ในการตรวจสอบสถานะ (จะได้ไม่กวนหน้าหลัก)
with st.sidebar:
    if st.button("🔄 รีโหลดข้อมูลใหม่"):
        st.cache_data.clear()
        st.rerun()
    if not mapping_df.empty:
        st.write("✅ คอลัมน์ที่ตรวจพบ:", list(mapping_df.columns))

tab1, tab2 = st.tabs(["📌 บันทึกงาน", "🔍 ค้นหาและแผนที่"])

# --- TAB 1: บันทึกงาน (ใช้ Form เพื่อลดการรีเฟรชหน้า) ---
with tab1:
    loc = streamlit_geolocation()
    if loc.get('latitude'):
        lat, lon = loc['latitude'], loc['longitude']
        st.success(f"GPS พิกัดปัจจุบัน: {lat}, {lon}")

        # ส่วนกรอง 6 ระดับ
        c1, c2 = st.columns(2)
        g = c1.selectbox("1. ประตู", get_opts("ประตู"))
        z = c2.selectbox("2. โซน", get_opts("ฝั่งถนน/โซน", {"ประตู": g}))
        
        c3, c4 = st.columns(2)
        m = c3.selectbox("3. ซอยหลัก", get_opts("ซอยหลัก", {"ประตู": g, "ฝั่งถนน/โซน": z}))
        ms = c4.selectbox("4. ฝั่งซอยหลัก", get_opts("ฝั่งซอยหลัก", {"ประตู": g, "ฝั่งถนน/โซน": z, "ซอยหลัก": m}))
        
        c5, c6 = st.columns(2)
        s = c5.selectbox("5. ซอยย่อย", get_opts("ซอยย่อย/ทางเชื่อม", {"ประตู": g, "ฝั่งถนน/โซน": z, "ซอยหลัก": m, "ฝั่งซอยหลัก": ms}))
        d = c6.selectbox("6. ฝั่งของซอยย่อย", get_opts("ฝั่งของซอยย่อย", {"ประตู": g, "ฝั่งถนน/โซน": z, "ซอยหลัก": m, "ฝั่งซอยหลัก": ms, "ซอยย่อย/ทางเชื่อม": s}))

        with st.form("save_form", clear_on_submit=True):
            p_name = st.text_input("ชื่อสถานที่/บ้านเลขที่")
            p_note = st.text_area("หมายเหตุ")
            
            if st.form_submit_button("🚀 บันทึกเข้า Google Sheets", use_container_width=True):
                if g == "-- เลือก --" or not p_name:
                    st.error("❌ กรุณาเลือกตำแหน่งและกรอกชื่อสถานที่")
                else:
                    path = f"{g}>{z}>{m}>{ms}>{s}>{d}"
                    new_row = [datetime.now().strftime("%Y-%m-%d %H:%M"), path, lat, lon, p_name, "", "", "", p_note, "Incomplete"]
                    
                    try:
                        sh = get_sheets()
                        sh.worksheet("Sheet1").append_row(new_row)
                        st.balloons()
                        st.success("✅ บันทึกสำเร็จ!")
                    except Exception as e:
                        st.error(f"❌ บันทึกไม่สำเร็จ: {e}")
    else:
        st.warning("⚠️ โปรดรอสักครู่เพื่อดึงพิกัด GPS...")

# --- TAB 2: ค้นหาและแผนที่ (ใช้ Fragment เพื่อ No-Refresh) ---
@st.fragment
def search_section():
    st.subheader("🔍 ค้นหาพิกัดพื้นที่")
    q = st.text_input("พิมพ์เพื่อค้นหา (หน้าเพจจะไม่รีเฟรช)", placeholder="เช่น ชื่อหอพัก, ซอย...")
    
    _, df_search = load_data() # ดึงข้อมูลล่าสุด
    
    if not df_search.empty:
        # เตรียมพิกัด
        df_search['lat'] = pd.to_numeric(df_search['lat'], errors='coerce')
        df_search['lon'] = pd.to_numeric(df_search['lon'], errors='coerce')
        df_clean = df_search.dropna(subset=['lat', 'lon'])

        if q:
            mask = df_clean.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)
            df_clean = df_clean[mask]

        if not df_clean.empty:
            # วาดแผนที่
            st.pydeck_chart(pdk.Deck(
                initial_view_state=pdk.ViewState(latitude=df_clean['lat'].mean(), longitude=df_clean['lon'].mean(), zoom=14),
                layers=[pdk.Layer("ScatterplotLayer", df_clean, get_position='[lon, lat]', get_color='[0, 200, 0, 150]', get_radius=20, pickable=True)],
                tooltip={"text": "ที่อยู่: {place_name}\nเส้นทาง: {location_path}"}
            ))
            st.dataframe(df_clean[["timestamp", "place_name", "location_path"]], use_container_width=True)
        else:
            st.info("ไม่พบข้อมูล")

with tab2:
    search_section()
