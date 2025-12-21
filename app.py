import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. ตั้งค่าพื้นฐานและการเชื่อมต่อ Google Sheets ---
st.set_page_config(page_title="NU Delivery Pro: Ultimate Admin", page_icon="🛵", layout="wide")

def get_sheets():
    # เชื่อมต่อ Google Sheets โดยใช้ Service Account จาก st.secrets
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

# เก็บแถวข้อมูลที่กำลังกรอก
if 'entry_rows' not in st.session_state:
    st.session_state.entry_rows = [{"main": "", "sub": "-", "det": "-"}]

# --- 3. UI ส่วนหลัก ---
st.title("🛵 ระบบพิกัดขนส่ง มน. (Smart & Flexible)")
mapping_df = load_mapping_df()

tab1, tab2, tab3 = st.tabs(["📌 บันทึกงานส่งของ", "🔍 ค้นหาพิกัด", "⚙️ Admin Manage"])

# --- TAB 1 & 2: ส่วนการใช้งานทั่วไป ---
with tab1:
    location = streamlit_geolocation()
    if location.get('latitude'):
        lat, lon = location['latitude'], location['longitude']
        st.success(f"📍 GPS พร้อมบันทึก: {lat:.6f}, {lon:.6f}")
        # แสดงแผนที่ย่อ
        layer = pdk.Layer("ScatterplotLayer", data=pd.DataFrame({'lat': [lat], 'lon': [lon]}),
                         get_position='[lon, lat]', get_color='[255, 75, 75, 230]', get_radius=3)
        st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=pdk.ViewState(latitude=lat, longitude=lon, zoom=17), map_style='carto-positron'))
        
        # ระบบเลือก 5 ระดับ
        gate = st.selectbox("1. เลือกประตู:", ["-- เลือก --"] + sorted(mapping_df['ประตู'].unique().tolist()))
        if gate != "-- เลือก --":
            def get_options(df, filters, col_name):
                tmp = df.copy()
                for k, v in filters.items():
                    if v and v != "-- เลือก --": tmp = tmp[tmp[k] == v]
                return sorted([str(x) for x in tmp[col_name].unique() if x and x != "-"])

            c1, c2 = st.columns(2)
            zone = c1.selectbox("2. ฝั่งของถนน:", ["-- เลือก --"] + get_options(mapping_df, {"ประตู": gate}, "ฝั่งถนน/โซน"))
            main_soi = c2.selectbox("3. ซอยหลัก:", ["-- เลือก --"] + get_options(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone}, "ซอยหลัก"))
            
            c3, c4 = st.columns(2)
            sub_soi = c3.selectbox("4. ซอยย่อย/ทางเชื่อม:", ["-- เลือก --"] + get_options(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main_soi}, "ซอยย่อย/ทางเชื่อม"))
            detail = c4.selectbox("5. ฝั่ง/จุดละเอียด:", ["-- เลือก --"] + get_options(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main_soi, "ซอยย่อย/ทางเชื่อม": sub_soi}, "ฝั่ง/จุดรายละเอียด"))
            
            extra = st.text_input("✍️ หมายเหตุ (เลขห้อง/ชื่อหอ):")
            if st.button("🚀 บันทึกพิกัดตอนนี้", type="primary"):
                sh = get_sheets()
                sh.worksheet("Sheet1").append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), f"{gate}|{zone}|{main_soi}|{sub_soi}|{detail}|{extra}", lat, lon, "Maps"])
                st.balloons(); st.success("บันทึกสำเร็จ!")

with tab2:
    q = st.text_input("🔍 ค้นหาชื่อสถานที่ที่เคยบันทึก:")
    if st.button("ค้นหา"):
        sh = get_sheets(); hist = pd.DataFrame(sh.worksheet("Sheet1").get_all_records())
        res = hist[hist['บันทึก'].str.contains(q, case=False, na=False)]
        if not res.empty:
            st.info(f"พบข้อมูลล่าสุด: {res.iloc[-1]['บันทึก']}")
        else: st.error("ไม่พบข้อมูล")

