import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. การตั้งค่าหน้าจอและ Google Sheets ---
st.set_page_config(page_title="NU Delivery Pro (Full Version)", page_icon="🛵", layout="wide")

def get_sheets():
    # ดึงค่าจาก st.secrets
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])

@st.cache_data(ttl=10) # รีเฟรชข้อมูลทุก 10 วินาที
def load_mapping_df():
    try:
        sh = get_sheets()
        data = sh.worksheet("Mapping").get_all_records()
        if not data:
            return pd.DataFrame(columns=["ประตู", "ฝั่งถนน/โซน", "ซอยหลัก", "ซอยย่อย/ทางเชื่อม", "ฝั่ง/จุดรายละเอียด"])
        df = pd.DataFrame(data)
        return df.map(lambda x: str(x).strip())
    except:
        return pd.DataFrame(columns=["ประตู", "ฝั่งถนน/โซน", "ซอยหลัก", "ซอยย่อย/ทางเชื่อม", "ฝั่ง/จุดรายละเอียด"])

def display_precision_map(lat, lon, zoom=18):
    layer = pdk.Layer("ScatterplotLayer", data=pd.DataFrame({'lat': [lat], 'lon': [lon]}),
        get_position='[lon, lat]', get_color='[255, 75, 75, 230]', get_radius=3)
    view = pdk.ViewState(latitude=lat, longitude=lon, zoom=zoom)
    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view, map_style='carto-positron'))

# --- 2. จัดการ Session State (ล็อกอิน และ แถวการกรอก) ---
if 'admin_auth' not in st.session_state:
    st.session_state.admin_auth = False
if 'rows' not in st.session_state:
    st.session_state.rows = [{"main": "", "sub": "-", "det": "-"}]

# --- 3. UI หน้าหลัก ---
st.title("🛵 ระบบพิกัดขนส่ง มน. (Full Edition)")
mapping_df = load_mapping_df()

tab1, tab2, tab3 = st.tabs(["📌 บันทึกงานส่งของ", "🔍 ค้นหาพิกัด", "⚙️ Admin Manage"])

# --- TAB 1: บันทึกงาน (5 ลำดับชั้น) ---
with tab1:
    location = streamlit_geolocation()
    if location.get('latitude'):
        lat, lon = location['latitude'], location['longitude']
        st.success(f"📍 GPS พร้อมบันทึก: {lat:.6f}, {lon:.6f}")
        display_precision_map(lat, lon, zoom=17)
        
        # ระบบกรองตัวเลือก
        def filter_opts(df, filters):
            tmp = df.copy()
            for k, v in filters.items():
                if v and v != "-- เลือก --": tmp = tmp[tmp[k] == v]
            idx = len(filters)
            return sorted([str(x) for x in tmp.iloc[:, idx].unique() if x and x != "-"]) if idx < 5 else []

        gate = st.selectbox("1. เลือกประตู:", ["-- เลือก --"] + sorted(mapping_df['ประตู'].unique().tolist()))
        if gate != "-- เลือก --":
            c1, c2 = st.columns(2)
            zone = c1.selectbox("2. ฝั่งของถนน:", ["-- เลือก --"] + filter_opts(mapping_df, {"ประตู": gate}))
            main_soi = c2.selectbox("3. ซอยหลัก:", ["-- เลือก --"] + filter_opts(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone}))
            
            c3, c4 = st.columns(2)
            sub_soi = c3.selectbox("4. ซอยย่อย/ทางเชื่อม:", ["-- เลือก --"] + filter_opts(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main_soi}))
            detail = c4.selectbox("5. ฝั่งของซอยย่อย (สุดท้าย):", ["-- เลือก --"] + filter_opts(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main_soi, "ซอยย่อย/ทางเชื่อม": sub_soi}))
            
            extra = st.text_input("✍️ หมายเหตุ (เลขห้อง/ชื่อหอ):")
            if st.button("🚀 บันทึกข้อมูลพิกัด", type="primary"):
                sh = get_sheets()
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                maps_url = f"https://www.google.com/maps?q={lat},{lon}"
                sh.worksheet("Sheet1").append_row([now, f"{gate}|{zone}|{main_soi}|{sub_soi}|{detail}|{extra}", lat, lon, maps_url])
                st.balloons(); st.success("บันทึกลงฐานข้อมูลสำเร็จ!")

# --- TAB 2: ค้นหาประวัติ ---
with tab2:
    query = st.text_input("🔍 ค้นหาชื่อสถานที่/ซอย ที่เคยบันทึก:")
    if st.button("ค้นหา"):
        sh = get_sheets()
        hist = pd.DataFrame(sh.worksheet("Sheet1").get_all_records())
        res = hist[hist['บันทึก'].str.contains(query, case=False, na=False)]
        if not res.empty:
            last = res.iloc[-1]
            st.info(f"ข้อมูลล่าสุด: {last['บันทึก']}")
            display_precision_map(float(last['ละติจูด']), float(last['ลองจิจูด']), zoom=19)
        else: st.error("ไม่พบประวัติพิกัดนี้")

