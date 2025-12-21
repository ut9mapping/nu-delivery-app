import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. ตั้งค่าพื้นฐานและการเชื่อมต่อ ---
st.set_page_config(page_title="NU Delivery: Pro Territory", page_icon="📍", layout="wide")

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])
    except Exception as e:
        st.error(f"การเชื่อมต่อ Google Sheets ผิดพลาด: {e}")
        return None

@st.cache_data(ttl=2)
def load_all_data():
    sh = get_sheets()
    if not sh: return pd.DataFrame(), pd.DataFrame()
    
    # ดึงข้อมูล Mapping (โครงสร้างซอย)
    try:
        map_sheet = sh.worksheet("Mapping").get_all_records()
        map_df = pd.DataFrame(map_sheet).map(lambda x: str(x).strip() if x is not None else "")
    except:
        map_df = pd.DataFrame(columns=["ประตู", "ฝั่งถนน/โซน", "ซอยหลัก", "ฝั่งซอยหลัก", "ซอยย่อย/ทางเชื่อม", "ฝั่งของซอยย่อย"])

    # ดึงข้อมูลการบันทึกงาน (Sheet1)
    try:
        log_sheet = sh.worksheet("Sheet1").get_all_records()
        log_df = pd.DataFrame(log_sheet)
    except:
        log_df = pd.DataFrame(columns=["timestamp", "location_path", "lat", "lon", "place_name", "img1", "img2", "img3", "note", "status"])
    
    return map_df, log_df

# --- 2. จัดการสถานะระบบ ---
if 'admin_auth' not in st.session_state:
    st.session_state.admin_auth = False
if 'tree_data' not in st.session_state:
    st.session_state.tree_data = [{'main': '', 'sides': [{'side_name': '-', 'subs': [{'sub_name': '-', 'dets': ['-']}]}]}]

mapping_df, log_df = load_all_data()

# ฟังก์ชันช่วยกรองข้อมูลแบบปลอดภัย (Safe Sorting)
def get_safe_opts(df, filters, col_name):
    if df.empty or col_name not in df.columns: return []
    tmp = df.copy()
    for k, v in filters.items():
        if v and v != "-- เลือก --": tmp = tmp[tmp[k] == v]
    # แปลงเป็น string ทั้งหมดเพื่อป้องกัน TypeError ตอน sorted
    opts = tmp[col_name].astype(str).unique().tolist()
    return sorted([x for x in opts if x and x != "-" and x != "nan"])

# --- 3. UI ส่วนหลัก ---
st.title("📍 ระบบบริหารพิกัดอาณาเขต (Pro Version)")

tab1, tab2, tab3, tab4 = st.tabs(["📌 บันทึกงานใหม่", "🗺️ แผนที่อาณาเขต", "🔍 ค้นหา/ประวัติ", "⚙️ Admin Manage"])

