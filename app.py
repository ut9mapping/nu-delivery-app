import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. การตั้งค่าหน้าจอและการเชื่อมต่อ ---
st.set_page_config(page_title="NU Delivery: Hierarchical Admin", page_icon="🛵", layout="wide")

def get_sheets():
    # เชื่อมต่อ Google Sheets ผ่าน st.secrets
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])

@st.cache_data(ttl=5)
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

# --- 2. จัดการสถานะระบบ (Session State) ---
# ตรวจสอบการ Login
if 'admin_auth' not in st.session_state:
    st.session_state.admin_auth = False

# โครงสร้างข้อมูลแบบต้นไม้สำหรับการเพิ่มข้อมูล (Tree Structure)
# รูปแบบ: [{'main': 'ชื่อซอย', 'subs': [{'name': 'ซอยย่อย', 'dets': ['จุดรายละเอียด']}]}]
if 'tree_data' not in st.session_state:
    st.session_state.tree_data = [{'main': '', 'subs': [{'name': '-', 'dets': ['-']}]}]

# --- 3. UI หน้าหลัก ---
st.title("🛵 ระบบจัดการพิกัด (Hierarchical Subset Mode)")
mapping_df = load_mapping_df()

tab1, tab2, tab3 = st.tabs(["📌 บันทึกงานส่งของ", "🔍 ค้นหาพิกัด", "⚙️ Admin Manage"])

# --- TAB 1: บันทึกงาน (5 ระดับ) ---
with tab1:
    location = streamlit_geolocation()
    if location.get('latitude'):
        lat, lon = location['latitude'], location['longitude']
        st.success(f"📍 GPS พร้อมบันทึก: {lat:.6f}, {lon:.6f}")
        
        # กรองข้อมูล 5 ระดับจาก Mapping
        def filter_options(df, filters, col_idx):
            tmp = df.copy()
            for k, v in filters.items():
                if v and v != "-- เลือก --": tmp = tmp[tmp[k] == v]
            return sorted([str(x) for x in tmp.iloc[:, col_idx].unique() if x and x != "-"])

        gate = st.selectbox("1. ประตู:", ["-- เลือก --"] + sorted(mapping_df['ประตู'].unique().tolist()))
        if gate != "-- เลือก --":
            c1, c2 = st.columns(2)
            zone = c1.selectbox("2. ฝั่งของถนน:", ["-- เลือก --"] + filter_options(mapping_df, {"ประตู": gate}, 1))
            main_soi = c2.selectbox("3. ซอยหลัก:", ["-- เลือก --"] + filter_options(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone}, 2))
            
            c3, c4 = st.columns(2)
            sub_soi = c3.selectbox("4. ซอยย่อย/ทางเชื่อม:", ["-- เลือก --"] + filter_options(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main_soi}, 3))
            detail = c4.selectbox("5. ฝั่ง/จุดรายละเอียด (สุดท้าย):", ["-- เลือก --"] + filter_options(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main_soi, "ซอยย่อย/ทางเชื่อม": sub_soi}, 4))
            
            extra = st.text_input("✍️ หมายเหตุ (เลขห้อง/ชื่อหอ):")
            if st.button("🚀 บันทึกพิกัดตอนนี้", type="primary"):
                sh = get_sheets()
                sh.worksheet("Sheet1").append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), f"{gate}|{zone}|{main_soi}|{sub_soi}|{detail}|{extra}", lat, lon, "Maps"])
                st.balloons(); st.success("บันทึกข้อมูลเรียบร้อย!")

# --- TAB 2: ค้นหาประวัติ ---
with tab2:
    q = st.text_input("🔍 ค้นหาชื่อสถานที่/ซอย:")
    if st.button("ค้นหา"):
        sh = get_sheets(); hist = pd.DataFrame(sh.worksheet("Sheet1").get_all_records())
        res = hist[hist['บันทึก'].str.contains(q, case=False, na=False)]
        if not res.empty:
            st.info(f"ข้อมูลล่าสุด: {res.iloc[-1]['บันทึก']}")
        else: st.error("ไม่พบข้อมูล")

