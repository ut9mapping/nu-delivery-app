import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. การตั้งค่าระบบ ---
st.set_page_config(page_title="NU Delivery: Smart Pro V2", layout="wide")

# พิกัดเริ่มต้น (ม.นเรศวร) กรณีหาพิกัดไม่พบ เพื่อป้องกัน Error NaN
DEFAULT_LAT = 16.7469
DEFAULT_LON = 100.1914

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])
    except: return None

def load_data():
    sh = get_sheets()
    if not sh: return pd.DataFrame()
    ws = sh.worksheet("Sheet1")
    df = pd.DataFrame(ws.get_all_records())
    if not df.empty:
        df.columns = [c.strip() for c in df.columns]
        # แปลงพิกัดเป็นตัวเลข และลบทิ้งแถวที่ไม่มีพิกัด (ป้องกัน NaN)
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
        return df.dropna(subset=['lat', 'lon'])
    return df

# --- 2. ระบบ Smart Search (ความฉลาดแบบ AI) ---
def smart_search(df, query):
    if not query: return df
    keywords = query.lower().split()
    def calculate_score(row):
        score = 0
        text = f"{row.get('place_name','')} {row.get('note','')} {row.get('gate','')} {row.get('main_alley','')}".lower()
        for kw in keywords:
            if kw in text:
                score += 1
                if kw in str(row.get('place_name','')).lower(): score += 2 
        return score
    
    temp_df = df.copy()
    temp_df['relevance'] = temp_df.apply(calculate_score, axis=1)
    return temp_df[temp_df['relevance'] > 0].sort_values(by='relevance', ascending=False)

# --- 3. การแสดงผล ---
st.title("🛵 NU Delivery Smart Pro")

tab1, tab2, tab3 = st.tabs(["📌 บันทึกหน้างาน", "⚙️ จัดการข้อมูล (Admin)", "🔍 ค้นหาอัจฉริยะ"])

# --- TAB 1: USER (ช่องใส่รูปครบ) ---
with tab1:
    st.subheader("📝 บันทึกพิกัดและรูปถ่าย")
    loc = streamlit_geolocation()
    lat, lon = loc.get('latitude'), loc.get('longitude')
    
    if lat and lon: st.success(f"📍 GPS Lock: {lat}, {lon}")
    else: st.warning("📡 กำลังรอพิกัด... โปรดอนุญาตสิทธิ์ตำแหน่ง")

    p_name = st.text_input("🏠 ชื่อสถานที่/โครงการ")
    note = st.text_area("🗒️ จุดสังเกต (เช่น ตึกแถวสีเหลือง)")
    
    st.write("🖼️ อัปโหลดรูปภาพ (3 รูป)")
    c1, c2, c3 = st.columns(3)
    i1 = c1.file_uploader("รูป 1", type=['jpg','png'], key="u1")
    i2 = c2.file_uploader("รูป 2", type=['jpg','png'], key="u2")
    i3 = c3.file_uploader("รูป 3", type=['jpg','png'], key="u3")

    if st.button("🚀 บันทึกข้อมูล", use_container_width=True, type="primary"):
        if lat and p_name:
            ws = get_sheets().worksheet("Sheet1")
            imgs = ["Yes" if i else "No" for i in [i1, i2, i3]]
            new_row = [datetime.now().strftime("%Y-%m-%d %H:%M"), lat, lon, p_name, note, "รอวิเคราะห์"] + imgs + [""]*7
            ws.insert_row(new_row, index=2)
            st.success("✅ บันทึกเรียบร้อย!")
        else: st.error("⚠️ ข้อมูลไม่ครบ")

