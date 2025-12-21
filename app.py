import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. การตั้งค่าเริ่มต้น ---
st.set_page_config(page_title="NU Delivery Pro", layout="wide")

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])
    except Exception as e:
        st.error(f"❌ เชื่อมต่อ Google Sheets ไม่สำเร็จ: {e}")
        return None

@st.cache_data(ttl=5) # แคชข้อมูล 5 วินาทีเพื่อให้แอปลื่น
def load_data():
    sh = get_sheets()
    if not sh: return pd.DataFrame(), pd.DataFrame()
    try:
        m_df = pd.DataFrame(sh.worksheet("Mapping").get_all_records()).astype(str)
        l_df = pd.DataFrame(sh.worksheet("Sheet1").get_all_records())
    except:
        m_df, l_df = pd.DataFrame(), pd.DataFrame()
    return m_df, l_df

mapping_df, log_df = load_data()

# --- 2. ส่วนฟังก์ชันบันทึกข้อมูล (ทำงานเบื้องหลัง) ---
def save_to_gsheet(data_list):
    try:
        sh = get_sheets()
        sh.worksheet("Sheet1").append_row(data_list)
        return True
    except Exception as e:
        st.error(f"บันทึกไม่สำเร็จ: {e}")
        return False

# --- 3. หน้าจอหลักและการจัดการ UI ---
st.title("📍 NU Delivery Territory Management")

tab1, tab2, tab3 = st.tabs(["📌 บันทึกงาน", "🔍 ค้นหาและแผนที่", "⚙️ Admin"])

# --- Tab 1: บันทึกงาน (ใช้ Form เพื่อลดการรีเฟรช) ---
with tab1:
    loc = streamlit_geolocation()
    if loc.get('latitude'):
        lat, lon = loc['latitude'], loc['longitude']
        st.success(f"GPS Lock: {lat}, {lon}")
        
        # ส่วนเลือกตำแหน่ง (กรอง 6 ระดับ)
        def get_opts(col, filters={}):
            tmp = mapping_df.copy()
            for k, v in filters.items():
                if v and v != "-- เลือก --": tmp = tmp[tmp[k] == v]
            return ["-- เลือก --"] + sorted([x for x in tmp[col].unique() if x and x != "nan"])

        g = st.selectbox("1. ประตู", get_opts("ประตู"))
        z = st.selectbox("2. โซน", get_opts("ฝั่งถนน/โซน", {"ประตู": g}))
        m = st.selectbox("3. ซอยหลัก", get_opts("ซอยหลัก", {"ประตู": g, "ฝั่งถนน/โซน": z}))
        ms = st.selectbox("4. ฝั่งซอยหลัก", get_opts("ฝั่งซอยหลัก", {"ประตู": g, "ฝั่งถนน/โซน": z, "ซอยหลัก": m}))
        s = st.selectbox("5. ซอยย่อย", get_opts("ซอยย่อย/ทางเชื่อม", {"ประตู": g, "ฝั่งถนน/โซน": z, "ซอยหลัก": m, "ฝั่งซอยหลัก": ms}))
        d = st.selectbox("6. ฝั่งของซอยย่อย", get_opts("ฝั่งของซอยย่อย", {"ประตู": g, "ฝั่งถนน/โซน": z, "ซอยหลัก": m, "ฝั่งซอยหลัก": ms, "ซอยย่อย/ทางเชื่อม": s}))

        with st.form("entry_form", clear_on_submit=True):
            p_name = st.text_input("ชื่อสถานที่/บ้านเลขที่")
            note = st.text_area("หมายเหตุ")
            st.write("📸 รูปภาพ 3 รูป (เลือกไฟล์)")
            i1 = st.file_uploader("รูปที่ 1", type=['jpg','png'])
            i2 = st.file_uploader("รูปที่ 2", type=['jpg','png'])
            i3 = st.file_uploader("รูปที่ 3", type=['jpg','png'])
            
            if st.form_submit_button("🚀 บันทึกข้อมูล"):
                if g == "-- เลือก --" or not p_name:
                    st.error("กรุณาเลือกตำแหน่งและกรอกชื่อสถานที่")
                else:
                    path = f"{g}|{z}|{m}|{ms}|{s}|{d}"
                    status = "Complete" if i1 else "Incomplete"
                    row = [datetime.now().strftime("%Y-%m-%d %H:%M"), path, lat, lon, p_name, 
                           i1.name if i1 else "", i2.name if i2 else "", i3.name if i3 else "", 
                           note, status]
                    
                    if save_to_gsheet(row):
                        st.success("✅ บันทึกสำเร็จ! ข้อมูลถูกส่งไปที่ Google Sheets แล้ว")
                        st.balloons()
    else:
        st.warning("กรุณาเปิด GPS เพื่อเริ่มบันทึกงาน")

# --- Tab 2: ค้นหาและแผนที่ (ใช้ Fragment เพื่อไม่ให้รีเฟรชหน้า) ---
@st.fragment
def search_and_map_section():
    st.subheader("🔍 ค้นหาและดูพื้นที่ครอบคลุม")
    q = st.text_input("ค้นหาชื่อสถานที่ หรือ ซอย (ไม่ต้องกด Enter หน้าจะไม่รีเฟรช)")
    
    # ดึงข้อมูลล่าสุด
    _, current_log = load_data()
    
    if not current_log.empty:
        # แปลงพิกัดเป็นตัวเลข
        current_log['lat'] = pd.to_numeric(current_log['lat'], errors='coerce')
        current_log['lon'] = pd.to_numeric(current_log['lon'], errors='coerce')
        df = current_log.dropna(subset=['lat', 'lon'])

        if q:
            mask = df.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)
            df = df[mask]

        if not df.empty:
            df['color'] = df['status'].apply(lambda x: [0, 255, 0, 150] if x == "Complete" else [255, 0, 0, 150])
            
            st.pydeck_chart(pdk.Deck(
                map_style='mapbox://styles/mapbox/light-v9',
                initial_view_state=pdk.ViewState(latitude=df['lat'].mean(), longitude=df['lon'].mean(), zoom=14, pitch=45),
                layers=[pdk.Layer("ScatterplotLayer", df, get_position='[lon, lat]', get_color='color', get_radius=15, pickable=True)],
                tooltip={"text": "สถานที่: {place_name}\nสถานะ: {status}"}
            ))
            st.dataframe(df[["timestamp", "place_name", "status", "location_path"]], use_container_width=True)
        else:
            st.info("ไม่พบข้อมูลที่ค้นหา")
    else:
        st.info("ยังไม่มีข้อมูลในระบบ")

with tab2:
    search_and_map_section()

# --- Tab 3: Admin (ระบบ PIN) ---
with tab3:
    if 'auth' not in st.session_state: st.session_state.auth = False
    if not st.session_state.auth:
        pw = st.text_input("รหัส Admin", type="password")
        if pw == "9999": 
            st.session_state.auth = True
            st.rerun()
    else:
        st.write("✅ โหมดแอดมิน: คุณสามารถจัดการโครงสร้าง Mapping ได้ใน Google Sheets โดยตรง")
        if st.button("Logout"):
            st.session_state.auth = False
            st.rerun()