# --- TAB 3: ADMIN MANAGE (ระบบบวกเพิ่มแบบ Subset) ---
with tab3:
    # 1. ระบบ Login (ซ่อนช่อง PIN ทันทีที่ผ่าน)
    if not st.session_state.admin_auth:
        st.subheader("🔒 ยืนยันสิทธิ์ Admin")
        pin = st.text_input("กรอกรหัสผ่าน (9999):", type="password")
        if pin == "9999":
            st.session_state.admin_auth = True
            st.rerun()
    
    else:
        # ส่วนหัว Admin
        c_h1, c_h2 = st.columns([8, 2])
        c_h1.header("⚙️ จัดการโครงสร้างข้อมูล (Hierarchy Mode)")
        if c_h2.button("🔒 Logout"):
            st.session_state.admin_auth = False
            st.rerun()

        # ส่วนที่ 1: เลือก ประตู และ ฝั่งถนน
        c1, c2 = st.columns(2)
        with c1:
            gates = sorted(mapping_df['ประตู'].unique().tolist())
            sel_g = st.selectbox("เลือกประตู:", ["-- เพิ่มใหม่ --"] + gates, key="adm_g")
            gate_f = st.text_input("ระบุชื่อประตูใหม่:", key="new_g") if sel_g == "-- เพิ่มใหม่ --" else sel_g
        with c2:
            zones = sorted(mapping_df[mapping_df['ประตู'] == gate_f]['ฝั่งถนน/โซน'].unique().tolist()) if gate_f else []
            sel_z = st.selectbox("เลือกฝั่งถนน/โซน:", ["-- เพิ่มใหม่ --"] + [z for z in zones if z and z != "-"], key="adm_z")
            zone_f = st.text_input("ระบุฝั่งถนนใหม่:", value="-", key="new_z") if sel_z == "-- เพิ่มใหม่ --" else sel_z

        st.divider()

        # --- ส่วนหัวใจ: ระบบบวกเพิ่มระดับ Subset ---
        st.subheader("➕ เพิ่มข้อมูลแบบลำดับชั้น (Subset)")
        
        # ฟังก์ชันจัดการ Tree Data
        def add_main_soi(): 
            st.session_state.tree_data.append({'main': '', 'subs': [{'name': '-', 'dets': ['-']}]})
        def add_sub_soi(m_idx): 
            st.session_state.tree_data[m_idx]['subs'].append({'name': '', 'dets': ['-']})
        def add_detail(m_idx, s_idx): 
            st.session_state.tree_data[m_idx]['subs'][s_idx]['dets'].append('')
        def delete_main(m_idx):
            if len(st.session_state.tree_data) > 1: st.session_state.tree_data.pop(m_idx)

        # วาดหน้าจอตามโครงสร้าง Subset
        for m_idx, main_node in enumerate(st.session_state.tree_data):
            with st.container(border=True):
                # ระดับ ซอยหลัก
                cm1, cm2 = st.columns([9, 1])
                main_node['main'] = cm1.text_input(f"📍 ซอยหลักที่ {m_idx+1}", value=main_node['main'], key=f"main_{m_idx}", placeholder="เช่น ซอย 1")
                if cm2.button("🗑️", key=f"del_m_{m_idx}"):
                    delete_main(m_idx); st.rerun()

                # ระดับ ซอยย่อย (Subset ของซอยหลัก)
                for s_idx, sub_node in enumerate(main_node['subs']):
                    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**↳ ซอยย่อย {s_idx+1}**")
                    cs1, cs2 = st.columns([1, 9])
                    sub_node['name'] = cs2.text_input(f"ชื่อซอยย่อย", value=sub_node['name'], key=f"sub_{m_idx}_{s_idx}")

                    # ระดับ ฝั่ง/จุดย่อย (Subset ของซอยย่อย)
                    for d_idx, det_val in enumerate(sub_node['dets']):
                        cd1, cd2 = st.columns([2, 8])
                        sub_node['dets'][d_idx] = cd2.text_input(f"ฝั่ง / รายละเอียดจุดสุดท้าย", value=det_val, key=f"det_{m_idx}_{s_idx}_{d_idx}", placeholder="เช่น ฝั่งซ้าย / หน้าหอพัก")

                    # ปุ่มบวกเพิ่ม "ฝั่ง" ในซอยย่อยนั้นๆ
                    _, c_add_d = st.columns([2, 8])
                    c_add_d.button(f"➕ เพิ่มฝั่งในซอยย่อยที่ {s_idx+1}", on_click=add_detail, args=(m_idx, s_idx), key=f"btn_d_{m_idx}_{s_idx}")
                
                # ปุ่มบวกเพิ่ม "ซอยย่อย" ในซอยหลักนั้นๆ
                st.button(f"➕ เพิ่มซอยย่อยใน {main_node['main'] if main_node['main'] else 'ซอยนี้'}", on_click=add_sub_soi, args=(m_idx,), key=f"btn_s_{m_idx}")

        st.button("➕ เพิ่มซอยหลักใหม่", on_click=add_main_soi, type="secondary")

        st.divider()

        # ปุ่มบันทึก (แปลง Tree เป็นแถวเพื่อบันทึกลง Sheets)
        if st.button("💾 บันทึกโครงสร้างทั้งหมด", type="primary", use_container_width=True):
            rows_to_save = []
            for m in st.session_state.tree_data:
                if not m['main']: continue
                for s in m['subs']:
                    for d in s['dets']:
                        rows_to_save.append([gate_f, zone_f, m['main'], s['name'], d])
            
            if rows_to_save:
                sh = get_sheets()
                sh.worksheet("Mapping").append_rows(rows_to_save)
                st.session_state.tree_data = [{'main': '', 'subs': [{'name': '-', 'dets': ['-']}]}]
                st.cache_data.clear()
                st.success(f"บันทึกสำเร็จ! เพิ่มข้อมูลทั้งหมด {len(rows_to_save)} รายการ")
                st.rerun()
            else:
                st.error("กรุณากรอกข้อมูลในช่องซอยหลักอย่างน้อย 1 ช่อง")

        # ส่วนจัดการลบข้อมูลเดิม
        with st.expander("🗑️ ลบข้อมูลเดิม"):
            st.dataframe(mapping_df, use_container_width=True)
            idx_del = st.number_input("ลำดับ Index ที่จะลบ:", min_value=0, max_value=len(mapping_df)-1, step=1)
            if st.button("🔥 ยืนยันการลบถาวร"):
                sh = get_sheets(); sh.worksheet("Mapping").delete_rows(int(idx_del) + 2)
                st.cache_data.clear(); st.success("ลบข้อมูลสำเร็จ!"); st.rerun()
