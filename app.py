import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. ตั้งค่าระบบและการเชื่อมต่อ ---
st.set_page_config(page_title="NU Delivery EasySave", layout="wide")

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])
    except Exception as e:
        st.error(f"❌ ระบบเชื่อมต่อ Google Sheets ไม่ได้: {e}")
        return None

@st.cache_data(ttl=2)
def load_data():
    sh = get_sheets()
    if not sh: return pd.DataFrame(), pd.DataFrame()
    try:
        m_df = pd.DataFrame(sh.worksheet("Mapping").get_all_records())
        m_df.columns = [str(c).strip() for c in m_df.columns]
    except: m_df = pd.DataFrame()
    try:
        l_df = pd.DataFrame(sh.worksheet("Sheet1").get_all_records())
        l_df.columns = [str(c).strip() for c in l_df.columns]
    except: l_df = pd.DataFrame()
    return m_df, l_df

mapping_df, log_df = load_data()

def get_opts(col_name, filters={}):
    if mapping_df.empty or col_name not in mapping_df.columns: return ["-- ไม่ระบุ --"]
    tmp = mapping_df.copy()
    for k, v in filters.items():
        if k in tmp.columns and v and v not in ["-- เลือก --", "-- ไม่ระบุ --"]:
            tmp = tmp[tmp[k] == v]
    res = sorted([x for x in tmp[col_name].unique() if x and str(x).lower() not in ["nan", "none", ""]])
    return ["-- เลือก --"] + res

# --- 2. หน้าจอหลัก (Tabs) ---
st.title("🛵 NU Delivery Pro (Easy Record)")

tab1, tab2 = st.tabs(["📌 บันทึกงาน (ด่วน)", "🗺️ แผนที่อาณาเขต"])

# --- TAB 1: บันทึกงาน (ยืดหยุ่น ไม่บังคับกรอกครบ) ---
with tab1:
    location = streamlit_geolocation()
    lat, lon = location.get('latitude'), location.get('longitude')
    
    if lat:
        st.success(f"📍 GPS Lock: {lat}, {lon}")
    else:
        st.warning("📡 กำลังรอพิกัด GPS... โปรดอนุญาตสิทธิ์ระบุตำแหน่ง")

    st.subheader("🏠 ข้อมูลสถานที่")
    place_name = st.text_input("ชื่อสถานที่ / บ้านเลขที่ (จำเป็น)", placeholder="เช่น หอพัก ABC, บ้านเลขที่ 123/4")
    
    with st.expander("📍 ระบุรายละเอียดซอย (ไม่บังคับ)", expanded=False):
        c1, c2 = st.columns(2)
        g = c1.selectbox("1. ประตู", get_opts("ประตู"))
        z = c2.selectbox("2. ฝั่งถนน/โซน", get_opts("ฝั่งถนน/โซน", {"ประตู": g}))
        m = c1.selectbox("3. ซอยหลัก", get_opts("ซอยหลัก", {"ประตู": g, "ฝั่งถนน/โซน": z}))
        ms = c2.selectbox("4. ฝั่งซอยหลัก", get_opts("ฝั่งซอยหลัก", {"ประตู": g, "ฝั่งถนน/โซน": z, "ซอยหลัก": m}))
        s = c1.selectbox("5. ซอยย่อย", get_opts("ซอยย่อย/ทางเชื่อม", {"ประตู": g, "ฝั่งถนน/โซน": z, "ซอยหลัก": m, "ฝั่งซอยหลัก": ms}))
        d = c2.selectbox("6. ฝั่งของซอยย่อย", get_opts("ฝั่งของซอยย่อย", {"ประตู": g, "ฝั่งถนน/โซน": z, "ซอยหลัก": m, "ฝั่งซอยหลัก": ms, "ซอยย่อย/ทางเชื่อม": s}))

    note = st.text_area("🗒️ หมายเหตุเพิ่มเติม")

    if st.button("🚀 บันทึกข้อมูลทันที", use_container_width=True, type="primary"):
        if not lat or not lon:
            st.error("❌ ไม่สามารถบันทึกได้: ไม่พบพิกัด GPS")
        elif not place_name:
            st.error("❌ ไม่สามารถบันทึกได้: กรุณากรอกชื่อสถานที่")
        else:
            try:
                # รวมเส้นทาง (ถ้าไม่ได้เลือกให้ใส่เป็น -)
                path_parts = [g, z, m, ms, s, d]
                clean_path = " > ".join([p if p not in ["-- เลือก --", "-- ไม่ระบุ --"] else "-" for p in path_parts])
                
                sh = get_sheets()
                # เตรียมข้อมูล 10 คอลัมน์ (A-J)
                new_row = [
                    datetime.now().strftime("%Y-%m-%d %H:%M"), # A: timestamp
                    clean_path, # B: location_path
                    lat, lon,   # C, D: พิกัด
                    place_name, # E: place_name
                    "", "", "", # F, G, H: รูปว่าง
                    note,       # I: note
                    "Complete"  # J: status
                ]
                sh.worksheet("Sheet1").append_row(new_row)
                st.balloons()
                st.success(f"✅ บันทึก '{place_name}' ลงระบบเรียบร้อยแล้ว!")
                st.cache_data.clear() # ล้างแคชเพื่อให้แผนที่อัปเดต
            except Exception as e:
                st.error(f"❌ บันทึกไม่สำเร็จ: {e}")

# --- TAB 2: แผนที่ (No-Refresh Search) ---
@st.fragment
def territory_map():
    st.subheader("🗺️ แผนที่พิกัดทั้งหมด")
    q = st.text_input("🔍 ค้นหาด่วน (หน้าไม่รีเฟรช):", placeholder="ชื่อสถานที่ หรือ ชื่อซอย...")
    
    _, current_df = load_data()
    if not current_df.empty:
        current_df['lat'] = pd.to_numeric(current_df['lat'], errors='coerce')
        current_df['lon'] = pd.to_numeric(current_df['lon'], errors='coerce')
        df = current_df.dropna(subset=['lat', 'lon'])

        if q:
            mask = df.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)
            df = df[mask]

        if not df.empty:
            st.pydeck_chart(pdk.Deck(
                initial_view_state=pdk.ViewState(latitude=df['lat'].mean(), longitude=df['lon'].mean(), zoom=14),
                layers=[pdk.Layer("ScatterplotLayer", df, get_position='[lon, lat]', get_color='[0, 200, 0, 160]', get_radius=25, pickable=True)],
                tooltip={"text": "{place_name}\n{location_path}"}
            ))
            st.dataframe(df[["timestamp", "place_name", "location_path", "note"]], use_container_width=True)
        else:
            st.info("ไม่พบข้อมูลที่ค้นหา")
    else:
        st.info("ยังไม่มีข้อมูลในระบบ")

with tab2:
    territory_map()
