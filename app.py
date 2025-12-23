import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime

# --- 1. ตั้งค่าการเชื่อมต่อ ---
st.set_page_config(page_title="NU Delivery: Admin Analytics", layout="wide")

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])
    except Exception as e:
        st.error(f"❌ เชื่อมต่อไม่ได้: {e}")
        return None

def load_data(sheet_name):
    sh = get_sheets()
    if not sh: return pd.DataFrame()
    return pd.DataFrame(sh.worksheet(sheet_name).get_all_records())

# ฟังก์ชันช่วยกรองตัวเลือก Dropdown
def get_options(df, target_col, filters={}):
    temp_df = df.copy()
    for col, val in filters.items():
        if val:
            temp_df = temp_df[temp_df[col] == val]
    options = sorted(temp_df[target_col].unique().tolist())
    return [opt for opt in options if opt]

# --- 2. ส่วนแสดงผลหน้าจอ ---
st.title("🛵 ระบบจัดการพิกัด (User & Admin Analysis)")

tab1, tab2, tab3 = st.tabs(["📌 บันทึกหน้างาน (User)", "⚙️ วิเคราะห์ข้อมูล (Admin)", "🔍 ค้นหา/นำทาง"])

# --- TAB 1: USER (รับข้อมูลดิบ) ---
with tab1:
    st.subheader("📝 บันทึกพิกัดใหม่")
    loc = streamlit_geolocation()
    lat, lon = loc.get('latitude'), loc.get('longitude')
    
    if lat: st.success(f"📍 GPS Lock: {lat}, {lon}")
    else: st.warning("📡 กรุณารอสัญญาณ GPS...")

    p_name = st.text_input("🏠 ชื่อสถานที่/บ้านเลขที่")
    note = st.text_area("🗒️ หมายเหตุ/จุดสังเกต")
    
    st.write("🖼️ รูปภาพ 3 มุม")
    c1, c2, c3 = st.columns(3)
    img1 = c1.file_uploader("รูปที่ 1", type=['jpg','png'], key="u1")
    img2 = c2.file_uploader("รูปที่ 2", type=['jpg','png'], key="u2")
    img3 = c3.file_uploader("รูปที่ 3", type=['jpg','png'], key="u3")

    if st.button("🚀 ส่งข้อมูลให้แอดมิน", use_container_width=True, type="primary"):
        if lat and p_name:
            # เก็บสถานะรูป
            imgs = ["Yes" if i else "No" for i in [img1, img2, img3]]
            # เตรียมแถว (16 คอลัมน์ตามหัวข้อ)
            new_row = [datetime.now().strftime("%Y-%m-%d %H:%M"), lat, lon, p_name, note, "รอวิเคราะห์"] + imgs + [""]*7
            get_sheets().worksheet("Sheet1").insert_row(new_row, index=2)
            st.success("✅ บันทึกสำเร็จ! ส่งข้อมูลเข้าคลังรอแอดมินแยกหมวดหมู่")
        else: st.warning("⚠️ กรุณาระบุชื่อสถานที่และพิกัด")

# --- TAB 2: ADMIN (วิเคราะห์และเลือกโครงสร้างสถานที่) ---
with tab2:
    st.subheader("🛠️ การวิเคราะห์ข้อมูลสถานที่")
    
    # โหลดทั้งข้อมูลดิบและ Mapping
    df_raw = load_data("Sheet1")
    df_map = load_data("Mapping")
    
    pending = df_raw[df_raw['status'] == "รอวิเคราะห์"]
    
    if not pending.empty:
        # เลือกรายการที่จะวิเคราะห์
        target_idx = st.selectbox("เลือกรายการที่จะจัดแจงข้อมูล:", pending.index, 
                                 format_func=lambda x: f"{pending.loc[x, 'place_name']} ({pending.loc[x, 'timestamp']})")
        
        st.info(f"📍 ข้อมูลจาก User: {pending.loc[target_idx, 'place_name']} | หมายเหตุ: {pending.loc[target_idx, 'note']}")
        
        st.write("---")
        st.write("🔍 **เลือกโครงสร้างสถานที่จากฐานข้อมูล:**")
        
        # Cascading Dropdowns (เลือกอันบน กรองอันล่าง)
        col1, col2 = st.columns(2)
        
        with col1:
            g = st.selectbox("1. ประตู", get_options(df_map, 'gate'))
            r = st.selectbox("2. ถนน", get_options(df_map, 'road', {'gate': g}))
            rs = st.selectbox("3. ฝั่งถนน", get_options(df_map, 'road_side', {'gate': g, 'road': r}))
            ma = st.selectbox("4. ซอยหลัก", get_options(df_map, 'main_alley', {'gate': g, 'road': r, 'road_side': rs}))
            
        with col2:
            ms = st.selectbox("5. ฝั่งซอยหลัก", get_options(df_map, 'main_side', {'gate': g, 'road': r, 'main_alley': ma}))
            sa = st.selectbox("6. ซอยย่อย", get_options(df_map, 'sub_alley', {'gate': g, 'main_alley': ma}))
            ss = st.selectbox("7. ฝั่งซอยย่อย", get_options(df_map, 'sub_side', {'gate': g, 'sub_alley': sa}))

        if st.button("💾 ยืนยันการวิเคราะห์และบันทึก", type="primary"):
            ws = get_sheets().worksheet("Sheet1")
            row_num = int(target_idx) + 2
            
            # อัปเดตข้อมูลที่แอดมินเลือก (คอลัมน์ J-P ใน Sheet1)
            updates = [
                {'range': f'F{row_num}', 'values': [["วิเคราะห์แล้ว"]]},
                {'range': f'J{row_num}:P{row_num}', 'values': [[g, r, rs, ma, ms, sa, ss]]}
            ]
            for up in updates:
                ws.update(up['range'], up['values'])
            
            st.success("✅ จัดแจงข้อมูลเรียบร้อย!")
            st.rerun()
            
        # ส่วนแอดมินเพิ่ม Mapping ใหม่
        with st.expander("➕ เพิ่มโครงสร้างสถานที่ใหม่เข้า Database"):
            new_g = st.text_input("ประตูใหม่")
            new_a = st.text_input("ซอยใหม่")
            if st.button("บันทึกโครงสร้างใหม่"):
                get_sheets().worksheet("Mapping").append_row([new_g, "", "", new_a, "", "", ""])
                st.success("เพิ่มข้อมูลสำเร็จ")

    else: st.info("🎉 ไม่มีข้อมูลค้างวิเคราะห์")

# --- TAB 3: SEARCH & NAVIGATION ---
with tab3:
    st.subheader("🔍 ค้นหาและนำทาง")
    search_df = load_data("Sheet1")
    q = st.text_input("ค้นหาชื่อสถานที่, ซอย, หรือประตู:")
    
    if not search_df.empty:
        # กรองข้อมูล
        res = search_df[search_df.apply(lambda r: q.lower() in str(r.values).lower(), axis=1)]
        
        for idx, row in res.iterrows():
            with st.expander(f"📍 {row['place_name']} | {row['gate']} > {row['main_alley']}"):
                c_a, c_b = st.columns([3, 1])
                with c_a:
                    st.write(f"**พิกัดละเอียด:** ประตู {row['gate']}, {row['road']}, {row['main_alley']} ({row['main_side']})")
                    st.write(f"**หมายเหตุ:** {row['note']}")
                with c_b:
                    nav_url = f"https://www.google.com/maps/dir/?api=1&destination={row['lat']},{row['lon']}"
                    st.link_button("🚗 นำทาง", nav_url, type="primary")
