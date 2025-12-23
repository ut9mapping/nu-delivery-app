import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. ตั้งค่าระบบและการเชื่อมต่อ ---
st.set_page_config(page_title="NU Delivery: Smart System", layout="wide")

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
        text_to_search = f"{row['place_name']} {row['note']} {row['gate']} {row['main_alley']}".lower()
        for kw in keywords:
            if kw in text_to_search:
                score += 1
                if kw in str(row['place_name']).lower(): score += 2 # ให้คะแนนชื่อสถานที่มากพิเศษ
        return score
    
    df['relevance'] = df.apply(calculate_score, axis=1)
    return df[df['relevance'] > 0].sort_values(by='relevance', ascending=False)

# --- 3. ส่วนหน้าจอแสดงผล ---
st.title("🛵 NU Delivery Smart Pro")

tab1, tab2, tab3 = st.tabs(["📌 บันทึกหน้างาน", "⚙️ จัดการข้อมูล (Admin)", "🔍 ค้นหาอัจฉริยะ"])

# --- TAB 1: USER (ช่องใส่รูปครบ) ---
with tab1:
    st.subheader("📝 บันทึกพิกัดและรูปถ่าย")
    loc = streamlit_geolocation()
    lat, lon = loc.get('latitude'), loc.get('longitude')
    
    if lat: st.success(f"📍 GPS Lock: {lat}, {lon}")
    else: st.warning("📡 กำลังค้นหาพิกัด... โปรดอนุญาตสิทธิ์ตำแหน่ง")

    p_name = st.text_input("🏠 ชื่อสถานที่/โครงการ")
    note = st.text_area("🗒️ จุดสังเกต")
    
    st.write("🖼️ รูปถ่ายจุดพิกัด")
    c1, c2, c3 = st.columns(3)
    i1 = c1.file_uploader("รูป 1", type=['jpg','png'], key="i1")
    i2 = c2.file_uploader("รูป 2", type=['jpg','png'], key="i2")
    i3 = c3.file_uploader("รูป 3", type=['jpg','png'], key="i3")

    if st.button("🚀 บันทึกข้อมูล", use_container_width=True, type="primary"):
        if lat and p_name:
            ws = get_sheets().worksheet("Sheet1")
            imgs = ["Yes" if i else "No" for i in [i1, i2, i3]]
            new_row = [datetime.now().strftime("%Y-%m-%d %H:%M"), lat, lon, p_name, note, "รอวิเคราะห์"] + imgs + [""]*7
            ws.insert_row(new_row, index=2)
            st.success("✅ บันทึกเรียบร้อย!")
        else: st.error("⚠️ ข้อมูลไม่ครบ")

# --- TAB 2: ADMIN (ปุ่มลบ/แก้ไข รายตัว) ---
with tab2:
    pwd = st.text_input("รหัสผ่านแอดมิน", type="password")
    if pwd == "9999":
        st.info("🔓 โหมดจัดการข้อมูล (CRUD Mode)")
        df_admin = load_data()
        
        for idx, row in df_admin.iterrows():
            actual_idx = int(idx) + 2
            with st.expander(f"📍 {row['place_name']} (แถวที่ {actual_idx})"):
                col_edit, col_del = st.columns([4, 1])
                
                with col_edit:
                    e_note = st.text_input("แก้ไขหมายเหตุ", value=row['note'], key=f"n_{idx}")
                    e_gate = st.text_input("ประตู", value=row.get('gate', ''), key=f"g_{idx}")
                    if st.button("💾 บันทึกการแก้ไข", key=f"save_{idx}"):
                        ws = get_sheets().worksheet("Sheet1")
                        ws.update_cell(actual_idx, 5, e_note)
                        ws.update_cell(actual_idx, 10, e_gate)
                        st.success("อัปเดตแล้ว!")
                        st.rerun()
                
                with col_del:
                    st.write("---")
                    if st.button("🗑️ ลบพิกัด", key=f"del_{idx}"):
                        get_sheets().worksheet("Sheet1").delete_rows(actual_idx)
                        st.warning("ลบข้อมูลแล้ว")
                        st.rerun()

# --- TAB 3: SMART SEARCH & INTERACTIVE MAP ---
with tab3:
    st.subheader("🔍 ระบบค้นหาอัจฉริยะ")
    raw_df = load_data()
    
    if not raw_df.empty:
        search_query = st.text_input("🔎 พิมพ์อะไรก็ได้ (เช่น 'ประตู 4 ร้านสีแดง ซอย 2'):")
        results = smart_search(raw_df, search_query)
        
        # แสดงแผนที่อาณาเขตพร้อม Hover Tooltip
        st.write("🌍 **อาณาเขตข้อมูล (ชี้ที่จุดเพื่อดูรายละเอียด)**")
        view_state = pdk.ViewState(latitude=results['lat'].mean(), longitude=results['lon'].mean(), zoom=14)
        
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
                "html": """
                <div style='background: white; color: black; padding: 10px; border-radius: 5px;'>
                    <b>🏠 สถานที่:</b> {place_name} <br/>
                    <b>🚪 ประตู:</b> {gate} <br/>
                    <b>🗒️ หมายเหตุ:</b> {note}
                </div>
                """
            }
        ))
        
        

        # แสดงรายการที่ค้นหาพบ
        st.write(f"พบข้อมูลที่เกี่ยวข้อง {len(results)} รายการ")
        for _, r in results.iterrows():
            with st.expander(f"📌 {r['place_name']} (ความเกี่ยวข้อง: {r.get('relevance', 0)})"):
                c_a, c_b = st.columns(2)
                with c_a:
                    st.write(f"**ประตู:** {r['gate']} | **หมายเหตุ:** {r['note']}")
                    st.link_button("🚗 นำทาง", f"https://www.google.com/maps?q={r['lat']},{r['lon']}")
                with c_b:
                    # ภาพจำลองดาวเทียม
                    st.pydeck_chart(pdk.Deck(
                        map_style="https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
                        initial_view_state=pdk.ViewState(latitude=r['lat'], longitude=r['lon'], zoom=18),
                        layers=[pdk.Layer("ScatterplotLayer", pd.DataFrame([r]), get_position='[lon, lat]', get_color='[255,0,0]', get_radius=10)]
                    ))
