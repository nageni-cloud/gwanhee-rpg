import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# ==========================================
# 1. 구글 시트 연동 (클라우드 호환 V15)
# ==========================================
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
SHEET_NAME = "Gwanhee_Data" 

@st.cache_resource
def connect_to_sheet():
    # Streamlit Cloud의 Secrets에서 키를 찾음
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
    # 로컬 파일에서 키를 찾음 (테스트용)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", SCOPE)
        
    client = gspread.authorize(creds)
    sh = client.open(SHEET_NAME) # 시트 열기
    
    # 탭 확인 및 생성
    try: ws_status = sh.worksheet("Status")
    except: 
        ws_status = sh.add_worksheet("Status", 10, 5)
        ws_status.append_row(["Level", "Current_XP", "Total_XP"]); ws_status.append_row([1, 0, 0])
    try: ws_logs = sh.worksheet("Logs")
    except: 
        ws_logs = sh.add_worksheet("Logs", 1000, 5)
        ws_logs.append_row(["Time", "Action", "XP", "Value"])
    return ws_status, ws_logs

try:
    ws_status, ws_logs = connect_to_sheet()
except Exception as e:
    st.error(f"❌ 연결 실패: {e}")
    st.stop()

# ==========================================
# 2. 데이터 관리
# ==========================================
def load_data():
    status = ws_status.get_all_records()
    if not status: ws_status.append_row([1, 0, 0]); return 1, 0, 0, []
    cur = status[0]
    # Logs 역순 로드
    logs = ws_logs.get_all_records(); logs.reverse()
    return int(cur["Level"]), int(cur["Current_XP"]), int(cur["Total_XP"]), logs

level, current_xp, total_xp, logs = load_data()
next_level_xp = level * 100 

