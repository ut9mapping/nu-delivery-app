import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. การตั้งค่าหน้าจอและการเชื่อมต่อ ---
st.set_page_config(page_title="NU Delivery Pro", page_icon="🛵", layout="wide")

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])
    except Exception as e:
        st.error(f"เชื่อมต่อ Google Sheets ไม่สำเร็จ: {e}")
        return None

@st.cache_data(ttl=1)
def load_all_data():
    sh = get_sheets()
    if not sh: return pd.DataFrame(), pd.DataFrame()
    
    # โหลดข้อมูล Mapping (โครงสร้าง)
    try:
        m_df = pd.DataFrame(sh.worksheet("Mapping").get_all_records())
        m_df = m_df.astype(str).map(lambda x: x.strip())
    except:
        m_df = pd.DataFrame(columns=["ประตู", "ฝั่งถนน/โซน", "ซอยหลัก", "ฝั่งซอยหลัก", "ซอยย่อย/ทางเชื่อม", "ฝั่งของซอยย่อย"])

    # โหลดข้อมูลการบันทึกงาน (Sheet1)
    try:
        l_df = pd.DataFrame(sh.worksheet("Sheet1").get_all_records())
        # ตรวจสอบคอลัมน์สำคัญ
        for col in ["lat", "lon", "status", "place_name"]:
            if col not in l_df.columns: l_df[col] = ""
    except:
        l_df = pd.DataFrame(columns=["timestamp", "location_path", "lat", "lon", "place_name", "img1", "img2", "img3", "note", "status"])
    
    return m_df, l_df

# --- 2. สถานะระบบ (Session State) ---
if 'admin_auth' not in st.session_state:
    st.session_state.admin_auth = False
if 'tree_data' not in st.session_state:
    st.session_state.tree_data = [{'main': '', 'sides': [{'side_name': '-', 'subs': [{'sub_name': '-', 'dets': ['-']}]}]}]

mapping_df, log_df = load_all_data()

# ฟังก์ชันกรองข้อมูลแบบปลอดภัย (Safe Filter & Sort)
def safe_opts(df, filters, col_name):
    if df.empty or col_name not in df.columns: return []
    tmp = df.copy()
    for k, v in filters.items():
        if v and v != "-- เลือก --": tmp = tmp[tmp[k] == v]
    res = sorted(tmp[col_name].astype(str).unique().tolist())
    return [x for x in res if x and x not in ["-", "nan", "None"]]

# --- 3. UI ส่วนหลัก ---
st.title("🛵 ระบบบริหารพิกัดอาณาเขต NU Delivery")

tab1, tab2, tab3, tab4 = st.tabs(["📌 บันทึกงาน", "🗺️ แผนที่อาณาเขต", "🔍 ค้นหา", "⚙️ Admin Manage"])

# --- TAB 1: บันทึกงาน (6 ระดับ + 3 รูป) ---
with tab1:
    location = streamlit_geolocation()
    if location.get('latitude'):
        lat, lon = location['latitude'], location['longitude']
        st.success(f"📍 GPS ตรวจพบ: {lat:.6f}, {lon:.6f}")
        
        # ส่วนเลือกตำแหน่ง (Real-time Filtering นอก Form)
        st.subheader("🔍 ระบุตำแหน่ง")
        gate = st.selectbox("1. ประตู:", ["-- เลือก --"] + safe_opts(mapping_df, {}, "ประตู"))
        
        c1, c2 = st.columns(2)
        zone = c1.selectbox("2. ฝั่งถนน/โซน:", ["-- เลือก --"] + safe_opts(mapping_df, {"ประตู": gate}, "ฝั่งถนน/โซน"))
        main = c2.selectbox("3. ซอยหลัก:", ["-- เลือก --"] + safe_opts(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone}, "ซอยหลัก"))
        
        c3, c4 = st.columns(2)
        m_side = c3.selectbox("4. ฝั่งซอยหลัก:", ["-- เลือก --"] + safe_opts(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main}, "ฝั่งซอยหลัก"))
        sub = c4.selectbox("5. ซอยย่อย/ทางเชื่อม:", ["-- เลือก --"] + safe_opts(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main, "ฝั่งซอยหลัก": m_side}, "ซอยย่อย/ทางเชื่อม"))
        
        det = st.selectbox("6. ฝั่งของซอยย่อย:", ["-- เลือก --"] + safe_opts(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main, "ฝั่งซอยหลัก": m_side, "ซอยย่อย/ทางเชื่อม": sub}, "ฝั่งของซอยย่อย"))

        # ส่วนกรอกข้อมูลรายละเอียด (ใน Form)
        with st.form("work_form"):
            st.subheader("🏠 ข้อมูลสถานที่")
            p_name = st.text_input("ชื่อสถานที่ / บ้านเลขที่:")
            
            st.write("📸 รูปภาพสถานที่ (3 รูป):")
            ic1, ic2, ic3 = st.columns(3)
            i1 = ic1.file_uploader("รูปหน้าบ้าน", type=['jpg','png','jpeg'])
            i2 = ic2.file_uploader("รูปซอย", type=['jpg','png','jpeg'])
            i3 = ic3.file_uploader("รูปอื่นๆ", type=['jpg','png','jpeg'])
            
            p_note = st.text_area("🗒️ หมายเหตุสำหรับการตามงานย้อนหลัง:")
            
            if st.form_submit_button("🚀 บันทึกข้อมูลลงฐานข้อมูล", use_container_width=True):
                # เช็คสถานะความสมบูรณ์
                status = "Complete" if (p_name and i1) else "Incomplete"
                path = f"{gate}>{zone}>{main}>{m_side}>{sub}>{det}"
                
                sh = get_sheets()
                sh.worksheet("Sheet1").append_row([
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                    path, lat, lon, p_name,
                    i1.name if i1 else "", i2.name if i2 else "", i3.name if i3 else "",
                    p_note, status
                ])
                st.balloons()
                st.success(f"บันทึกสำเร็จ! สถานะงาน: {status}")
                st.rerun()

