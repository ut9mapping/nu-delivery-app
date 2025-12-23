import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

st.set_page_config(page_title="NU Delivery Fixed", layout="wide")

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])
    except Exception as e:
        st.error(f"❌ เชื่อมต่อ Google Sheets ไม่ได้: {e}")
        return None

@st.cache_data(ttl=2)
def load_data_robust():
    sh = get_sheets()
    if not sh: return pd.DataFrame()
    try:
        ws = sh.worksheet("Sheet1")
        all_values = ws.get_all_values()
        
        if len(all_values) > 1:
            headers = all_values[0]
            data = all_values[1:]
            
            # --- แก้ปัญหาชื่อคอลัมน์ซ้ำ (Deduplicate) ---
            clean_headers = []
            for i, h in enumerate(headers):
                h = str(h).strip().lower()
                if h == "" or h in clean_headers:
                    clean_headers.append(f"{h if h != '' else 'empty'}_{i}")
                else:
                    clean_headers.append(h)
            
            df = pd.DataFrame(data, columns=clean_headers)
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading: {e}")
        return pd.DataFrame()

# --- ส่วน UI ---
st.title("🛵 ระบบจัดการพิกัด (Fixed Duplicate Error)")

tab1, tab2 = st.tabs(["📌 บันทึกข้อมูล", "🗺️ แผนที่และตาราง"])

with tab1:
    location = streamlit_geolocation()
    lat, lon = location.get('latitude'), location.get('longitude')
    p_name = st.text_input("🏠 ชื่อสถานที่ / บ้านเลขที่")
    
    if st.button("💾 บันทึกข้อมูล", type="primary"):
        if lat and p_name:
            try:
                sh = get_sheets()
                ws = sh.worksheet("Sheet1")
                # บันทึกข้อมูล 10 คอลัมน์ (A-J)
                new_data = [datetime.now().strftime("%Y-%m-%d %H:%M"), "-", lat, lon, p_name, "", "", "", "", "Complete"]
                ws.insert_row(new_data, index=2)
                st.success("✅ บันทึกสำเร็จ!")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"บันทึกไม่สำเร็จ: {e}")
        else:
            st.warning("⚠️ กรุณารอพิกัดและกรอกชื่อสถานที่")

with tab2:
    if st.button("🔄 ดึงข้อมูลใหม่"):
        st.cache_data.clear()
        st.rerun()

    df = load_data_robust()

    if not df.empty:
        # แสดงตารางเพื่อให้เห็นว่าดึงมาได้จริง
        st.write("📋 ข้อมูลล่าสุดในชีต:")
        st.dataframe(df, use_container_width=True)

        # เตรียมข้อมูลสำหรับแผนที่ (ตรวจสอบคอลัมน์ lat/lon)
        # หมายเหตุ: คอลัมน์อาจถูกเปลี่ยนชื่อเป็น lat_2 ถ้าในชีตมี lat ซ้ำ
        lat_col = 'lat' if 'lat' in df.columns else [c for c in df.columns if 'lat' in c][0]
        lon_col = 'lon' if 'lon' in df.columns else [c for c in df.columns if 'lon' in c][0]

        df[lat_col] = pd.to_numeric(df[lat_col], errors='coerce')
        df[lon_col] = pd.to_numeric(df[lon_col], errors='coerce')
        df_map = df.dropna(subset=[lat_col, lon_col])

        if not df_map.empty:
            st.write("📍 พิกัดบนแผนที่:")
            st.pydeck_chart(pdk.Deck(
                initial_view_state=pdk.ViewState(latitude=df_map[lat_col].iloc[0], longitude=df_map[lon_col].iloc[0], zoom=13),
                layers=[pdk.Layer("ScatterplotLayer", df_map, get_position=f'[{lon_col}, {lat_col}]', get_color='[255, 0, 0, 160]', get_radius=50)],
            ))
    else:
        st.info("ยังไม่มีข้อมูลในระบบ")
