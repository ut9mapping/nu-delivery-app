import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import google.generativeai as genai
import re
import pydeck as pdk

# --- 1. ตั้งค่าพื้นฐาน ---
st.set_page_config(page_title="NU Delivery Admin Pro", page_icon="🛵", layout="wide")

def get_sheets():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])

try:
    genai.configure(api_key=st.secrets["API_KEY"])
    model = genai.GenerativeModel('models/gemini-1.5-flash')
except:
    st.error("AI Config Error")

# --- 2. ฟังก์ชันจัดการข้อมูล ---
def load_mapping_df():
    try:
        sh = get_sheets()
        sheet = sh.worksheet("Mapping")
        data = sheet.get_all_records()
        df = pd.DataFrame(data) if data else pd.DataFrame(columns=["ประตู", "ฝั่งถนน/โซน", "ซอยหลัก", "ซอยย่อย/ทางเชื่อม", "ฝั่ง/จุดรายละเอียด"])
        df.columns = [str(c).strip() for c in df.columns]
        return df.map(lambda x: str(x).strip() if x is not None else "")
    except:
        return pd.DataFrame(columns=["ประตู", "ฝั่งถนน/โซน", "ซอยหลัก", "ซอยย่อย/ทางเชื่อม", "ฝั่ง/จุดรายละเอียด"])

def display_precision_map(lat, lon, zoom=18):
    layer = pdk.Layer("ScatterplotLayer", data=pd.DataFrame({'lat': [lat], 'lon': [lon]}),
        get_position='[lon, lat]', get_color='[255, 75, 75, 230]', get_radius=3)
    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=pdk.ViewState(latitude=lat, longitude=lon, zoom=zoom), map_style='carto-positron'))

# --- 3. ส่วน UI หลัก ---
st.title("🛵 ระบบพิกัดขนส่ง มน. (Dynamic Admin)")
mapping_df = load_mapping_df()

tab1, tab2, tab3 = st.tabs(["📌 บันทึกงานส่งของ", "🔍 ค้นหาพิกัด", "⚙️ Admin Manage"])

# --- TAB 1: บันทึกงาน (ตามเดิม) ---
with tab1:
    location = streamlit_geolocation()
    if location.get('latitude'):
        lat, lon = location['latitude'], location['longitude']
        st.success(f"📍 GPS พร้อม: {lat:.6f}, {lon:.6f}")
        display_precision_map(lat, lon, zoom=17)
        gate = st.selectbox("1. เลือกประตู:", ["-- เลือก --"] + sorted(mapping_df['ประตู'].unique().tolist()))
        if gate != "-- เลือก --":
            # กรองข้อมูลตามลำดับ 5 ระดับ
            def get_opts(df, filters):
                temp = df.copy()
                for k, v in filters.items():
                    if v and v != "-- เลือก --": temp = temp[temp[k] == v]
                idx = len(filters)
                return sorted([str(x) for x in temp.iloc[:, idx].unique() if str(x) not in ["", "-"]]) if idx < len(df.columns) else []

            c1, c2 = st.columns(2)
            zone = c1.selectbox("2. ฝั่งของถนน:", ["-- เลือก --"] + get_opts(mapping_df, {"ประตู": gate}))
            main_soi = c2.selectbox("3. ซอยหลัก:", ["-- เลือก --"] + get_opts(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone}))
            
            c3, c4 = st.columns(2)
            sub_soi = c3.selectbox("4. ซอยย่อย/ทางเชื่อม:", ["-- เลือก --"] + get_opts(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main_soi}))
            detail = c4.selectbox("5. ฝั่งของซอยย่อย (ลำดับสุดท้าย):", ["-- เลือก --"] + get_opts(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main_soi, "ซอยย่อย/ทางเชื่อม": sub_soi}))
            
            extra = st.text_input("✍️ หมายเหตุเพิ่มเติม (เลขห้อง/ชื่อหอ):")
            if st.button("🚀 บันทึกพิกัดลงฐานข้อมูล"):
                sh = get_sheets()
                sh.worksheet("Sheet1").append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), f"{gate}|{zone}|{main_soi}|{sub_soi}|{detail}|{extra}", lat, lon, f"http://google.com/maps?q={lat},{lon}"])
                st.balloons(); st.success("บันทึกสำเร็จ!")

# --- TAB 2: ค้นหา (ตามเดิม) ---
with tab2:
    query = st.text_input("🔍 ค้นหาชื่อสถานที่/ซอย:")
    if st.button("ค้นหา"):
        sh = get_sheets(); history_df = pd.DataFrame(sh.worksheet("Sheet1").get_all_records())
        results = history_df[history_df['บันทึก'].str.contains(query, case=False, na=False)]
        if not results.empty:
            last = results.iloc[-1]; st.info(f"พบข้อมูล: {last['บันทึก']}")
            display_precision_map(float(last['ละติจูด']), float(last['ลองจิจูด']), zoom=19)
        else: st.error("ไม่พบข้อมูล")

