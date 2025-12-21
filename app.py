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
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])

@st.cache_data(ttl=2)
def load_all_data():
    sh = get_sheets()
    # ดึงข้อมูล Mapping
    map_data = pd.DataFrame(sh.worksheet("Mapping").get_all_records())
    # ดึงข้อมูลการบันทึกงาน (Sheet1)
    log_data = pd.DataFrame(sh.worksheet("Sheet1").get_all_records())
    return map_data, log_data

# --- 2. สถานะระบบ (Session State) ---
if 'admin_auth' not in st.session_state:
    st.session_state.admin_auth = False
if 'tree_data' not in st.session_state:
    st.session_state.tree_data = [{'main': '', 'sides': [{'side_name': '-', 'subs': [{'sub_name': '-', 'dets': ['-']}]}]}]

# --- 3. UI ส่วนหลัก ---
st.title("🛵 ระบบบริหารพิกัดและอาณาเขตขนส่ง")
mapping_df, log_df = load_all_data()

tab1, tab2, tab3, tab4 = st.tabs(["📌 บันทึกงานใหม่", "🗺️ แผนที่อาณาเขต", "🔍 ค้นหา/ประวัติ", "⚙️ Admin Manage"])

# --- TAB 1: บันทึกงาน (เพิ่มรูป + สถานะไม่ครบ) ---
with tab1:
    location = streamlit_geolocation()
    if location.get('latitude'):
        lat, lon = location['latitude'], location['longitude']
        st.success(f"📍 พิกัดปัจจุบัน: {lat}, {lon}")
        
        with st.form("work_log_form"):
            st.subheader("📝 รายละเอียดสถานที่")
            # กรอง 6 ระดับ
            def get_opt(df, filters, col_idx):
                tmp = df.copy()
                for k, v in filters.items():
                    if v and v != "-- เลือก --": tmp = tmp[tmp[k] == v]
                return sorted([str(x) for x in tmp.iloc[:, col_idx].unique() if x and x != "-"])

            gate = st.selectbox("1. ประตู:", ["-- เลือก --"] + sorted(mapping_df['ประตู'].unique().tolist()))
            c1, c2 = st.columns(2)
            zone = c1.selectbox("2. ฝั่งถนน/โซน:", ["-- เลือก --"] + get_opt(mapping_df, {"ประตู": gate}, 1))
            main = c2.selectbox("3. ซอยหลัก:", ["-- เลือก --"] + get_opt(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone}, 2))
            
            c3, c4 = st.columns(2)
            m_side = c3.selectbox("4. ฝั่งซอยหลัก:", ["-- เลือก --"] + get_opt(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main}, 3))
            sub = c4.selectbox("5. ซอยย่อย/ทางเชื่อม:", ["-- เลือก --"] + get_opt(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main, "ฝั่งซอยหลัก": m_side}, 4))
            
            det = st.selectbox("6. ฝั่งของซอยย่อย:", ["-- เลือก --"] + get_opt(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main, "ฝั่งซอยหลัก": m_side, "ซอยย่อย/ทางเชื่อม": sub}, 5))
            
            st.divider()
            place_name = st.text_input("🏠 ชื่อสถานที่ / บ้านเลขที่ (ถ้ามี):")
            
            # อัปโหลดรูป 3 รูป
            st.write("📸 รูปภาพสถานที่ (สูงสุด 3 รูป):")
            img_cols = st.columns(3)
            img1 = img_cols[0].file_uploader("รูปที่ 1", type=['jpg','png'], key="img1")
            img2 = img_cols[1].file_uploader("รูปที่ 2", type=['jpg','png'], key="img2")
            img3 = img_cols[2].file_uploader("รูปที่ 3", type=['jpg','png'], key="img3")
            
            note = st.text_area("🗒️ หมายเหตุสำหรับการตามงานย้อนหลัง:")
            
            submit = st.form_submit_button("🚀 บันทึกข้อมูล", use_container_width=True)
            
            if submit:
                # ตรวจสอบสถานะความสมบูรณ์
                status = "Complete"
                if not place_name or not img1:
                    status = "Incomplete"
                
                sh = get_sheets()
                row = [
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                    f"{gate}|{zone}|{main}|{m_side}|{sub}|{det}",
                    lat, lon, place_name, 
                    img1.name if img1 else "", img2.name if img2 else "", img3.name if img3 else "",
                    note, status
                ]
                sh.worksheet("Sheet1").append_row(row)
                st.balloons()
                st.success(f"บันทึกเรียบร้อย! สถานะ: {status}")

# --- TAB 2: แผนที่อาณาเขต (Territory Simulation) ---
with tab2:
    st.header("🗺️ แผนที่พิกัดอาณาเขตขนส่ง")
    if not log_df.empty:
        # แยกสีตามสถานะ: เขียว = Complete, แดง = Incomplete
        log_df['color'] = log_df['status'].apply(lambda x: [0, 255, 0, 160] if x == 'Complete' else [255, 0, 0, 160])
        
        view_state = pdk.ViewState(latitude=log_df['lat'].mean(), longitude=log_df['lon'].mean(), zoom=15, pitch=45)
        
        layer = pdk.Layer(
            "ScatterplotLayer",
            log_df,
            get_position='[lon, lat]',
            get_color='color',
            get_radius=5,
            pickable=True
        )
        
        st.pydeck_chart(pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            tooltip={"text": "สถานที่: {place_name}\nสถานะ: {status}\nข้อมูล: {บันทึก}"}
        ))
        
        st.write("🔴 สีแดง: ข้อมูลยังไม่ครบ | 🟢 สีเขียว: ข้อมูลสมบูรณ์")
    else:
        st.info("ยังไม่มีข้อมูลพิกัดในระบบ")

# --- TAB 4: ADMIN MANAGE (ปรับปรุงใหม่ตามสั่ง) ---
with tab4:
    if not st.session_state.admin_auth:
        st.subheader("🔒 กรุณากรอกรหัสแอดมิน")
        col_auth, _ = st.columns([3, 7])
        pin = col_auth.text_input("PIN:", type="password")
        if pin == "9999":
            st.session_state.admin_auth = True
            st.rerun()
    else:
        c_h1, c_h2 = st.columns([8, 2])
        c_h1.header("⚙️ จัดการโครงสร้างแบบลำดับชั้น")
        if c_h2.button("🔒 Logout"):
            st.session_state.admin_auth = False; st.rerun()

        # ส่วนเลือกหัวใหญ่
        c_main1, c_main2 = st.columns(2)
        gate_f = c_main1.text_input("ระบุชื่อประตู:", value="ประตู 1")
        zone_f = c_main2.text_input("ระบุฝั่งถนน/โซน:", value="โซน A")

        st.divider()

        # ฟังก์ชัน Tree Logic
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
                            # เปลี่ยนชื่อตามคำขอ: ฝั่งของซอยย่อย
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
            st.cache_data.clear(); st.rerun()
