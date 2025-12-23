import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. การตั้งค่าระบบ ---
st.set_page_config(page_title="NU Delivery: Processor", layout="wide")

DEFAULT_LAT, DEFAULT_LON = 16.7469, 100.1914

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
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    if not df.empty:
        df.columns = [c.strip() for c in df.columns]
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
        return df.dropna(subset=['lat', 'lon'])
    return df

# --- 2. ฟังก์ชันช่วยค้นหา (Smart Search) ---
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

# --- 3. UI หน้าจอหลัก ---
st.title("🛵 NU Delivery: Data Processor")

tab1, tab2, tab3 = st.tabs(["📌 ส่งข้อมูล (User)", "⚙️ ประมวลผล/วิเคราะห์ (Admin)", "🔍 ค้นหาอัจฉริยะ"])

# --- TAB 1: USER (ส่งพิกัดและรูป) ---
with tab1:
    st.subheader("📝 บันทึกพิกัดใหม่")
    loc = streamlit_geolocation()
    lat, lon = loc.get('latitude'), loc.get('longitude')
    
    p_name = st.text_input("🏠 ชื่อสถานที่/ตึกแถว (ข้อมูลจาก User)")
    note = st.text_area("🗒️ จุดสังเกต/รายละเอียดเพิ่มเติม")
    
    st.write("🖼️ อัปโหลดรูปภาพประกอบ (แอดมินจะใช้ดูเพื่อวิเคราะห์)")
    c1, c2, c3 = st.columns(3)
    i1 = c1.file_uploader("รูป 1", type=['jpg','png'], key="u1")
    i2 = c2.file_uploader("รูป 2", type=['jpg','png'], key="u2")
    i3 = c3.file_uploader("รูป 3", type=['jpg','png'], key="u3")

    if st.button("🚀 ส่งข้อมูลให้แอดมิน", use_container_width=True, type="primary"):
        if lat and p_name:
            ws = get_sheets().worksheet("Sheet1")
            imgs = ["Yes" if i else "No" for i in [i1, i2, i3]]
            # บันทึกข้อมูลดิบลงชีต (Status จะเป็น 'รอวิเคราะห์')
            new_row = [datetime.now().strftime("%Y-%m-%d %H:%M"), lat, lon, p_name, note, "รอวิเคราะห์"] + imgs + ["", "", "", "", "", ""]
            ws.insert_row(new_row, index=2)
            st.success("✅ ส่งข้อมูลสำเร็จ! รอแอดมินประมวลผลแยกหมวดหมู่")
        else: st.error("⚠️ กรุณาระบุชื่อและรอพิกัด GPS")

