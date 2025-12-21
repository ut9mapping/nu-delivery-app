import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. ตั้งค่าพื้นฐานและการเชื่อมต่อ (เพิ่มการดัก Error) ---
st.set_page_config(page_title="NU Delivery: Pro Territory", page_icon="📍", layout="wide")

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])
    except Exception as e:
        st.error(f"การเชื่อมต่อฐานข้อมูลผิดพลาด: {e}")
        return None

@st.cache_data(ttl=2)
def load_all_data():
    sh = get_sheets()
    if not sh:
        return pd.DataFrame(), pd.DataFrame()
    
    # ดึงข้อมูล Mapping
    map_sheet = sh.worksheet("Mapping").get_all_records()
    map_df = pd.DataFrame(map_sheet) if map_sheet else pd.DataFrame(columns=["ประตู", "ฝั่งถนน/โซน", "ซอยหลัก", "ฝั่งซอยหลัก", "ซอยย่อย/ทางเชื่อม", "ฝั่งของซอยย่อย"])
    
    # ดึงข้อมูลการบันทึกงาน
    log_sheet = sh.worksheet("Sheet1").get_all_records()
    log_df = pd.DataFrame(log_sheet) if log_sheet else pd.DataFrame(columns=["timestamp", "location_path", "lat", "lon", "place_name", "img1", "img2", "img3", "note", "status"])
    
    return map_df, log_df

# --- 2. สถานะระบบ ---
if 'admin_auth' not in st.session_state:
    st.session_state.admin_auth = False
if 'tree_data' not in st.session_state:
    st.session_state.tree_data = [{'main': '', 'sides': [{'side_name': '-', 'subs': [{'sub_name': '-', 'dets': ['-']}]}]}]

mapping_df, log_df = load_all_data()

# --- 3. UI ส่วนหลัก ---
st.title("📍 ระบบพิกัดอาณาเขต NU Delivery")

tab1, tab2, tab3, tab4 = st.tabs(["📌 บันทึกงาน", "🗺️ แผนที่อาณาเขต", "🔍 ค้นหาประวัติ", "⚙️ Admin Manage"])

# --- TAB 1: บันทึกงาน (แก้ไขเรื่อง Form และ Submit) ---
with tab1:
    location = streamlit_geolocation()
    if location.get('latitude'):
        lat, lon = location['latitude'], location['longitude']
        st.success(f"📍 GPS Ready: {lat:.6f}, {lon:.6f}")
        
        # --- ส่วนการกรอง (อยู่นอก Form เพื่อให้ Real-time) ---
        st.subheader("🔍 เลือกตำแหน่ง")
        
        def get_opt(df, filters, col_name):
            if df.empty or col_name not in df.columns: return []
            tmp = df.copy()
            for k, v in filters.items():
                if v and v != "-- เลือก --": tmp = tmp[tmp[k] == v]
            return sorted([str(x) for x in tmp[col_name].unique() if x and x != "-"])

        # ลำดับการเลือก
        g_list = sorted(mapping_df['ประตู'].unique().tolist()) if not mapping_df.empty else []
        gate = st.selectbox("1. ประตู:", ["-- เลือก --"] + g_list)
        
        c1, c2 = st.columns(2)
        zone = c1.selectbox("2. ฝั่งถนน/โซน:", ["-- เลือก --"] + get_opt(mapping_df, {"ประตู": gate}, "ฝั่งถนน/โซน"))
        main = c2.selectbox("3. ซอยหลัก:", ["-- เลือก --"] + get_opt(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone}, "ซอยหลัก"))
        
        c3, c4 = st.columns(2)
        m_side = c3.selectbox("4. ฝั่งซอยหลัก:", ["-- เลือก --"] + get_opt(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main}, "ฝั่งซอยหลัก"))
        sub = c4.selectbox("5. ซอยย่อย/ทางเชื่อม:", ["-- เลือก --"] + get_opt(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main, "ฝั่งซอยหลัก": m_side}, "ซอยย่อย/ทางเชื่อม"))
        
        det = st.selectbox("6. ฝั่งของซอยย่อย:", ["-- เลือก --"] + get_opt(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main, "ฝั่งซอยหลัก": m_side, "ซอยย่อย/ทางเชื่อม": sub}, "ฝั่งของซอยย่อย"))

        # --- ส่วนการกรอกข้อมูล (อยู่ใน Form) ---
        with st.form("detail_form"):
            st.subheader("🏠 ข้อมูลสถานที่")
            place_name = st.text_input("ชื่อสถานที่ / บ้านเลขที่ (ถ้ามี):")
            
            st.write("📸 รูปภาพสถานที่ (3 รูป):")
            ic1, ic2, ic3 = st.columns(3)
            img1 = ic1.file_uploader("รูป 1", type=['jpg','png'])
            img2 = ic2.file_uploader("รูป 2", type=['jpg','png'])
            img3 = ic3.file_uploader("รูป 3", type=['jpg','png'])
            
            note = st.text_area("หมายเหตุสำหรับตามงาน (เช่น ข้อมูลไม่ครบ):")
            
            # ปุ่มบันทึกใน Form
            submitted = st.form_submit_button("🚀 บันทึกข้อมูลลงระบบ", use_container_width=True)
            
            if submitted:
                if gate == "-- เลือก --":
                    st.error("กรุณาเลือกตำแหน่งประตูเป็นอย่างน้อย")
                else:
                    # เช็คความสมบูรณ์
                    status = "Complete" if (place_name and img1) else "Incomplete"
                    
                    sh = get_sheets()
                    sh.worksheet("Sheet1").append_row([
                        datetime.now().strftime("%Y-%m-%d %H:%M"),
                        f"{gate}|{zone}|{main}|{m_side}|{sub}|{det}",
                        lat, lon, place_name, 
                        img1.name if img1 else "", img2.name if img2 else "", img3.name if img3 else "",
                        note, status
                    ])
                    st.success(f"บันทึกสำเร็จ! สถานะข้อมูล: {status}")
                    st.balloons()

