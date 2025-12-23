import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk
import difflib  # สำหรับแก้คำพิมพ์ผิด (Fuzzy Matching)
import re      # สำหรับตรวจจับตัวเลข/เลขที่บ้าน

# --- 1. ตั้งค่าพื้นฐานและเชื่อมต่อฐานข้อมูล ---
st.set_page_config(page_title="NU Delivery: Super AI Pro", layout="wide")

# พิกัดกลาง (ม.นเรศวร) กรณีเริ่มระบบ
DEFAULT_LAT, DEFAULT_LON = 16.7469, 100.1914

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])
    except Exception as e:
        st.error(f"เชื่อมต่อ Google Sheets ไม่ได้: {e}")
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

# --- 2. 🧠 SUPER AI SEARCH LOGIC (ฉลาด เข้าใจคำถาม และคำผิด) ---
def super_ai_search(df, query):
    if not query: 
        return df, "สวัสดีครับ! ผมคือ AI ผู้ช่วยหาพิกัด พิมพ์ถามได้เลย เช่น 'บ้านเลขที่ 55' หรือ 'หอพักแถวประตู 4'"
    
    q = query.lower().strip()
    digits = re.findall(r'\d+', q) # สกัดตัวเลขออกมาสำหรับหาเลขที่บ้าน
    
    def get_score(row):
        score = 0
        name = str(row['place_name']).lower()
        note = str(row['note']).lower()
        gate = str(row['gate']).lower()
        alley = str(row['main_alley']).lower()
        full_text = f"{name} {note} {gate} {alley}".lower()
        
        # 1. ค้นหาแบบตรงตัว
        if q in full_text: score += 10
        
        # 2. ค้นหาเลขที่บ้าน (ถ้ามีตัวเลขตรงกัน ให้คะแนนพิเศษ)
        for num in digits:
            if num in full_text: score += 15
            
        # 3. Fuzzy Match (แก้ปัญหาพิมพ์ผิด)
        # ตรวจความคล้ายกับชื่อสถานที่
        similarity = difflib.SequenceMatcher(None, q, name).ratio()
        if similarity > 0.5: score += (similarity * 10)
        
        # 4. ตรวจสอบบริบท (ประตู/ซอย)
        if "ประตู" in q and gate in q: score += 5
        
        return score

    temp_df = df.copy()
    temp_df['ai_score'] = temp_df.apply(get_score, axis=1)
    results = temp_df[temp_df['ai_score'] > 2].sort_values(by='ai_score', ascending=False)
    
    # AI ตอบกลับแบบฉลาด
    if not results.empty:
        top_match = results.iloc[0]['place_name']
        if results.iloc[0]['ai_score'] > 15:
            msg = f"✅ ผมเจอพิกัดที่แม่นยำที่สุดคือ **{top_match}** ครับ!"
        else:
            msg = f"🤔 ผมหาไม่เจอแบบเป๊ะๆ แต่คิดว่าคุณน่าจะหมายถึง **{top_match}** หรือเปล่าครับ?"
    else:
        msg = "😅 ขออภัยครับ ผมยังไม่เจอสถานที่ที่ใกล้เคียงกับคำค้นหานี้เลย"
        
    return results, msg

# --- 3. หน้าจอการใช้งาน ---
st.title("🧠 NU Delivery: Super AI & Admin Control")

tab1, tab2, tab3 = st.tabs(["📌 บันทึกหน้างาน (User)", "⚙️ ประมวลผลข้อมูล (Admin)", "🔍 ค้นหาอัจฉริยะ (AI)"])

# --- TAB 1: USER (บันทึกพิกัด + รูป 3 ช่อง) ---
with tab1:
    st.subheader("📝 บันทึกข้อมูลพิกัดและรูปถ่าย")
    loc = streamlit_geolocation()
    lat, lon = loc.get('latitude'), loc.get('longitude')
    
    if lat: st.success(f"📍 พิกัดพร้อม: {lat}, {lon}")
    else: st.warning("📡 กำลังรอพิกัด GPS... (โปรดกดยอมรับสิทธิ์ที่เบราว์เซอร์)")

    p_name = st.text_input("🏠 ชื่อสถานที่ / ตึกแถว / บ้านเลขที่")
    note = st.text_area("🗒️ จุดสังเกตเพิ่มเติม (User Note)")
    
    st.write("🖼️ อัปโหลดรูปภาพประกอบ (3 รูป)")
    c1, c2, c3 = st.columns(3)
    img1 = c1.file_uploader("รูป 1", type=['jpg','png'], key="img1")
    img2 = c2.file_uploader("รูป 2", type=['jpg','png'], key="img2")
    img3 = c3.file_uploader("รูป 3", type=['jpg','png'], key="img3")

    if st.button("🚀 ส่งข้อมูลให้แอดมิน", use_container_width=True, type="primary"):
        if lat and p_name:
            ws = get_sheets().worksheet("Sheet1")
            has_imgs = ["Yes" if i else "No" for i in [img1, img2, img3]]
            new_row = [datetime.now().strftime("%Y-%m-%d %H:%M"), lat, lon, p_name, note, "รอวิเคราะห์"] + has_imgs + [""]*7
            ws.insert_row(new_row, index=2)
            st.balloons()
            st.success("✅ บันทึกสำเร็จ! ข้อมูลถูกส่งไปรอการประมวลผลแล้ว")
        else: st.error("⚠️ ข้อมูลไม่ครบ")

