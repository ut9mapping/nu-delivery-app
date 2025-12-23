import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. การตั้งค่าระบบและการเชื่อมต่อ ---
st.set_page_config(page_title="NU Delivery: Smart AI System", layout="wide")

# พิกัดเริ่มต้นกรณีไม่มีข้อมูล (ม.นเรศวร)
DEFAULT_LAT, DEFAULT_LON = 16.7469, 100.1914

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])
    except Exception as e:
        st.error(f"การเชื่อมต่อ Google Sheets ผิดพลาด: {e}")
        return None

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

# --- 2. AI Logic: ระบบคิดวิเคราะห์และค้นหาอัจฉริยะ ---
def ai_brain_search(df, user_query):
    if not user_query: return df, "สวัสดีครับ! ผมเป็นผู้ช่วย AI วันนี้อยากให้ช่วยหาพิกัดแถวไหนดีครับ?"
    
    q = user_query.lower()
    is_urgent = any(word in q for word in ["ด่วน", "ยังไม่ตรวจ", "รอวิเคราะห์", "ใหม่"])
    
    def calculate_relevance(row):
        score = 0
        # รวบรวมข้อความทั้งหมดที่เกี่ยวข้องมาวิเคราะห์
        search_blob = f"{row['place_name']} {row['note']} {row['gate']} {row['main_alley']} {row['sub_alley']}".lower()
        
        # ค้นหาคำสำคัญ
        for word in q.split():
            if word in search_blob:
                score += 2
                if word in str(row['place_name']).lower(): score += 3 # ให้คะแนนชื่อสถานที่มากที่สุด
        
        # วิเคราะห์ Intent: ถ้าถามหาความใหม่หรือรายการที่ยังไม่ประมวลผล
        if is_urgent and row['status'] == "รอวิเคราะห์":
            score += 10
            
        # วิเคราะห์เลขประตู
        for i in range(1, 6):
            if f"ประตู {i}" in q and f"ประตู {i}" in str(row['gate']):
                score += 7
                
        return score

    temp_df = df.copy()
    temp_df['ai_score'] = temp_df.apply(calculate_relevance, axis=1)
    results = temp_df[temp_df['ai_score'] > 0].sort_values(by='ai_score', ascending=False)
    
    # สร้างคำตอบแบบ AI
    if not results.empty:
        top = results.iloc[0]
        msg = f"🤖 วิเคราะห์แล้วครับ! พบสถานที่ใกล้เคียง {len(results)} แห่ง แนะนำให้ดูที่ '{top['place_name']}' เป็นอันดับแรก เพราะตรงกับที่คุณค้นหาที่สุดครับ"
    else:
        msg = "🔍 ผมพยายามหาแล้วแต่ยังไม่เจอข้อมูลที่ตรงเป๊ะ ลองพิมพ์ชื่อประตูหรือลักษณะอาคารดูอีกครั้งนะครับ"
        
    return results, msg

# --- 3. ส่วนการแสดงผล (UI) ---
st.title("🧠 NU Delivery: Intelligent Mapping")

tab1, tab2, tab3 = st.tabs(["📌 บันทึกหน้างาน (User)", "⚙️ ประมวลผลข้อมูล (Admin)", "🔍 ผู้ช่วย AI ค้นหา"])

# --- TAB 1: บันทึกข้อมูล (User) ---
with tab1:
    st.subheader("📝 ส่งข้อมูลพิกัดใหม่")
    col_gps, col_form = st.columns([1, 2])
    
    with col_gps:
        st.write("🛰️ ตรวจสอบพิกัดปัจจุบัน")
        location = streamlit_geolocation()
        lat, lon = location.get('latitude'), location.get('longitude')
        if lat:
            st.success(f"Locked: {lat:.5f}, {lon:.5f}")
        else:
            st.warning("📡 กรุณากดอนุญาตสิทธิ์ GPS")

    with col_form:
        p_name = st.text_input("🏠 ชื่อสถานที่/ตึกแถว")
        note = st.text_area("🗒️ จุดสังเกต (User Note)")
        
        st.write("🖼️ อัปโหลดรูปภาพ (สูงสุด 3 รูป)")
        c1, c2, c3 = st.columns(3)
        img1 = c1.file_uploader("รูป 1", type=['jpg','png'], key="u1")
        img2 = c2.file_uploader("รูป 2", type=['jpg','png'], key="u2")
        img3 = c3.file_uploader("รูป 3", type=['jpg','png'], key="u3")

        if st.button("🚀 บันทึกข้อมูลดิบ", use_container_width=True, type="primary"):
            if lat and p_name:
                ws = get_sheets().worksheet("Sheet1")
                imgs = ["Yes" if i else "No" for i in [img1, img2, img3]]
                # ลำดับ: Timestamp, lat, lon, Name, Note, Status, img1, img2, img3, Gate, Alley, Side, SubAlley...
                new_row = [datetime.now().strftime("%Y-%m-%d %H:%M"), lat, lon, p_name, note, "รอวิเคราะห์"] + imgs + [""]*7
                ws.insert_row(new_row, index=2)
                st.balloons()
                st.success("✅ ส่งข้อมูลให้แอดมินแล้ว!")
            else: st.error("⚠️ ข้อมูลไม่ครบหรือ GPS ไม่ทำงาน")