# --- TAB 2: แผนที่อาณาเขต (แยกสีเขียว/แดง) ---
with tab2:
    st.header("🗺️ แผนที่พิกัดอาณาเขต")
    if not log_df.empty:
        # เตรียมพิกัด (แปลงเป็นตัวเลข)
        log_df['lat'] = pd.to_numeric(log_df['lat'], errors='coerce')
        log_df['lon'] = pd.to_numeric(log_df['lon'], errors='coerce')
        df_map = log_df.dropna(subset=['lat', 'lon'])

        if not df_map.empty:
            # กำหนดสีตามสถานะ
            df_map['color'] = df_map['status'].apply(lambda x: [0, 200, 0, 160] if x == "Complete" else [255, 0, 0, 160])
            
            st.pydeck_chart(pdk.Deck(
                initial_view_state=pdk.ViewState(latitude=df_map['lat'].mean(), longitude=df_map['lon'].mean(), zoom=14, pitch=45),
                layers=[pdk.Layer("ScatterplotLayer", df_map, get_position='[lon, lat]', get_color='color', get_radius=15, pickable=True)],
                tooltip={"text": "สถานที่: {place_name}\nสถานะ: {status}\nข้อมูล: {location_path}"}
            ))
            st.write(f"📊 พิกัดทั้งหมด {len(df_map)} จุด")
            st.markdown("🟢 **สมบูรณ์** | 🔴 **ไม่สมบูรณ์ (รอตามงาน)**")
    else:
        st.info("ยังไม่มีข้อมูลพิกัด")

# --- TAB 3: การค้นหา (Global Search) ---
with tab3:
    st.header("🔍 ค้นหาข้อมูลพิกัด")
    q = st.text_input("ค้นหาจากชื่อสถานที่, ซอย หรือหมายเหตุ:")
    if q:
        mask = log_df.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)
        res = log_df[mask]
        if not res.empty:
            st.dataframe(res[["timestamp", "place_name", "location_path", "status", "note"]], use_container_width=True)
            # แผนที่เฉพาะจุดที่เจอ
            res['lat'] = pd.to_numeric(res['lat'], errors='coerce')
            res['lon'] = pd.to_numeric(res['lon'], errors='coerce')
            st.map(res.dropna(subset=['lat', 'lon']))
        else:
            st.error("ไม่พบข้อมูล")

# --- TAB 4: ADMIN MANAGE (Tree Structure + Hidden PIN) ---
with tab4:
    if not st.session_state.admin_auth:
        st.subheader("🔒 ยืนยันสิทธิ์แอดมิน")
        pin = st.text_input("กรอกรหัส PIN:", type="password")
        if pin == "9999":
            st.session_state.admin_auth = True
            st.rerun()
    else:
        c_h1, c_h2 = st.columns([8, 2])
        c_h1.header("⚙️ จัดการโครงสร้างข้อมูล 6 ระดับ")
        if c_h2.button("🔒 Logout"):
            st.session_state.admin_auth = False; st.rerun()

        ca, cb = st.columns(2)
        g_f = ca.text_input("ระบุชื่อประตู:", value="ประตู 1")
        z_f = cb.text_input("ระบุฝั่งถนน/โซน:", value="โซน A")

        st.divider()
        # Tree Logic
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
                            sn['dets'][di] = st.text_input(f"      ↳ ฝั่งของซอยย่อย {di+1}", value=dv, key=f"d_{mi}_{msi}_{si}_{di}")
                        st.button(f"➕ เพิ่มฝั่งซอยย่อย", on_click=add_d, args=(mi, msi, si), key=f"bd_{mi}_{msi}_{si}")
                    st.button(f"➕ เพิ่มซอยย่อย", on_click=add_s, args=(mi, msi), key=f"bs_{mi}_{msi}")
                st.button(f"➕ เพิ่มฝั่งซอยหลัก", on_click=add_ms, args=(mi,), key=f"bms_{mi}")
        
        st.button("➕ เพิ่มซอยหลักใหม่", on_click=add_m)

        if st.button("💾 บันทึกโครงสร้างทั้งหมดลง Mapping", type="primary", use_container_width=True):
            rows = []
            for m in st.session_state.tree_data:
                for ms in m['sides']:
                    for s in ms['subs']:
                        for d in s['dets']:
                            rows.append([g_f, z_f, m['main'], ms['side_name'], s['sub_name'], d])
            sh = get_sheets()
            sh.worksheet("Mapping").append_rows(rows)
            st.success("บันทึกสำเร็จ!")
            st.cache_data.clear(); st.rerun()