# --- TAB 1: บันทึกงาน (ยืดหยุ่น + 3 รูปภาพ) ---
with tab1:
    location = streamlit_geolocation()
    if location.get('latitude'):
        lat, lon = location['latitude'], location['longitude']
        st.success(f"📍 GPS ตรวจพบพิกัดปัจจุบัน: {lat:.6f}, {lon:.6f}")
        
        # ส่วนเลือกตำแหน่ง (Real-time Filter)
        st.subheader("🔍 ระบุตำแหน่งพิกัด")
        g_list = mapping_df['ประตู'].astype(str).unique().tolist() if not mapping_df.empty else []
        gate = st.selectbox("1. ประตู:", ["-- เลือก --"] + sorted([x for x in g_list if x and x != "nan"]))
        
        c1, c2 = st.columns(2)
        zone = c1.selectbox("2. ฝั่งถนน/โซน:", ["-- เลือก --"] + get_safe_opts(mapping_df, {"ประตู": gate}, "ฝั่งถนน/โซน"))
        main = c2.selectbox("3. ซอยหลัก:", ["-- เลือก --"] + get_safe_opts(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone}, "ซอยหลัก"))
        
        c3, c4 = st.columns(2)
        m_side = c3.selectbox("4. ฝั่งซอยหลัก:", ["-- เลือก --"] + get_safe_opts(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main}, "ฝั่งซอยหลัก"))
        sub = c4.selectbox("5. ซอยย่อย/ทางเชื่อม:", ["-- เลือก --"] + get_safe_opts(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main, "ฝั่งซอยหลัก": m_side}, "ซอยย่อย/ทางเชื่อม"))
        
        det = st.selectbox("6. ฝั่งของซอยย่อย:", ["-- เลือก --"] + get_safe_opts(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main, "ฝั่งซอยหลัก": m_side, "ซอยย่อย/ทางเชื่อม": sub}, "ฝั่งของซอยย่อย"))

        with st.form("detail_entry"):
            st.subheader("🏠 รายละเอียดสถานที่")
            place_name = st.text_input("ชื่อสถานที่ / บ้านเลขที่ (ถ้ามี):")
            
            st.write("📸 รูปภาพประกอบ (สูงสุด 3 รูป):")
            ic1, ic2, ic3 = st.columns(3)
            i1 = ic1.file_uploader("รูปหน้าบ้าน", type=['jpg','png','jpeg'])
            i2 = ic2.file_uploader("รูปซอย/จุดสังเกต", type=['jpg','png','jpeg'])
            i3 = ic3.file_uploader("รูปอื่นๆ", type=['jpg','png','jpeg'])
            
            note = st.text_area("หมายเหตุเพิ่มเติม (สำหรับตามงาน):")
            
            if st.form_submit_button("🚀 บันทึกพิกัดและข้อมูล", use_container_width=True):
                # ตรวจสอบความสมบูรณ์: ต้องมีชื่อสถานที่และอย่างน้อย 1 รูปถึงจะเป็น Complete
                status = "Complete" if (place_name and i1) else "Incomplete"
                
                sh = get_sheets()
                sh.worksheet("Sheet1").append_row([
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                    f"{gate}|{zone}|{main}|{m_side}|{sub}|{det}",
                    lat, lon, place_name, 
                    i1.name if i1 else "", i2.name if i2 else "", i3.name if i3 else "",
                    note, status
                ])
                st.balloons()
                st.success(f"บันทึกสำเร็จ! ข้อมูลนี้ถูกจัดเป็นสถานะ: {status}")

# --- TAB 2: แผนที่จำลองอาณาเขต ---
with tab2:
    st.header("🗺️ แผนที่พิกัดอาณาเขต")
    if not log_df.empty and 'lat' in log_df.columns:
        log_df['lat'] = pd.to_numeric(log_df['lat'], errors='coerce')
        log_df['lon'] = pd.to_numeric(log_df['lon'], errors='coerce')
        df_map = log_df.dropna(subset=['lat', 'lon'])
        
        # สีตามสถานะ: เขียว=ครบ, แดง=ไม่ครบ
        df_map['color'] = df_map['status'].apply(lambda x: [0, 200, 0, 160] if x == "Complete" else [255, 0, 0, 160])
        
        st.pydeck_chart(pdk.Deck(
            initial_view_state=pdk.ViewState(latitude=df_map['lat'].mean(), longitude=df_map['lon'].mean(), zoom=14, pitch=40),
            layers=[pdk.Layer("ScatterplotLayer", df_map, get_position='[lon, lat]', get_color='color', get_radius=12, pickable=True)],
            tooltip={"text": "ที่อยู่: {place_name}\nสถานะ: {status}\nข้อมูล: {location_path}"}
        ))
        st.markdown("🟢 **ข้อมูลครบ** | 🔴 **ข้อมูลไม่ครบ (รอป้อนย้อนหลัง)**")