# --- TAB 2: จัดการและประมวลผลข้อมูล (Admin) ---
with tab2:
    pwd = st.text_input("รหัสผ่านแอดมิน", type="password")
    if pwd == "9999":
        st.subheader("🛠️ โต๊ะทำงานแอดมิน: วิเคราะห์และแยกหมวดหมู่")
        df_admin = load_data()
        
        if not df_admin.empty:
            # จัดเรียงเอา 'รอวิเคราะห์' ขึ้นก่อน
            df_admin = df_admin.sort_values(by="status", ascending=False)
            
            for idx, row in df_admin.iterrows():
                actual_row = int(idx) + 2
                status_icon = "🆕" if row['status'] == "รอวิเคราะห์" else "✅"
                
                with st.expander(f"{status_icon} {row['place_name']} - {row['timestamp']}"):
                    st.write("**📥 ข้อมูลจากหน้างาน:**")
                    st.caption(f"📍 {row['lat']}, {row['lon']} | 🖼️ รูปภาพที่มี: {row['img1']}, {row['img2']}, {row['img3']}")
                    st.info(f"💬 โน้ตจาก User: {row['note']}")
                    
                    st.write("**🧠 การประมวลผลของแอดมิน:**")
                    c_a, c_b, c_c = st.columns(3)
                    with c_a:
                        a_gate = st.selectbox("ระบุประตูถนน:", ["ประตู 1", "ประตู 2", "ประตู 3", "ประตู 4", "อื่นๆ"], key=f"gt_{idx}")
                    with c_b:
                        a_alley = st.text_input("ชื่อซอย/ถนนหลัก:", value=row.get('main_alley',''), key=f"al_{idx}")
                    with c_c:
                        a_side = st.selectbox("ฝั่งซอย:", ["ฝั่งใน", "ฝั่งนอก", "อื่นๆ"], key=f"sd_{idx}")
                    
                    a_note = st.text_area("สรุปจุดสังเกตใหม่ (ฉบับแอดมิน):", value=row['note'], key=f"nt_{idx}")
                    
                    col_save, col_del = st.columns(2)
                    if col_save.button("💾 บันทึกการวิเคราะห์", key=f"sv_{idx}", use_container_width=True):
                        ws = get_sheets().worksheet("Sheet1")
                        ws.update_cell(actual_row, 5, a_note)     # Note
                        ws.update_cell(actual_row, 6, "วิเคราะห์แล้ว") # Status
                        ws.update_cell(actual_row, 10, a_gate)    # Gate
                        ws.update_cell(actual_row, 13, a_alley)   # Main Alley
                        ws.update_cell(actual_row, 14, a_side)    # Main Side
                        st.success("ประมวลผลสำเร็จ!")
                        st.rerun()
                        
                    if col_del.button("🗑️ ลบพิกัดนี้", key=f"dl_{idx}", use_container_width=True):
                        get_sheets().worksheet("Sheet1").delete_rows(actual_row)
                        st.warning("ลบข้อมูลแล้ว")
                        st.rerun()
        else: st.info("ไม่มีข้อมูลให้ประมวลผล")

# --- TAB 3: ผู้ช่วย AI และแผนที่ (Smart Assistant) ---
with tab3:
    st.subheader("🤝 ผู้ช่วย AI ค้นหาพิกัด")
    search_input = st.text_input("💬 พิมพ์คุยกับ AI:", placeholder="เช่น หาตึกแถวใกล้ประตู 4 ที่ยังไม่ได้วิเคราะห์...")
    
    full_df = load_data()
    if not full_df.empty:
        results, ai_response = ai_brain_search(full_df, search_input)
        
        # กล่องโต้ตอบ AI
        with st.chat_message("assistant"):
            st.write(ai_response)
        
        # แสดงแผนที่อาณาเขตรวม (Hover Tooltip)
        if not results.empty:
            st.write("🌍 **แผนที่อาณาเขต (ชี้ที่จุดเพื่อดูรายละเอียด)**")
            view_lat = results['lat'].mean() if not results.empty else DEFAULT_LAT
            view_lon = results['lon'].mean() if not results.empty else DEFAULT_LON
            
            st.pydeck_chart(pdk.Deck(
                map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
                initial_view_state=pdk.ViewState(latitude=view_lat, longitude=view_lon, zoom=14),
                layers=[pdk.Layer(
                    "ScatterplotLayer",
                    results,
                    get_position='[lon, lat]',
                    get_color='[255, 75, 75, 180]',
                    get_radius=40,
                    pickable=True
                )],
                tooltip={
                    "html": "<b>สถานที่:</b> {place_name}<br/><b>ประตู:</b> {gate}<br/><b>ซอย:</b> {main_alley}<br/><b>สรุป:</b> {note}",
                    "style": {"backgroundColor": "white", "color": "black", "fontSize": "14px"}
                }
            ))
            
            

            # รายละเอียดรายบุคคล
            st.divider()
            for _, r in results.iterrows():
                with st.expander(f"📌 {r['place_name']} - {r['gate']}"):
                    cl1, cl2 = st.columns(2)
                    with cl1:
                        st.markdown(f"**🚪 ประตู:** {r['gate']} | **🛣️ ซอย:** {r['main_alley']}")
                        st.markdown(f"**📝 สรุปโดยแอดมิน:** {r['note']}")
                        st.link_button("🚗 นำทางด้วย Google Maps", f"https://www.google.com/maps?q={r['lat']},{r['lon']}")
                    with cl2:
                        # แผนที่ดาวเทียมซูมรายจุด
                        st.pydeck_chart(pdk.Deck(
                            map_style="https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
                            initial_view_state=pdk.ViewState(latitude=r['lat'], longitude=r['lon'], zoom=18),
                            layers=[pdk.Layer("ScatterplotLayer", pd.DataFrame([r]), get_position='[lon, lat]', get_color='[255,0,0]', get_radius=10)]
                        ))
    else: st.info("ยังไม่มีข้อมูลพิกัดในระบบ")
