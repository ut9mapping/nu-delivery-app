import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. ตั้งค่าพื้นฐานและการเชื่อมต่อ ---
st.set_page_config(page_title="NU Delivery: Pro Admin", page_icon="🛵", layout="wide")

def get_sheets():
    # ดึงค่าจาก st.secrets เพื่อเชื่อมต่อ Google Sheets
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
    except Exception as e:
        return pd.DataFrame(columns=["ประตู", "ฝั่งถนน/โซน", "ซอยหลัก", "ซอยย่อย/ทางเชื่อม", "ฝั่ง/จุดรายละเอียด"])

# --- 2. จัดการสถานะ (Session State) ---
# เก็บสถานะการ Login
if 'admin_auth' not in st.session_state:
    st.session_state.admin_auth = False
# เก็บข้อมูลแถวที่กำลังพิมพ์ในหน้า Admin
if 'rows' not in st.session_state:
    st.session_state.rows = [{"main": "", "sub": "-", "det": "-"}]

# --- 3. UI ส่วนหลัก ---
st.title("🛵 ระบบพิกัดขนส่ง มน. (ฉบับสมบูรณ์)")
mapping_df = load_mapping_df()

tab1, tab2, tab3 = st.tabs(["📌 บันทึกงานส่งของ", "🔍 ค้นหาพิกัด", "⚙️ Admin Manage"])

# --- TAB 1: บันทึกงาน (5 ลำดับชั้น) ---
with tab1:
    location = streamlit_geolocation()
    if location.get('latitude'):
        lat, lon = location['latitude'], location['longitude']
        st.success(f"📍 GPS พร้อม: {lat:.6f}, {lon:.6f}")
        
        # แสดงแผนที่จุดปัจจุบัน
        layer = pdk.Layer("ScatterplotLayer", data=pd.DataFrame({'lat': [lat], 'lon': [lon]}),
                         get_position='[lon, lat]', get_color='[255, 75, 75, 230]', get_radius=3)
        st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=pdk.ViewState(latitude=lat, longitude=lon, zoom=17), map_style='carto-positron'))
        
        # ระบบ Selectbox กรองข้อมูลอัตโนมัติ
        def get_opts(df, filters, col_name):
            tmp = df.copy()
            for k, v in filters.items():
                if v and v != "-- เลือก --": tmp = tmp[tmp[k] == v]
            return sorted([str(x) for x in tmp[col_name].unique() if x and x != "-"])

        gate = st.selectbox("1. ประตู:", ["-- เลือก --"] + sorted(mapping_df['ประตู'].unique().tolist()))
        
        if gate != "-- เลือก --":
            c1, c2 = st.columns(2)
            zone = c1.selectbox("2. ฝั่งของถนน:", ["-- เลือก --"] + get_opts(mapping_df, {"ประตู": gate}, "ฝั่งถนน/โซน"))
            main_soi = c2.selectbox("3. ซอยหลัก:", ["-- เลือก --"] + get_opts(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone}, "ซอยหลัก"))
            
            c3, c4 = st.columns(2)
            sub_soi = c3.selectbox("4. ซอยย่อย/ทางเชื่อม:", ["-- เลือก --"] + get_opts(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main_soi}, "ซอยย่อย/ทางเชื่อม"))
            detail = c4.selectbox("5. ฝั่ง/จุดรายละเอียด (สุดท้าย):", ["-- เลือก --"] + get_opts(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main_soi, "ซอยย่อย/ทางเชื่อม": sub_soi}, "ฝั่ง/จุดรายละเอียด"))
            
            extra = st.text_input("✍️ หมายเหตุเพิ่มเติม (เลขห้อง/ชื่อหอ):")
            
            if st.button("🚀 บันทึกพิกัดลงระบบ", type="primary"):
                sh = get_sheets()
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # บันทึกข้อมูลลง Sheet1
                sh.worksheet("Sheet1").append_row([now, f"{gate}|{zone}|{main_soi}|{sub_soi}|{detail}|{extra}", lat, lon, "Google Maps"])
                st.balloons()
                st.success("บันทึกสำเร็จ!")