# --- TAB 4: ADMIN MANAGE (ระบบ Subset 6 ระดับ + ซ่อน PIN) ---
with tab4:
    if not st.session_state.admin_auth:
        st.subheader("🔒 ยืนยันสิทธิ์ผู้ดูแลระบบ")
        pin = st.text_input("กรอกรหัส PIN (9999):", type="password")
        if pin == "9999":
            st.session_state.admin_auth = True
            st.rerun()
    else:
        c_h1, c_h2 = st.columns([8, 2])
        c_h1.header("⚙️ ตั้งค่าโครงสร้าง Subset (6 ระดับ)")
        if c_h2.button("🔒 Logout"):
            st.session_state.admin_auth = False; st.rerun()

        # ส่วนหัว (Gate & Zone)
        ca, cb = st.columns(2)
        gate_f = ca.text_input("ระบุชื่อประตู:", value="ประตู 1")
        zone_f = cb.text_input("ระบุฝั่งถนน/โซน:", value="โซน A")

        # ระบบ Tree Logic
        def add_m(): st.session_state.tree_data.append({'main': '', 'sides': [{'side_name': '-', 'subs': [{'sub_name': '-', 'dets': ['-']}]}]})
        def add_ms(mi): st.session_state.tree_data[mi]['sides'].append({'side_name': '', 'subs': [{'sub_name': '-', 'dets': ['-']}]})
        def add_s(mi, msi): st.session_state.tree_data[mi]['sides'][msi]['subs'].append({'sub_name': '', 'dets': ['-']})
        def add_d(mi, msi, si): st.session_state.tree_data[mi]['sides'][msi]['subs'][si]['dets'].append('')

        for mi, mn in enumerate(st.session_state.tree_data):
            with st.container(border=True):
                mn['main'] = st.text_input(f"📍 ซอยหลัก {mi+1}", value=mn['main'], key=f"m_{mi}")
                for msi, msn in enumerate(mn['sides']):
                    msn['side_name'] = st.text_input(f"  ↳ ฝั่งของซอยหลัก {msi+1}", value=msn['side_name'], key=f"ms_{mi}_{msi}")
                    for si, sn in enumerate(msn['subs']):
                        sn['sub_name'] = st.text_input(f"    ↳ ซอยย่อย {si+1}", value=sn['sub_name'], key=f"s_{mi}_{msi}_{si}")
                        for di, dv in enumerate(sn['dets']):
                            # แก้ชื่อตามที่ต้องการ: ฝั่งของซอยย่อย
                            sn['dets'][di] = st.text_input(f"      ↳ ฝั่งของซอยย่อย {di+1}", value=dv, key=f"d_{mi}_{msi}_{si}_{di}")
                        st.button(f"➕ เพิ่มฝั่งของซอยย่อย", on_click=add_d, args=(mi, msi, si), key=f"bd_{mi}_{msi}_{si}")
                    st.button(f"➕ เพิ่มซอยย่อย", on_click=add_s, args=(mi, msi), key=f"bs_{mi}_{msi}")
                st.button(f"➕ เพิ่มฝั่งของซอยหลัก", on_click=add_ms, args=(mi,), key=f"bms_{mi}")
        
        st.button("➕ เพิ่มซอยหลักใหม่", on_click=add_m)

        if st.button("💾 บันทึกโครงสร้างทั้งหมด", type="primary", use_container_width=True):
            final_rows = []
            for m in st.session_state.tree_data:
                for ms in m['sides']:
                    for s in ms['subs']:
                        for d in s['dets']:
                            final_rows.append([gate_f, zone_f, m['main'], ms['side_name'], s['sub_name'], d])
            sh = get_sheets()
            sh.worksheet("Mapping").append_rows(final_rows)
            st.success("บันทึกโครงสร้างสำเร็จ!")
            st.session_state.tree_data = [{'main': '', 'sides': [{'side_name': '-', 'subs': [{'sub_name': '-', 'dets': ['-']}]}]}]
            st.cache_data.clear(); st.rerun()