# --- TAB 2: ADMIN (ปุ่มแก้ไข/ลบ รายตัว) ---
with tab2:
    pwd = st.text_input("รหัสผ่านแอดมิน", type="password")
    if pwd == "9999":
        st.info("🔓 โหมดแอดมิน: คุณสามารถแก้ไขหรือลบพิกัดได้รายจุด")
        df_admin = load_data()
        
        if not df_admin.empty:
            for idx, row in df_admin.iterrows():
                # แปลง index ให้เป็น int มาตรฐานของ Python เพื่อป้องกัน Error
                actual_idx = int(idx) + 2 
                with st.expander(f"📍 {row['place_name']} (แถวที่ {actual_idx})"):
                    col_edit, col_del = st.columns([3, 1])
                    
                    with col_edit:
                        e_note = st.text_input("แก้ไขหมายเหตุ", value=row['note'], key=f"n_{idx}")
                        e_gate = st.text_input("ประตู", value=row.get('gate', ''), key=f"g_{idx}")
                        if st.button("💾 บันทึกแก้ไข", key=f"save_{idx}"):
                            ws = get_sheets().worksheet("Sheet1")
                            ws.update_cell(actual_idx, 5, e_note)
                            ws.update_cell(actual_idx, 10, e_gate)
                            st.success("อัปเดตแล้ว!")
                            st.rerun()
                    
                    with col_del:
                        st.write("---")
                        if st.button("🗑️ ลบถาวร", key=f"del_{idx}"):
                            get_sheets().worksheet("Sheet1").delete_rows(actual_idx)
                            st.warning("ลบข้อมูลแล้ว")
                            st.rerun()
        else: st.info("ไม่มีข้อมูล")

# --- TAB 3: SMART SEARCH & INTERACTIVE MAP ---
with tab3:
    st.subheader("🔍 ค้นหาอัจฉริยะ & อาณาเขต")
    raw_df = load_data()
    
    if not raw_df.empty:
        q = st.text_input("🔎 ค้นหา (เช่น 'ประตู 4 ตึกแถวสีแดง'):")
        results = smart_search(raw_df, q)
        
        # ป้องกัน Error NaN: คำนวณจุดกึ่งกลาง ถ้าไม่มีผลลัพธ์ให้ไปที่ค่า Default
        if not results.empty:
            m_lat, m_lon = results['lat'].mean(), results['lon'].mean()
        else:
            m_lat, m_lon = DEFAULT_LAT, DEFAULT_LON

        # แผนที่อาณาเขตพร้อม Hover Tooltip
        view_state = pdk.ViewState(latitude=m_lat, longitude=m_lon, zoom=14)
        
        layer = pdk.Layer(
            "ScatterplotLayer",
            results,
            get_position='[lon, lat]',
            get_color='[255, 75, 75, 200]',
            get_radius=40,
            pickable=True,
        )
        
        st.pydeck_chart(pdk.Deck(
            map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
            initial_view_state=view_state,
            layers=[layer],
            tooltip={
                "html": "<b>สถานที่:</b> {place_name} <br/> <b>ประตู:</b> {gate} <br/> <b>หมายเหตุ:</b> {note}",
                "style": {"backgroundColor": "white", "color": "black"}
            }
        ))
        
        # แสดงรายการที่พบ
        st.write(f"พบ {len(results)} รายการ")
        for _, r in results.iterrows():
            with st.expander(f"📌 {r['place_name']}"):
                col_a, col_b = st.columns(2)
                with col_a:
                    st.write(f"**ประตู:** {r.get('gate','-')} | **โน้ต:** {r['note']}")
                    st.link_button("🚗 นำทาง", f"https://www.google.com/maps?q={r['lat']},{r['lon']}")
                with col_b:
                    # ภาพจำลองดาวเทียมซูมรายจุด
                    st.pydeck_chart(pdk.Deck(
                        map_style="https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
                        initial_view_state=pdk.ViewState(latitude=r['lat'], longitude=r['lon'], zoom=18),
                        layers=[pdk.Layer("ScatterplotLayer", pd.DataFrame([r]), get_position='[lon, lat]', get_color='[255,0,0]', get_radius=10)]
                    ))
    else: st.info("ยังไม่มีข้อมูลพิกัด")