# --- TAB 2: ADMIN (ประมวลผล / แก้ไข / ลบ) ---
with tab2:
    pwd = st.text_input("รหัสผ่านแอดมิน", type="password")
    if pwd == "9999":
        st.subheader("🛠️ ระบบจัดการข้อมูล (ADMIN CRUD)")
        df_admin = load_data()
        
        if not df_admin.empty:
            for idx, row in df_admin.iterrows():
                actual_idx = int(idx) + 2
                status_icon = "🔵" if row['status'] == "รอวิเคราะห์" else "🟢"
                
                with st.expander(f"{status_icon} {row['place_name']} ({row['timestamp']})"):
                    st.write(f"📍 **พิกัด:** {row['lat']}, {row['lon']} | 🖼️ **รูปที่มี:** 1:{row['img1']} 2:{row['img2']} 3:{row['img3']}")
                    st.info(f"💬 โน้ตจาก User: {row['note']}")
                    
                    st.write("**📝 แอดมินวิเคราะห์ข้อมูล:**")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        new_gate = st.selectbox("ประตู:", ["ประตู 1", "ประตู 2", "ประตู 3", "ประตู 4", "อื่นๆ"], 
                                                index=0, key=f"g_{idx}")
                        new_alley = st.text_input("ชื่อซอย/ถนนหลัก:", value=row.get('main_alley',''), key=f"al_{idx}")
                    with col_b:
                        new_side = st.selectbox("ฝั่ง:", ["ฝั่งใน", "ฝั่งนอก", "อื่นๆ"], key=f"s_{idx}")
                        new_status = st.selectbox("สถานะ:", ["รอวิเคราะห์", "วิเคราะห์แล้ว", "ยกเลิก"], key=f"st_{idx}")
                    
                    new_note = st.text_area("สรุปจุดสังเกตใหม่ (ฉบับแอดมิน):", value=row['note'], key=f"nt_{idx}")
                    
                    btn_save, btn_del = st.columns(2)
                    if btn_save.button("💾 บันทึกการแก้ไข", key=f"sv_{idx}", use_container_width=True):
                        ws = get_sheets().worksheet("Sheet1")
                        ws.update_cell(actual_row_idx, 5, new_note)
                        ws.update_cell(actual_row_idx, 6, new_status)
                        ws.update_cell(actual_row_idx, 10, new_gate)
                        ws.update_cell(actual_row_idx, 13, new_alley)
                        ws.update_cell(actual_row_idx, 14, new_side)
                        st.success("อัปเดตเรียบร้อย!")
                        st.rerun()
                        
                    if btn_del.button("🗑️ ลบพิกัดถาวร", key=f"dl_{idx}", use_container_width=True):
                        get_sheets().worksheet("Sheet1").delete_rows(actual_idx)
                        st.warning("ลบข้อมูลแล้ว")
                        st.rerun()
        else: st.info("ไม่มีข้อมูล")

# --- TAB 3: AI ASSISTANT (Hover Tooltip + Fuzzy Search) ---
with tab3:
    st.subheader("🔍 ค้นหาอัจฉริยะด้วย AI")
    query = st.text_input("💬 พิมพ์ถาม AI:", placeholder="เช่น 'ตึกแถวเลขที่ 12/3 ประตู 4'")
    
    data_all = load_data()
    if not data_all.empty:
        results, ai_msg = super_ai_search(data_all, query)
        
        with st.chat_message("assistant"):
            st.write(ai_msg)
            
        if not results.empty:
            # แผนที่ภาพรวมพร้อม Hover Tooltip
            st.write("🌍 **อาณาเขตพื้นที่ (เอาเมาส์ชี้เพื่อดูรายละเอียด)**")
            
            view_lat = results['lat'].mean()
            view_lon = results['lon'].mean()
            
            st.pydeck_chart(pdk.Deck(
                map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
                initial_view_state=pdk.ViewState(latitude=view_lat, longitude=view_lon, zoom=15),
                layers=[pdk.Layer(
                    "ScatterplotLayer",
                    results,
                    get_position='[lon, lat]',
                    get_color='[255, 75, 75, 180]',
                    get_radius=40,
                    pickable=True
                )],
                tooltip={
                    "html": "<b>{place_name}</b><br/>ประตู: {gate}<br/>ซอย: {main_alley}<br/>หมายเหตุ: {note}",
                    "style": {"backgroundColor": "white", "color": "black", "fontSize": "14px"}
                }
            ))
            
            # รายละเอียดพร้อมภาพจำลองดาวเทียม
            for _, r in results.iterrows():
                with st.expander(f"📍 {r['place_name']} - {r['gate']}"):
                    cola, colb = st.columns(2)
                    with cola:
                        st.markdown(f"**🚪 ประตู:** {r['gate']} | **🛣️ ถนน:** {r['main_alley']}")
                        st.markdown(f"**📝 สรุป:** {r['note']}")
                        st.link_button("🚗 นำทางด้วย Google Maps", f"https://www.google.com/maps?q={r['lat']},{r['lon']}")
                    with colb:
                        st.pydeck_chart(pdk.Deck(
                            map_style="https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
                            initial_view_state=pdk.ViewState(latitude=r['lat'], longitude=r['lon'], zoom=18),
                            layers=[pdk.Layer("ScatterplotLayer", pd.DataFrame([r]), get_position='[lon, lat]', get_color='[255,0,0]', get_radius=10)]
                        ))