# --- TAB 3: ADMIN MANAGE (ปรับปรุงตามโจทย์) ---
with tab3:
    # 1. ส่วนเช็ครหัส (ซ่อนอัตโนมัติเมื่อผ่าน)
    if not st.session_state.admin_auth:
        st.subheader("🔒 ยืนยันสิทธิ์ Admin")
        pin = st.text_input("กรอกรหัสผ่านเพื่อจัดการข้อมูล:", type="password")
        if pin == "9999":
            st.session_state.admin_auth = True
            st.rerun() # รีโหลดหน้าเพื่อซ่อนช่อง PIN ทันที
    
    # 2. เมื่อผ่านรหัสแล้ว จะแสดงส่วนนี้แทน
    else:
        c_head1, c_head2 = st.columns([8, 2])
        c_head1.header("⚙️ ระบบจัดการโครงสร้างข้อมูล")
        if c_head2.button("🔒 ออกจากระบบ"):
            st.session_state.admin_auth = False
            st.rerun()

        # ส่วนที่ 1: ตั้งค่า ประตู และ ฝั่งถนน (เป็นรากฐานหลัก)
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

        # ส่วนที่ 2: ระบบเพิ่มระดับซอย/จุดย่อย (Batch Entry แบบฉลาด)
        st.subheader("📝 เพิ่มรายการ (เลือกซอยเดิม หรือ พิมพ์ใหม่)")
        
        # รายชื่อซอยหลักเดิมในโซนนี้
        existing_mains = sorted(mapping_df[(mapping_df['ประตู'] == gate_f) & (mapping_df['ฝั่งถนน/โซน'] == zone_f)]['ซอยหลัก'].unique().tolist())

        # ฟังก์ชันควบคุมแถว
        def add_row(): st.session_state.entry_rows.append({"main": "", "sub": "-", "det": "-"})
        def clone_row(): st.session_state.entry_rows.append(st.session_state.entry_rows[-1].copy())
        def del_row(i): 
            if len(st.session_state.entry_rows) > 1: st.session_state.entry_rows.pop(i)

        for i, row in enumerate(st.session_state.entry_rows):
            with st.container():
                cols = st.columns([4, 4, 4, 0.5])
                
                # --- ระดับ ซอยหลัก (Smart Select) ---
                with cols[0]:
                    m_opts = ["-- พิมพ์ใหม่ --"] + [m for m in existing_mains if m and m != "-"]
                    try: d_idx = m_opts.index(row['main'])
                    except: d_idx = 0
                    sel_m = st.selectbox(f"ซอยหลัก {i+1}", m_opts, index=d_idx, key=f"sm_{i}")
                    if sel_m == "-- พิมพ์ใหม่ --":
                        st.session_state.entry_rows[i]['main'] = st.text_input(f"ชื่อซอยหลักใหม่ {i+1}", value=row['main'], key=f"tm_{i}")
                    else:
                        st.session_state.entry_rows[i]['main'] = sel_m

                # --- ระดับ ซอยย่อย (Smart Select) ---
                with cols[1]:
                    curr_m = st.session_state.entry_rows[i]['main']
                    existing_subs = sorted(mapping_df[(mapping_df['ประตู'] == gate_f) & (mapping_df['ซอยหลัก'] == curr_m)]['ซอยย่อย/ทางเชื่อม'].unique().tolist()) if curr_m else []
                    s_opts = ["-- พิมพ์ใหม่ --"] + [s for s in existing_subs if s and s != "-"]
                    try: ds_idx = s_opts.index(row['sub'])
                    except: ds_idx = 0
                    sel_s = st.selectbox(f"ซอยย่อย {i+1}", s_opts, index=ds_idx, key=f"ss_{i}")
                    if sel_s == "-- พิมพ์ใหม่ --":
                        st.session_state.entry_rows[i]['sub'] = st.text_input(f"ชื่อซอยย่อยใหม่ {i+1}", value=row['sub'], key=f"ts_{i}")
                    else:
                        st.session_state.entry_rows[i]['sub'] = sel_s

                # --- ระดับ ฝั่ง/จุดสุดท้าย ---
                with cols[2]:
                    st.session_state.entry_rows[i]['det'] = st.text_input(f"ฝั่งสุดท้าย {i+1}", value=row['det'], key=f"td_{i}")

                # --- ลบแถว ---
                with cols[3]:
                    st.write("##")
                    if st.button("🗑️", key=f"dr_{i}"): del_row(i); st.rerun()

        # ปุ่มจัดการแถว
        btn_c1, btn_c2, _ = st.columns([2, 2, 6])
        btn_c1.button("➕ เพิ่มแถวใหม่", on_click=add_row)
        btn_c2.button("👯 คัดลอกแถวบน", on_click=clone_row)

        st.divider()
        if st.button("💾 บันทึกทั้งหมดลง Google Sheets", type="primary", use_container_width=True):
            final_data = [[gate_f, zone_f, r['main'], r['sub'], r['det']] for r in st.session_state.entry_rows if r['main']]
            if final_data:
                sh = get_sheets()
                sh.worksheet("Mapping").append_rows(final_data)
                st.session_state.entry_rows = [{"main": "", "sub": "-", "det": "-"}]
                st.cache_data.clear() # อัปเดตข้อมูลในระบบทันที
                st.success(f"บันทึกสำเร็จ {len(final_data)} รายการ!"); st.rerun()
            else:
                st.error("กรุณากรอกชื่อซอยหลักอย่างน้อย 1 แถว")

        # ส่วนจัดการลบข้อมูลเดิม (Expander เพื่อความคลีน)
        with st.expander("🗑️ ลบข้อมูลเดิมในระบบ"):
            st.dataframe(mapping_df, use_container_width=True)
            idx_del = st.number_input("Index แถวที่จะลบ:", min_value=0, max_value=len(mapping_df)-1, step=1)
            if st.button("❌ ยืนยันการลบ"):
                sh = get_sheets(); sh.worksheet("Mapping").delete_rows(int(idx_del) + 2)
                st.cache_data.clear(); st.success("ลบสำเร็จ!"); st.rerun()
