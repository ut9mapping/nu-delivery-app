import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. การตั้งค่าหน้าจอและการเชื่อมต่อ ---
st.set_page_config(page_title="NU Delivery: 6-Level Admin", page_icon="🛵", layout="wide")

def get_sheets():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])

@st.cache_data(ttl=5)
def load_mapping_df():
    cols = ["ประตู", "ฝั่งถนน/โซน", "ซอยหลัก", "ฝั่งซอยหลัก", "ซอยย่อย/ทางเชื่อม", "ฝั่ง/จุดรายละเอียด"]
    try:
        sh = get_sheets()
        data = sh.worksheet("Mapping").get_all_records()
        if not data: return pd.DataFrame(columns=cols)
        return pd.DataFrame(data).map(lambda x: str(x).strip())
    except:
        return pd.DataFrame(columns=cols)

# --- 2. จัดการสถานะระบบ (Session State) ---
if 'admin_auth' not in st.session_state:
    st.session_state.admin_auth = False

# โครงสร้าง Tree ใหม่: Main > MainSide > SubSoi > Points
if 'tree_data' not in st.session_state:
    st.session_state.tree_data = [{
        'main': '', 
        'sides': [{
            'side_name': '-', 
            'subs': [{
                'sub_name': '-', 
                'dets': ['-']
            }]
        }]
    }]

# --- 3. UI ส่วนหลัก ---
st.title("🛵 ระบบจัดการพิกัด (6-Level Hierarchical)")
mapping_df = load_mapping_df()

tab1, tab2, tab3 = st.tabs(["📌 บันทึกงาน", "🔍 ค้นหา", "⚙️ Admin Manage"])

# --- TAB 1: บันทึกงาน (6 ระดับ) ---
with tab1:
    location = streamlit_geolocation()
    if location.get('latitude'):
        lat, lon = location['latitude'], location['longitude']
        st.success(f"📍 GPS Ready: {lat:.6f}, {lon:.6f}")
        
        def filter_step(df, filters, col_idx):
            tmp = df.copy()
            for k, v in filters.items():
                if v and v != "-- เลือก --": tmp = tmp[tmp[k] == v]
            return sorted([str(x) for x in tmp.iloc[:, col_idx].unique() if x and x != "-"])

        gate = st.selectbox("1. ประตู:", ["-- เลือก --"] + sorted(mapping_df['ประตู'].unique().tolist()))
        if gate != "-- เลือก --":
            c1, c2 = st.columns(2)
            zone = c1.selectbox("2. ฝั่งถนน/โซน:", ["-- เลือก --"] + filter_step(mapping_df, {"ประตู": gate}, 1))
            main = c2.selectbox("3. ซอยหลัก:", ["-- เลือก --"] + filter_step(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone}, 2))
            
            c3, c4 = st.columns(2)
            m_side = c3.selectbox("4. ฝั่งของซอยหลัก:", ["-- เลือก --"] + filter_step(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main}, 3))
            sub = c4.selectbox("5. ซอยย่อย/ทางเชื่อม:", ["-- เลือก --"] + filter_step(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main, "ฝั่งซอยหลัก": m_side}, 4))
            
            det = st.selectbox("6. จุดรายละเอียดสุดท้าย:", ["-- เลือก --"] + filter_step(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main, "ฝั่งซอยหลัก": m_side, "ซอยย่อย/ทางเชื่อม": sub}, 5))
            
            extra = st.text_input("✍️ หมายเหตุ (เลขห้อง/ชื่อหอ):")
            if st.button("🚀 บันทึกพิกัด", type="primary"):
                sh = get_sheets()
                sh.worksheet("Sheet1").append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), f"{gate}|{zone}|{main}|{m_side}|{sub}|{det}|{extra}", lat, lon])
                st.balloons(); st.success("บันทึกสำเร็จ!")