# ==========================================
# 3. 티어 로직
# ==========================================
TIER_MAP = [
    {"name": "Iron", "start": 1, "color": "#717171", "percent": "상위 100%"},
    {"name": "Bronze", "start": 13, "color": "#8C7853", "percent": "상위 80%"},
    {"name": "Silver", "start": 25, "color": "#808B96", "percent": "상위 60%"},
    {"name": "Gold", "start": 37, "color": "#D4AC0D", "percent": "상위 40%"},
    {"name": "Platinum", "start": 49, "color": "#27AE60", "percent": "상위 20%"},
    {"name": "Emerald", "start": 61, "color": "#138D75", "percent": "상위 10%"},
    {"name": "Diamond", "start": 73, "color": "#2980B9", "percent": "상위 5%"},
    {"name": "Master", "start": 85, "color": "#8E44AD", "percent": "상위 1%"},
    {"name": "GrandMaster", "start": 97, "color": "#C0392B", "percent": "상위 0.1%"},
    {"name": "Challenger", "start": 109, "color": "#F1C40F", "percent": "상위 0.01%"}
]
def get_tier(lv):
    for i in range(len(TIER_MAP)-1, -1, -1):
        t = TIER_MAP[i]
        if lv >= t["start"]:
            if t["name"] == "Challenger": return t["name"], "", t["color"]
            div = 4 - ((lv - t["start"]) // 3)
            return t["name"], str(max(1, div)), t["color"]
    return "Iron", "4", "#717171"
cur_n, cur_d, cur_c = get_tier(level)

# ==========================================
# 4. 액션
# ==========================================
def update_server(l, c, t):
    ws_status.update_cell(2, 1, l); ws_status.update_cell(2, 2, c); ws_status.update_cell(2, 3, t)

def add_xp(amt, act, val):
    global current_xp, total_xp, level
    add = int(amt); current_xp += add; total_xp += add
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    lvl_up = False
    if current_xp >= (level * 100):
        current_xp -= (level * 100); level += 1; lvl_up = True
    
    update_server(level, current_xp, total_xp)
    ws_logs.append_row([ts, act, add, val])
    
    if lvl_up: st.toast(f"🎉 레벨 업! Lv.{level}", icon="🔥"); st.balloons()
    else: st.toast("✅ 저장 완료!", icon="☁️")
    st.rerun()

def undo():
    if not logs: st.toast("기록 없음", icon="🚫"); return
    ws_logs.delete_rows(len(ws_logs.get_all_values()))
    
    last = logs[0]; xp_back = int(last["XP"])
    global current_xp, total_xp, level
    total_xp -= xp_back; current_xp -= xp_back
    while current_xp < 0:
        if level > 1: level -= 1; current_xp += (level * 100)
        else: current_xp = 0; break
    update_server(level, current_xp, total_xp)
    st.toast("↩️ 취소 완료", icon="🗑️"); st.rerun()

# ==========================================
# 5. UI
# ==========================================
st.set_page_config(page_title="관희의 성장 RPG", page_icon="☁️", layout="centered")
st.title("🔥 관희의 성장 RPG (Cloud)")
st.markdown(f"<h2 style='color:{cur_c}; margin-top:-15px;'>{cur_n} {cur_d} <span style='color:#555;font-size:24px;'>(Lv.{level})</span></h2>", unsafe_allow_html=True)

with st.expander("ℹ️ 티어 정보"):
    st.table(pd.DataFrame(TIER_MAP)[['name', 'percent']])

today = datetime.now().date(); d_day = (today - datetime(2026,1,1).date()).days
d_str = f"D{d_day}" if d_day < 0 else f"Day +{d_day+1}"
st.markdown(f"<div style='text-align:center; color:#666;'>📅 {today} | 🚀 {d_str}</div><hr>", unsafe_allow_html=True)

r_stat = sum([x['Value'] for x in logs if '달리기' in x['Action']])
p_stat = sum([x['Value'] for x in logs if '팔굽혀펴기' in x['Action']])
s_stat = sum([x['Value'] for x in logs if '자기계발' in x['Action']])
c1,c2,c3 = st.columns(3)
c1.metric("🏃 달리기", f"{r_stat:.1f} km"); c2.metric("💪 푸쉬업", f"{int(p_stat)} 개"); c3.metric("🧠 자기계발", f"{s_stat/60:.1f} 시간")

pg = min(current_xp/next_level_xp, 1.0) if next_level_xp > 0 else 0
st.progress(pg)

t1,t2,t3 = st.tabs(["⚔️ 운동", "🧠 공부", "🛡️ 루틴"])
with t1:
    cr, cp = st.columns(2)
    with cr:
        val = st.number_input("달리기(km)", 0.0, 43.0, 5.0, 0.1)
        if st.button("기록", key="br", type="primary", use_container_width=True): 
            if val>0: add_xp(val*20, f"🏃 달리기 {val}km", val)
    with cp:
        val = st.number_input("푸쉬업(회)", 0, 1000, 30, 5)
        if st.button("기록", key="bp", type="primary", use_container_width=True): 
            if val>0: add_xp(val*0.5, f"💪 팔굽혀펴기 {val}회", val)
with t2:
    val = st.number_input("자기계발(분)", 0, 1440, 60, 10)
    if st.button("기록", key="bs", type="primary", use_container_width=True): 
        if val>0: add_xp(val, f"🧠 자기계발 {val}분", val)
with t3:
    b1,b2,b3 = st.columns(3)
    if b1.button("💰 무지출", use_container_width=True): add_xp(20, "💰 무지출 챌린지", 0)
    if b2.button("💧 물", use_container_width=True): add_xp(10, "💧 물 마시기", 0)
    if b3.button("🧘 명상", use_container_width=True): add_xp(10, "🧘 명상", 0)

st.divider()
with st.expander("📜 기록 보기"):
    if logs: st.dataframe(pd.DataFrame(logs)[['Time','Action','XP']], use_container_width=True)
    else: st.info("기록 없음")
if st.button("↩️ 취소", type="secondary", use_container_width=True): undo()