# --- TAB 2: แผนที่อาณาเขต (Territory Map) ---
with tab2:
    st.header("🗺️ แผนที่จำลองอาณาเขตที่ครอบคลุม")
    if not log_df.empty:
        # เตรียมข้อมูลสำหรับ Map
        log_df['lat'] = pd.to_numeric(log_df['lat'], errors='coerce')
        log_df['lon'] = pd.to_numeric(log_df['lon'], errors='coerce')
        log_df = log_df.dropna(subset=['lat', 'lon'])

        # แยกสี: เขียว=สมบูรณ์, แดง=ไม่สมบูรณ์
        log_df['color'] = log_df['status'].apply(lambda x: [0, 200, 0, 180] if x == "Complete" else [230, 0, 0, 180])
        
        view_state = pdk.ViewState(latitude=log_df['lat'].mean(), longitude=log_df['lon'].mean(), zoom=14, pitch=30)
        
        # Layer จุดพิกัด
        layer_points = pdk.Layer(
            "ScatterplotLayer",
            log_df,
            get_position='[lon, lat]',
            get_color='color',
            get_radius=10,
            pickable=True
        )

        st.pydeck_chart(pdk.Deck(
            layers=[layer_points],
            initial_view_state=view_state,
            tooltip={"text": "สถานที่: {place_name}\nสถานะ: {status}\nเส้นทาง: {location_path}"}
        ))
        st.markdown("🟢 **สมบูรณ์** | 🔴 **ไม่สมบูรณ์ (รอตามงาน)**")
    else:
        st.info("ยังไม่มีพิกัดถูกบันทึกในระบบ")

# --- TAB 4: Admin Manage (ซ่อนรหัส PIN และระบบ Subset) ---
with tab4:
    if not st.session_state.admin_auth:
        st.subheader("🔒 แอดมินล็อกอิน")
        pin = st.text_input("ใส่รหัส PIN:", type="password")
        if pin == "9999":
            st.session_state.admin_auth = True
            st.rerun()
    else:
        c_h1, c_h2 = st.columns([8, 2])
        c_h1.header("⚙️ ตั้งค่าโครงสร้าง Subset (6 ระดับ)")
        if c_h2.button("🔒 ออกจากระบบ"):
            st.session_state.admin_auth = False; st.rerun()

        # ส่วนหัวใหญ่
        c_m1, c_m2 = st.columns(2)
        gate_f = c_m1.text_input("ประตูหลัก:", value="ประตู 1")
        zone_f = c_m2.text_input("ฝั่งถนน/โซน:", value="โซน A")

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
            st.success("บันทึกโครงสร้างเรียบร้อย!")
            st.cache_data.clear(); st.rerun()