# --- TAB 3: ADMIN MANAGE (ระบบบวก Subset 6 ระดับ) ---
with tab3:
    if not st.session_state.admin_auth:
        st.subheader("🔒 ยืนยันสิทธิ์ Admin")
        pin = st.text_input("กรอก PIN (9999):", type="password")
        if pin == "9999":
            st.session_state.admin_auth = True
            st.rerun()
    else:
        c_h1, c_h2 = st.columns([8, 2])
        c_h1.header("⚙️ จัดการโครงสร้าง (ระดับ Subset)")
        if c_h2.button("🔒 Logout"):
            st.session_state.admin_auth = False; st.rerun()

        # ส่วนที่ 1: ประตู & ฝั่งถนน
        c1, c2 = st.columns(2)
        with c1:
            sel_g = st.selectbox("ประตู:", ["-- เพิ่มใหม่ --"] + sorted(mapping_df['ประตู'].unique().tolist()), key="adm_g")
            gate_f = st.text_input("ชื่อประตูใหม่:", key="new_g") if sel_g == "-- เพิ่มใหม่ --" else sel_g
        with c2:
            zones = sorted(mapping_df[mapping_df['ประตู'] == gate_f]['ฝั่งถนน/โซน'].unique().tolist()) if gate_f else []
            sel_z = st.selectbox("ฝั่งถนน:", ["-- เพิ่มใหม่ --"] + [z for z in zones if z and z != "-"], key="adm_z")
            zone_f = st.text_input("ชื่อฝั่งถนนใหม่:", value="-", key="new_z") if sel_z == "-- เพิ่มใหม่ --" else sel_z

        st.divider()
        st.subheader("🌳 โครงสร้างซอยหลักและฝั่งย่อย")

        # ฟังก์ชันควบคุมโครงสร้าง
        def add_m(): st.session_state.tree_data.append({'main': '', 'sides': [{'side_name': '-', 'subs': [{'sub_name': '-', 'dets': ['-']}]}]})
        def add_ms(m_i): st.session_state.tree_data[m_i]['sides'].append({'side_name': '', 'subs': [{'sub_name': '-', 'dets': ['-']}]})
        def add_s(m_i, ms_i): st.session_state.tree_data[m_i]['sides'][ms_i]['subs'].append({'sub_name': '', 'dets': ['-']})
        def add_d(m_i, ms_i, s_i): st.session_state.tree_data[m_i]['sides'][ms_i]['subs'][s_i]['dets'].append('')
        def del_m(m_i): st.session_state.tree_data.pop(m_i)

        for m_i, m_n in enumerate(st.session_state.tree_data):
            with st.container(border=True):
                # ระดับ 3: ซอยหลัก
                cm1, cm2 = st.columns([9, 1])
                m_n['main'] = cm1.text_input(f"📍 ซอยหลัก {m_i+1}", value=m_n['main'], key=f"m_{m_i}")
                if cm2.button("🗑️", key=f"dm_{m_i}"): del_m(m_i); st.rerun()

                # ระดับ 4: ฝั่งของซอยหลัก (Subset ของซอยหลัก)
                for ms_i, ms_n in enumerate(m_n['sides']):
                    st.markdown(f"&nbsp;&nbsp;**↳ ฝั่งของซอยหลัก {ms_i+1}**")
                    ms_n['side_name'] = st.text_input(f"ระบุฝั่ง (เช่น ซ้าย/ขวา)", value=ms_n['side_name'], key=f"ms_{m_i}_{ms_i}")

                    # ระดับ 5: ซอยย่อย (Subset ของฝั่งซอยหลัก)
                    for s_i, s_n in enumerate(ms_n['subs']):
                        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**↳ ซอยย่อย {s_i+1}**")
                        s_n['sub_name'] = st.text_input(f"ชื่อซอยย่อย", value=s_n['sub_name'], key=f"s_{m_i}_{ms_i}_{s_i}")

                        # ระดับ 6: จุดสุดท้าย (Subset ของซอยย่อย)
                        for d_i, d_v in enumerate(s_n['dets']):
                            s_n['dets'][d_i] = st.text_input(f"จุดรายละเอียดสุดท้าย {d_i+1}", value=d_v, key=f"d_{m_i}_{ms_i}_{s_i}_{d_i}")
                        
                        st.button(f"➕ เพิ่มจุดในซอยย่อย {s_i+1}", on_click=add_d, args=(m_i, ms_i, s_i), key=f"bd_{m_i}_{ms_i}_{s_i}")

                    st.button(f"➕ เพิ่มซอยย่อยในฝั่ง {ms_n['side_name']}", on_click=add_s, args=(m_i, ms_i), key=f"bs_{m_i}_{ms_i}")

                st.button(f"➕ เพิ่มฝั่งใหม่ใน {m_n['main']}", on_click=add_ms, args=(m_i,), key=f"bms_{m_i}")

        st.button("➕ เพิ่มซอยหลักใหม่", on_click=add_m, type="secondary")

        if st.button("💾 บันทึกโครงสร้าง 6 ระดับทั้งหมด", type="primary", use_container_width=True):
            data_to_save = []
            for m in st.session_state.tree_data:
                if not m['main']: continue
                for ms in m['sides']:
                    for s in ms['subs']:
                        for d in s['dets']:
                            data_to_save.append([gate_f, zone_f, m['main'], ms['side_name'], s['sub_name'], d])
            
            if data_to_save:
                sh = get_sheets(); sh.worksheet("Mapping").append_rows(data_to_save)
                st.session_state.tree_data = [{'main': '', 'sides': [{'side_name': '-', 'subs': [{'sub_name': '-', 'dets': ['-']}]}]}]
                st.cache_data.clear(); st.success("บันทึกสำเร็จ!"); st.rerun()