# --- TAB 3: ADMIN MANAGE (ฉบับสมบูรณ์) ---
with tab3:
    if not st.session_state.admin_auth:
        st.subheader("🔒 กรุณายืนยันสิทธิ์ Admin")
        pin = st.text_input("กรอกรหัส PIN:", type="password")
        if pin == "9999":
            st.session_state.admin_auth = True
            st.rerun()
    else:
        # ส่วนหัว Admin เมื่อล็อกอินแล้ว
        c_head1, c_head2 = st.columns([8, 2])
        c_head1.header("⚙️ ระบบจัดการโครงสร้างข้อมูล")
        if c_head2.button("🔒 Logout"):
            st.session_state.admin_auth = False
            st.rerun()

        # ส่วนที่ 1: ประตู & ฝั่งถนน
        c1, c2 = st.columns(2)
        with c1:
            sel_g = st.selectbox("เลือกประตู:", ["-- เพิ่มใหม่ --"] + sorted(mapping_df['ประตู'].unique().tolist()))
            gate_f = st.text_input("ชื่อประตูใหม่:") if sel_g == "-- เพิ่มใหม่ --" else sel_g
        with c2:
            zones = sorted(mapping_df[mapping_df['ประตู'] == gate_f]['ฝั่งถนน/โซน'].unique().tolist()) if gate_f else []
            sel_z = st.selectbox("เลือกฝั่งถนน:", ["-- เพิ่มใหม่ --"] + [z for z in zones if z and z != "-"])
            zone_f = st.text_input("ชื่อฝั่งถนนใหม่:", value="-") if sel_z == "-- เพิ่มใหม่ --" else sel_z

        st.divider()
        st.subheader("📝 เพิ่มรายการซอย/ฝั่ง (กดบวกเพิ่มได้อิสระ)")

        # รายชื่อซอยหลักและย่อยที่มีอยู่แล้วในโซนนี้
        ext_mains = sorted(mapping_df[(mapping_df['ประตู'] == gate_f) & (mapping_df['ฝั่งถนน/โซน'] == zone_f)]['ซอยหลัก'].unique().tolist())

        def add_r(): st.session_state.rows.append({"main": "", "sub": "-", "det": "-"})
        def del_r(i): 
            if len(st.session_state.rows) > 1: st.session_state.rows.pop(i)

        for i, row in enumerate(st.session_state.rows):
            with st.container():
                cols = st.columns([4, 4, 4, 1])
                # ซอยหลัก
                with cols[0]:
                    m_opts = ["-- พิมพ์ใหม่ --"] + [x for x in ext_mains if x and x != "-"]
                    sel_m = st.selectbox(f"ซอยหลัก {i+1}", m_opts, key=f"sel_m_{i}")
                    st.session_state.rows[i]['main'] = st.text_input(f"ระบุใหม่ {i+1}", key=f"txt_m_{i}") if sel_m == "-- พิมพ์ใหม่ --" else sel_m
                # ซอยย่อย
                with cols[1]:
                    curr_m = st.session_state.rows[i]['main']
                    ext_subs = sorted(mapping_df[(mapping_df['ประตู'] == gate_f) & (mapping_df['ซอยหลัก'] == curr_m)]['ซอยย่อย/ทางเชื่อม'].unique().tolist()) if curr_m else []
                    s_opts = ["-- พิมพ์ใหม่ --"] + [x for x in ext_subs if x and x != "-"]
                    sel_s = st.selectbox(f"ซอยย่อย {i+1}", s_opts, key=f"sel_s_{i}")
                    st.session_state.rows[i]['sub'] = st.text_input(f"ระบุใหม่ {i+1}", value="-", key=f"txt_s_{i}") if sel_s == "-- พิมพ์ใหม่ --" else sel_s
                # ฝั่งรายละเอียด
                with cols[2]:
                    st.session_state.rows[i]['det'] = st.text_input(f"ฝั่งสุดท้าย {i+1}", value=row['det'], key=f"txt_d_{i}")
                with cols[3]:
                    st.write("##")
                    if st.button("🗑️", key=f"del_r_{i}"): del_r(i); st.rerun()

        st.button("➕ เพิ่มรายการถัดไป", on_click=add_r)

        if st.button("💾 บันทึกข้อมูลทั้งหมดลง Google Sheets", type="primary"):
            final_data = [[gate_f, zone_f, r['main'], r['sub'], r['det']] for r in st.session_state.rows if r['main']]
            if final_data:
                sh = get_sheets(); sh.worksheet("Mapping").append_rows(final_data)
                st.session_state.rows = [{"main": "", "sub": "-", "det": "-"}]
                st.cache_data.clear(); st.success("บันทึกสำเร็จ!"); st.rerun()

        st.divider()
        st.subheader("🗑️ รายการทั้งหมดในระบบ (ลบข้อมูล)")
        st.dataframe(mapping_df, use_container_width=True)
        del_idx = st.number_input("ลำดับ Index ที่จะลบ:", min_value=0, max_value=len(mapping_df)-1, step=1)
        if st.button("❌ ลบรายการที่เลือก"):
            st.session_state.confirm_del_idx = del_idx

        if 'confirm_del_idx' in st.session_state:
            st.warning(f"ยืนยันการลบ Index {st.session_state.confirm_del_idx}?")
            conf_pin = st.text_input("ใส่ PIN ยืนยันเพื่อลบถาวร:", type="password", key="conf_pin")
            if st.button("🔥 ยืนยันการลบ"):
                if conf_pin == "9999":
                    sh = get_sheets(); sh.worksheet("Mapping").delete_rows(int(st.session_state.confirm_del_idx) + 2)
                    del st.session_state.confirm_del_idx
                    st.cache_data.clear(); st.success("ลบสำเร็จ!"); st.rerun()
                else: st.error("รหัสผิด")
