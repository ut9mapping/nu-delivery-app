import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. ตั้งค่าพื้นฐาน ---
st.set_page_config(page_title="NU Delivery Saver", layout="wide")

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])
    except Exception as e:
        st.error(f"❌ เชื่อ mindset ต่อ Google ไม่ได้: {e}")
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
    if mapping_df.empty or col_name not in mapping_df.columns: return ["-- เลือก --"]
    tmp = mapping_df.copy()
    for k, v in filters.items():
        if k in tmp.columns and v and v not in ["-- เลือก --"]:
            tmp = tmp[tmp[k] == str(v)]
    res = sorted([str(x) for x in tmp[col_name].unique() if x and str(x).lower() not in ["nan", "none", ""]])
    return ["-- เลือก --"] + res

# --- 2. หน้าจอหลัก (2 Tabs) ---
st.title("🛵 บันทึกพิกัด NU Delivery")

tab1, tab2 = st.tabs(["📌 บันทึกด่วน", "🗺️ อาณาเขต"])

with tab1:
    # ดึงพิกัด GPS
    location = streamlit_geolocation()
    curr_lat = location.get('latitude')
    curr_lon = location.get('longitude')
    
    if curr_lat:
        st.success(f"✅ GPS Locked: {curr_lat:.6f}, {curr_lon:.6f}")
    else:
        st.warning("📡 กำลังรอพิกัด GPS... (โปรดกดยอมรับสิทธิ์ระบุตำแหน่งในเบราว์เซอร์)")

    # ฟอร์มกรอกข้อมูล
    st.subheader("🏠 ข้อมูลสถานที่")
    p_name = st.text_input("ชื่อสถานที่ / บ้านเลขที่ (จำเป็น)")
    
    with st.expander("📍 ระบุรายละเอียดประตู/ซอย (ข้ามได้)", expanded=False):
        c1, c2 = st.columns(2)
        g = c1.selectbox("1. ประตู", get_opts("ประตู"))
        z = c2.selectbox("2. ฝั่งถนน/โซน", get_opts("ฝั่งถนน/โซน", {"ประตู": g}))
        m = c1.selectbox("3. ซอยหลัก", get_opts("ซอยหลัก", {"ประตู": g, "ฝั่งถนน/โซน": z}))
        ms = c2.selectbox("4. ฝั่งซอยหลัก", get_opts("ฝั่งซอยหลัก", {"ประตู": g, "ฝั่งถนน/โซน": z, "ซอยหลัก": m}))
        sub = c1.selectbox("5. ซอยย่อย", get_opts("ซอยย่อย/ทางเชื่อม", {"ประตู": g, "ฝั่งถนน/โซน": z, "ซอยหลัก": m, "ฝั่งซอยหลัก": ms}))
        det = c2.selectbox("6. ฝั่งของซอยย่อย", get_opts("ฝั่งของซอยย่อย", {"ประตู": g, "ฝั่งถนน/โซน": z, "ซอยหลัก": m, "ฝั่งซอยหลัก": ms, "ซอยย่อย/ทางเชื่อม": sub}))

    note = st.text_area("🗒️ หมายเหตุ")

    # ปุ่มบันทึกแบบตรวจสอบละเอียด
    if st.button("🚀 บันทึกข้อมูลลง Google Sheets", use_container_width=True, type="primary"):
        # 1. เช็กพิกัดก่อน
        if not curr_lat or not curr_lon:
            st.error("❌ บันทึกไม่ได้: ระบบยังหาพิกัด GPS ไม่เจอ โปรดรอสักครู่")
        # 2. เช็กชื่อสถานที่
        elif not p_name:
            st.warning("⚠️ โปรดระบุชื่อสถานที่หรือบ้านเลขที่")
        else:
            with st.spinner("กำลังบันทึกข้อมูล..."):
                try:
                    sh = get_sheets()
                    if sh:
                        worksheet = sh.worksheet("Sheet1")
                        
                        # รวมเส้นทางตำแหน่ง
                        path_list = [g, z, m, ms, sub, det]
                        path_str = " > ".join([str(p) if p != "-- เลือก --" else "-" for p in path_list])
                        
                        # เตรียมข้อมูล 10 คอลัมน์ (A-J) ตามหัวข้อที่คุณตั้งไว้
                        row_to_add = [
                            datetime.now().strftime("%Y-%m-%d %H:%M"), # A: timestamp
                            path_str,       # B: location_path
                            curr_lat,       # C: lat
                            curr_lon,       # D: lon
                            p_name,         # E: place_name
                            "", "", "",     # F, G, H: รูปภาพ (ว่าง)
                            note,           # I: note
                            "Complete"      # J: status
                        ]
                        
                        # คำสั่งบันทึกจริง
                        worksheet.append_row(row_to_add)
                        
                        st.balloons()
                        st.success(f"✅ บันทึกสำเร็จ! ข้อมูล '{p_name}' เข้าสู่ Google Sheets แล้ว")
                        st.cache_data.clear() # อัปเดตข้อมูลทันที
                    else:
                        st.error("❌ ไม่สามารถเปิดไฟล์ Google Sheets ได้ (ตรวจสอบ SHEET_ID)")
                except Exception as e:
                    # ถ้าบันทึกไม่ได้ จะโชว์ Error ตรงนี้
                    st.error(f"❌ เกิดข้อผิดพลาดขณะบันทึก: {e}")
                    st.info("💡 คำแนะนำ: ตรวจสอบว่าได้แชร์สิทธิ์ 'Editor' ให้กับอีเมลใน Secrets หรือยัง?")

# --- TAB 2: อาณาเขต (No-Refresh) ---
@st.fragment
def show_territory():
    st.subheader("🗺️ อาณาเขตพิกัดทั้งหมด")
    q = st.text_input("🔍 ค้นหา (หน้าไม่รีเฟรช):")
    
    _, current_df = load_data()
    if not current_df.empty:
        current_df['lat'] = pd.to_numeric(current_df['lat'], errors='coerce')
        current_df['lon'] = pd.to_numeric(current_df['lon'], errors='coerce')
        df = current_df.dropna(subset=['lat', 'lon'])

        if q:
            df = df[df.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)]

        if not df.empty:
            st.pydeck_chart(pdk.Deck(
                initial_view_state=pdk.ViewState(latitude=df['lat'].mean(), longitude=df['lon'].mean(), zoom=14),
                layers=[pdk.Layer("ScatterplotLayer", df, get_position='[lon, lat]', get_color='[0, 200, 0, 160]', get_radius=25, pickable=True)],
                tooltip={"text": "{place_name}\n{location_path}"}
            ))
            st.dataframe(df[["timestamp", "place_name", "location_path"]], use_container_width=True)
        else:
            st.info("ไม่พบข้อมูล")
    else:
        st.info("ยังไม่มีข้อมูลในระบบ")

with tab2:
    show_territory()