# --- TAB 3: ADMIN MANAGE (ปรับปรุงใหม่ตามคำขอ) ---
with tab3:
    st.header("⚙️ จัดการโครงสร้างซอยและฝั่งถนน")
    admin_pin = st.text_input("กรอก Admin PIN:", type="password")
    
    if admin_pin == "9999":
        st.subheader("➕ เพิ่มข้อมูลชุดใหม่ (กดปุ่มบวกเพื่อเพิ่มซอย/ฝั่ง)")
        
        # 1. เลือกส่วนหัว (ประตู และ ฝั่งถนน)
        c1, c2 = st.columns(2)
        with c1:
            sel_gate = st.selectbox("เลือกประตู:", ["-- เพิ่มใหม่ --"] + sorted(mapping_df['ประตู'].unique().tolist()))
            final_gate = st.text_input("ระบุชื่อประตูใหม่:") if sel_gate == "-- เพิ่มใหม่ --" else sel_gate
        with c2:
            sel_zone = st.selectbox("เลือกฝั่งของถนน:", ["-- เพิ่มใหม่ --"] + sorted(mapping_df[mapping_df['ประตู']==final_gate]['ฝั่งถนน/โซน'].unique().tolist())) if final_gate else "-- เพิ่มใหม่ --"
            final_zone = st.text_input("ระบุฝั่งถนนใหม่ (เช่น ซ้าย/ขวา):", value="-") if sel_zone == "-- เพิ่มใหม่ --" else sel_zone

        st.markdown("---")
        
        # 2. ส่วน Dynamic Rows (ซอยหลัก -> ซอยย่อย -> ฝั่งสุดท้าย)
        if 'rows' not in st.session_state:
            st.session_state.rows = [{"main": "", "sub": "-", "det": "-"}]

        def add_row(): st.session_state.rows.append({"main": "", "sub": "-", "det": "-"})
        def remove_row(i): 
            if len(st.session_state.rows) > 1: st.session_state.rows.pop(i)

        for i, row in enumerate(st.session_state.rows):
            cols = st.columns([3, 3, 3, 0.5])
            st.session_state.rows[i]['main'] = cols[0].text_input(f"ซอยหลัก", value=row['main'], key=f"m_{i}", placeholder="เช่น ซอยเฟื่องฟ้า")
            st.session_state.rows[i]['sub'] = cols[1].text_input(f"ซอยย่อย", value=row['sub'], key=f"s_{i}")
            st.session_state.rows[i]['det'] = cols[2].text_input(f"ฝั่งซอยย่อย (ท้ายสุด)", value=row['det'], key=f"d_{i}", placeholder="เช่น ฝั่งซ้าย/ท้ายซอย")
            if cols[3].button("🗑️", key=f"del_{i}"):
                remove_row(i); st.rerun()

        # ปุ่มบวกจำนวนซอย/ฝั่ง
        st.button("➕ เพิ่มรายการถัดไป", on_click=add_row)

        if st.button("💾 บันทึกข้อมูลทั้งหมด", type="primary"):
            new_entries = [[final_gate, final_zone, r['main'], r['sub'], r['det']] for r in st.session_state.rows if r['main']]
            if new_entries:
                sh = get_sheets(); sh.worksheet("Mapping").append_rows(new_entries)
                st.session_state.rows = [{"main": "", "sub": "-", "det": "-"}]
                st.success(f"บันทึกสำเร็จ {len(new_entries)} รายการ!"); st.rerun()
            else: st.error("กรุณากรอกชื่อซอยหลักอย่างน้อย 1 ช่อง")

        st.divider()

        # 3. ตารางและการลบ (ยืนยันรหัส)
        st.subheader("🗑️ รายการทั้งหมด (ลบข้อมูล)")
        st.dataframe(mapping_df, use_container_width=True)
        del_idx = st.number_input("ลำดับแถวที่จะลบ (Index):", min_value=0, max_value=len(mapping_df)-1, step=1)
        
        if st.button("❌ ลบแถวที่เลือก", type="secondary"):
            st.session_state.pending_del = del_idx
        
        if st.session_state.get('pending_del') is not None:
            st.warning(f"คุณกำลังจะลบแถวที่ {st.session_state.pending_del} ยืนยันหรือไม่?")
            v_pin = st.text_input("ใส่รหัส PIN เพื่อลบถาวร:", type="password", key="v_pin")
            if st.button("🔥 ยืนยันการลบเด็ดขาด"):
                if v_pin == "9999":
                    sh = get_sheets(); sh.worksheet("Mapping").delete_rows(int(st.session_state.pending_del) + 2)
                    st.session_state.pending_del = None
                    st.success("ลบเรียบร้อย!"); st.rerun()
                else: st.error("รหัสผิด")