# --- TAB 2: ค้นหาพิกัดเดิม ---
with tab2:
    q = st.text_input("🔍 ค้นหาชื่อสถานที่/ซอย:")
    if st.button("ค้นหา"):
        sh = get_sheets()
        hist = pd.DataFrame(sh.worksheet("Sheet1").get_all_records())
        res = hist[hist['บันทึก'].str.contains(q, case=False, na=False)]
        if not res.empty:
            l = res.iloc[-1]
            st.info(f"พบข้อมูลล่าสุด: {l['บันทึก']}")
        else:
            st.error("ไม่พบข้อมูลที่ค้นหา")

# --- TAB 3: ADMIN MANAGE (ปรับปรุงใหม่ตามที่ขอ) ---
with tab3:
    # 1. ส่วนเช็ค PIN (ถ้าผ่านแล้วช่องจะหายไป)
    if not st.session_state.admin_auth:
        st.subheader("🔒 ยืนยันสิทธิ์ Admin")
        pin = st.text_input("กรอกรหัส PIN (9999):", type="password")
        if pin == "9999":
            st.session_state.admin_auth = True
            st.rerun()
    else:
        # 2. หน้าจอ Admin หลัก
        c_h1, c_h2 = st.columns([8, 2])
        c_h1.header("⚙️ ระบบจัดการข้อมูล (Smart Entry)")
        if c_h2.button("🔒 ออกจากระบบ"):
            st.session_state.admin_auth = False
            st.rerun()

        # ส่วนเลือก ประตู และ ฝั่งถนน (เป็นพื้นฐานของทั้งชุดข้อมูลที่จะเพิ่ม)
        c1, c2 = st.columns(2)
        with c1:
            gates = sorted(mapping_df['ประตู'].unique().tolist())
            sel_g = st.selectbox("เลือกประตูที่ต้องการเพิ่ม:", ["-- เพิ่มใหม่ --"] + gates)
            gate_f = st.text_input("ระบุชื่อประตูใหม่:") if sel_g == "-- เพิ่มใหม่ --" else sel_g
        with c2:
            zones = sorted(mapping_df[mapping_df['ประตู'] == gate_f]['ฝั่งถนน/โซน'].unique().tolist()) if gate_f else []
            sel_z = st.selectbox("เลือกฝั่งถนน/โซน:", ["-- เพิ่มใหม่ --"] + [z for z in zones if z and z != "-"])
            zone_f = st.text_input("ระบุชื่อฝั่งถนนใหม่:", value="-") if sel_z == "-- เพิ่มใหม่ --" else sel_z

        st.divider()

        # ส่วนจัดการแถว (Batch Entry)
        st.subheader("📝 รายการซอยและจุดย่อย")
        
        # รายชื่อซอยหลักที่มีอยู่แล้วในโซนนี้ (สำหรับ Smart Select)
        existing_mains = sorted(mapping_df[(mapping_df['ประตู'] == gate_f) & (mapping_df['ฝั่งถนน/โซน'] == zone_f)]['ซอยหลัก'].unique().tolist())

        def add_row(): 
            st.session_state.rows.append({"main": "", "sub": "-", "det": "-"})
        def clone_row(): 
            st.session_state.rows.append(st.session_state.rows[-1].copy())
        def del_row(i): 
            if len(st.session_state.rows) > 1: st.session_state.rows.pop(i)

        for i, row in enumerate(st.session_state.rows):
            with st.container():
                cols = st.columns([4, 4, 4, 0.5])
                
                # --- ระดับซอยหลัก ---
                with cols[0]:
                    m_opts = ["-- พิมพ์ใหม่ --"] + [m for m in existing_mains if m and m != "-"]
                    try: def_idx = m_opts.index(row['main'])
                    except: def_idx = 0
                    sel_m = st.selectbox(f"ซอยหลัก {i+1}", m_opts, index=def_idx, key=f"sm_{i}")
                    if sel_m == "-- พิมพ์ใหม่ --":
                        st.session_state.rows[i]['main'] = st.text_input(f"ระบุซอยหลักใหม่ {i+1}", value=row['main'], key=f"tm_{i}")
                    else:
                        st.session_state.rows[i]['main'] = sel_m

                # --- ระดับซอยย่อย ---
                with cols[1]:
                    curr_m = st.session_state.rows[i]['main']
                    existing_subs = sorted(mapping_df[(mapping_df['ประตู'] == gate_f) & (mapping_df['ซอยหลัก'] == curr_m)]['ซอยย่อย/ทางเชื่อม'].unique().tolist()) if curr_m else []
                    s_opts = ["-- พิมพ์ใหม่ --"] + [s for s in existing_subs if s and s != "-"]
                    try: def_s_idx = s_opts.index(row['sub'])
                    except: def_s_idx = 0
                    sel_s = st.selectbox(f"ซอยย่อย {i+1}", s_opts, index=def_s_idx, key=f"ss_{i}")
                    if sel_s == "-- พิมพ์ใหม่ --":
                        st.session_state.rows[i]['sub'] = st.text_input(f"ระบุซอยย่อยใหม่ {i+1}", value=row['sub'], key=f"ts_{i}")
                    else:
                        st.session_state.rows[i]['sub'] = sel_s

                # --- ระดับฝั่ง/จุดละเอียด ---
                with cols[2]:
                    st.session_state.rows[i]['det'] = st.text_input(f"ฝั่งสุดท้าย {i+1}", value=row['det'], key=f"td_{i}")

                # --- ปุ่มลบแถว ---
                with cols[3]:
                    st.write("##")
                    if st.button("🗑️", key=f"del_{i}"):
                        del_row(i); st.rerun()

        # ปุ่มควบคุมแถว
        cb1, cb2, _ = st.columns([2, 2, 6])
        cb1.button("➕ เพิ่มแถวใหม่", on_click=add_row)
        cb2.button("👯 คัดลอกแถวบน", on_click=clone_row)

        st.divider()
        
        # ปุ่มบันทึกข้อมูลทั้งหมด
        if st.button("💾 บันทึกข้อมูลทั้งหมดลง Google Sheets", type="primary", use_container_width=True):
            final_data = [[gate_f, zone_f, r['main'], r['sub'], r['det']] for r in st.session_state.rows if r['main']]
            if final_data:
                sh = get_sheets()
                sh.worksheet("Mapping").append_rows(final_data)
                st.session_state.rows = [{"main": "", "sub": "-", "det": "-"}]
                st.cache_data.clear() # ล้าง Cache เพื่อให้ข้อมูลใหม่โชว์ทันที
                st.success(f"บันทึกข้อมูลเรียบร้อย {len(final_data)} รายการ!")
                st.rerun()
            else:
                st.error("กรุณากรอกข้อมูลซอยหลักอย่างน้อย 1 รายการ")

        # ส่วนจัดการลบข้อมูลเดิม
        with st.expander("🗑️ ลบข้อมูลเดิมในระบบ"):
            st.dataframe(mapping_df, use_container_width=True)
            idx_to_del = st.number_input("เลือก Index ที่จะลบ:", min_value=0, max_value=len(mapping_df)-1, step=1)
            if st.button("❌ ยืนยันการลบแถวนี้"):
                sh = get_sheets()
                # +2 เพราะ Header อยู่แถว 1 และ Index เริ่มที่ 0
                sh.worksheet("Mapping").delete_rows(int(idx_to_del) + 2)
                st.cache_data.clear()
                st.success("ลบข้อมูลสำเร็จ!")
                st.rerun()