# --- TAB 2: ADMIN (ประมวลผลข้อมูลแยกหมวดหมู่) ---
with tab2:
    pwd = st.text_input("รหัสผ่านแอดมิน", type="password")
    if pwd == "9999":
        st.subheader("⚙️ ระบบจัดการและวิเคราะห์ข้อมูลพิกัด")
        df_admin = load_data()
        
        if not df_admin.empty:
            # เลือกรายการที่ 'รอวิเคราะห์' ขึ้นมาแสดงก่อน
            pending_df = df_admin[df_admin['status'] == "รอวิเคราะห์"]
            
            st.write(f"📊 มีรายการรอประมวลผล {len(pending_df)} รายการ")
            
            for idx, row in df_admin.iterrows():
                actual_idx = int(idx) + 2
                status_color = "🔵" if row['status'] == "รอวิเคราะห์" else "🟢"
                
                with st.expander(f"{status_color} {row['place_name']} ({row['timestamp']})"):
                    st.write("--- **ข้อมูลดิบจาก User** ---")
                    st.write(f"📍 **พิกัด:** {row['lat']}, {row['lon']} | 🖼️ **รูปภาพ:** 1:{row['img1']} 2:{row['img2']} 3:{row['img3']}")
                    st.info(f"🗒️ **โน้ตจาก User:** {row['note']}")
                    
                    st.write("--- **แอดมินประมวลผล/แยกหมวดหมู่** ---")
                    col1, col2 = st.columns(2)
                    with col1:
                        # แอดมินกรอกข้อมูลโครงสร้างพื้นที่ตามที่เคยบอก
                        a_gate = st.selectbox("1. เลือกประตู:", ["ประตู 1", "ประตู 2", "ประตู 3", "ประตู 4", "อื่นๆ"], 
                                             index=0, key=f"gate_{idx}")
                        a_main_alley = st.text_input("2. ซอยหลัก/ถนน:", value=row.get('main_alley',''), key=f"main_{idx}")
                    with col2:
                        a_main_side = st.selectbox("3. ฝั่งซอย:", ["ฝั่งใน", "ฝั่งนอก", "ไม่ระบุ"], key=f"side_{idx}")
                        a_sub_alley = st.text_input("4. ซอยย่อย/โครงการ:", value=row.get('sub_alley',''), key=f"sub_{idx}")
                    
                    a_final_note = st.text_area("🗒️ สรุปจุดสังเกต (Admin สรุปใหม่):", value=row['note'], key=f"fnote_{idx}")
                    
                    btn_save, btn_del = st.columns([1,1])
                    if btn_save.button("💾 บันทึกการวิเคราะห์", key=f"save_{idx}", use_container_width=True):
                        ws = get_sheets().worksheet("Sheet1")
                        # อัปเดตข้อมูลที่แอดมินประมวลผลแล้วลงชีตตามคอลัมน์
                        ws.update_cell(actual_idx, 6, "วิเคราะห์แล้ว") # Status
                        ws.update_cell(actual_idx, 5, a_final_note)  # แก้ไข Note สรุป
                        ws.update_cell(actual_idx, 10, a_gate)        # Gate
                        ws.update_cell(actual_idx, 13, a_main_alley)  # Main Alley
                        ws.update_cell(actual_idx, 14, a_main_side)   # Main Side
                        ws.update_cell(actual_idx, 15, a_sub_alley)   # Sub Alley
                        st.success("✅ ประมวลผลข้อมูลเรียบร้อย!")
                        st.rerun()
                        
                    if btn_del.button("🗑️ ลบทิ้ง", key=f"del_{idx}", use_container_width=True):
                        get_sheets().worksheet("Sheet1").delete_rows(actual_idx)
                        st.warning("ลบข้อมูลแล้ว")
                        st.rerun()
        else: st.info("ไม่มีข้อมูลในระบบ")

# --- TAB 3: SMART SEARCH & PREVIEW ---
with tab3:
    st.subheader("🔍 ค้นหาอัจฉริยะ (ดูข้อมูลที่ประมวลผลแล้ว)")
    raw_df = load_data()
    if not raw_df.empty:
        q = st.text_input("🔎 พิมพ์สิ่งที่ต้องการหา (เช่น 'ประตู 4 ซอย 2 ร้านสีฟ้า'):")
        results = smart_search(raw_df, q)
        
        # แสดงแผนที่อาณาเขตพร้อมพิกัด
        view_state = pdk.ViewState(latitude=results['lat'].mean() if not results.empty else DEFAULT_LAT, 
                                   longitude=results['lon'].mean() if not results.empty else DEFAULT_LON, zoom=14)
        st.pydeck_chart(pdk.Deck(
            map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
            initial_view_state=view_state,
            layers=[pdk.Layer("ScatterplotLayer", results, get_position='[lon, lat]', get_color='[255, 75, 75, 200]', get_radius=40, pickable=True)],
            tooltip={"html": "<b>{place_name}</b><br/>ประตู: {gate}<br/>ซอย: {main_alley}<br/>ฝั่ง: {main_side}"}
        ))
        
        for _, r in results.iterrows():
            with st.expander(f"📌 {r['place_name']} - {r['gate']}"):
                col_info, col_map = st.columns(2)
                with col_info:
                    st.markdown(f"**🚪 ประตู:** {r['gate']} | **🛣️ ซอยหลัก:** {r['main_alley']}")
                    st.markdown(f"**🌍 ฝั่ง:** {r['main_side']} | **🏘️ ซอยย่อย:** {r['sub_alley']}")
                    st.markdown(f"**📝 สรุปโดยแอดมิน:** {r['note']}")
                    st.link_button("🚗 นำทางด้วย Google Maps", f"https://www.google.com/maps?q={r['lat']},{r['lon']}")
                with col_map:
                    st.pydeck_chart(pdk.Deck(
                        map_style="https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
                        initial_view_state=pdk.ViewState(latitude=r['lat'], longitude=r['lon'], zoom=18),
                        layers=[pdk.Layer("ScatterplotLayer", pd.DataFrame([r]), get_position='[lon, lat]', get_color='[255,0,0]', get_radius=10)]
                    ))
