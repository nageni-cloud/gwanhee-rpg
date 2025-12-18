import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

# ==========================================
# 1. 구글 시트 연동
# ==========================================
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
SHEET_NAME = "Gwanhee_Data" 

@st.cache_resource
def connect_to_sheet():
    # 클라우드 배포용 secrets 확인
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
    else:
        # 로컬 실행용 (혹시 나중에 쓸 수도 있으니 남겨둠)
        try: creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", SCOPE)
        except: st.error("설정 파일 오류"); st.stop()
        
    client = gspread.authorize(creds)
    sh = client.open(SHEET_NAME)
    
    try: ws_status = sh.worksheet("Status")
    except: ws_status = sh.add_worksheet("Status", 10, 5)
    
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
# 2. 데이터 로드 및 계산
# ==========================================
def calculate_status_from_logs(logs_data):
    total_xp = 0
    for log in logs_data:
        try:
            xp = int(log.get("XP", 0)) if isinstance(log, dict) else int(log[2])
            total_xp += xp
        except: continue

    level = 1
    current_xp = total_xp
    while True:
        req_xp = level * 100
        if current_xp >= req_xp:
            current_xp -= req_xp
            level += 1
        else: break
            
    return level, current_xp, total_xp

def load_data():
    logs_data = ws_logs.get_all_records()
    level, current_xp, total_xp = calculate_status_from_logs(logs_data)
    logs_data.reverse() # 최신순 정렬
    return level, current_xp, total_xp, logs_data

level, current_xp, total_xp, logs = load_data()
next_level_xp = level * 100 

# ==========================================
# 3. 티어 및 스트릭(연속 기록) 로직
# ==========================================
TIER_MAP = [
    {"name": "Iron", "start": 1, "color": "#717171"},
    {"name": "Bronze", "start": 13, "color": "#8C7853"},
    {"name": "Silver", "start": 25, "color": "#808B96"},
    {"name": "Gold", "start": 37, "color": "#D4AC0D"},
    {"name": "Platinum", "start": 49, "color": "#27AE60"},
    {"name": "Diamond", "start": 73, "color": "#2980B9"},
    {"name": "Master", "start": 85, "color": "#8E44AD"},
    {"name": "Challenger", "start": 109, "color": "#F1C40F"}
]
def get_tier(lv):
    for i in range(len(TIER_MAP)-1, -1, -1):
        if lv >= TIER_MAP[i]["start"]: return TIER_MAP[i]["name"], TIER_MAP[i]["color"]
    return "Iron", "#717171"
cur_n, cur_c = get_tier(level)

# 🔥 스트릭 계산 함수 (날짜 기준)
def get_streak(logs_data):
    if not logs_data: return 0
    dates = sorted(list(set([log['Time'].split(' ')[0] for log in logs_data])), reverse=True)
    
    if not dates: return 0
    
    streak = 0
    now_kst = datetime.now() + timedelta(hours=9)
    today_str = now_kst.strftime("%Y-%m-%d")
    
    # 오늘이나 어제 기록이 없으면 스트릭 끊김
    check_date = now_kst
    if dates[0] != today_str:
        check_date = now_kst - timedelta(days=1)
        
    for i in range(len(dates)):
        target_date = (check_date - timedelta(days=streak)).strftime("%Y-%m-%d")
        if target_date in dates:
            streak += 1
        else:
            break
    return streak

current_streak = get_streak(logs)

# ==========================================
# 4. 액션 (서버 저장)
# ==========================================
def save_to_server(ts, act, xp, val):
    ws_logs.append_row([ts, act, xp, val])
    try: ws_status.update_cell(2, 1, level)
    except: pass

def add_xp(amt, act, val):
    now_kst = datetime.now() + timedelta(hours=9)
    ts = now_kst.strftime("%Y-%m-%d %H:%M:%S")
    add = int(amt)
    save_to_server(ts, act, add, val)
    st.toast("✅ 저장 완료!", icon="☁️")
    st.rerun()

def undo():
    if not logs: st.toast("기록 없음", icon="🚫"); return
    all_rows = ws_logs.get_all_values()
    if len(all_rows) > 1:
        ws_logs.delete_rows(len(all_rows))
        st.toast("↩️ 취소 완료!", icon="🗑️")
        st.rerun()
    else: st.toast("취소할 기록이 없어", icon="🚫")

# ==========================================
# 5. UI 구성
# ==========================================
st.set_page_config(page_title="관희의 성장 RPG", page_icon="📈", layout="centered")

# [헤더] 티어 + 스트릭
col_t1, col_t2 = st.columns([3, 1])
with col_t1:
    st.markdown(f"<h2 style='color:{cur_c}; margin-bottom:0;'>{cur_n} <span style='color:#555;font-size:20px;'>(Lv.{level})</span></h2>", unsafe_allow_html=True)
with col_t2:
    if current_streak > 0:
        st.markdown(f"<div style='text-align:right; font-size:14px; font-weight:bold; color:#FF4B4B;'>🔥 {current_streak}일 연속!</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='text-align:right; font-size:14px; color:#999;'>💤 연속 기록 도전!</div>", unsafe_allow_html=True)

# [날짜 & 경험치 바]
now_kst = datetime.now() + timedelta(hours=9)
today = now_kst.date()
d_day = (today - datetime(2026,1,1).date()).days
d_str = f"D{d_day}" if d_day < 0 else f"Day +{d_day+1}"
st.caption(f"📅 {today} | 🚀 {d_str}")

pg = min(current_xp/next_level_xp, 1.0) if next_level_xp > 0 else 0
st.progress(pg)
st.caption(f"다음 레벨까지 {next_level_xp - current_xp} XP 남음")

st.divider()

# [메인 입력 탭]
t1, t2, t3 = st.tabs(["⚔️ 피지컬", "🧠 뇌지컬", "🛡️ 루틴"])

with t1: # 운동
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**🏃 달리기**")
        v1 = st.number_input("거리(km)", 0.0, 43.0, 5.0, 0.1, key="run")
        if st.button("기록 (+20/km)", key="b1", use_container_width=True): 
            if v1>0: add_xp(v1*20, f"🏃 달리기 {v1}km", v1)
    with c2:
        st.markdown("**🦵 스쿼트**")
        v2 = st.number_input("횟수(회)", 0, 1000, 30, 5, key="squat")
        if st.button("기록 (+0.5/회)", key="b2", use_container_width=True): 
            if v2>0: add_xp(v2*0.5, f"🦵 스쿼트 {v2}회", v2)
            
    st.markdown("**💪 푸쉬업**")
    v3 = st.number_input("횟수(회)", 0, 1000, 30, 5, key="push")
    if st.button("기록 (+0.5/회)", key="b3", use_container_width=True): 
        if v3>0: add_xp(v3*0.5, f"💪 팔굽혀펴기 {v3}회", v3)

with t2: # 공부
    c3, c4 = st.columns(2)
    with c3:
        st.markdown("**📚 자기계발**")
        v4 = st.number_input("시간(분)", 0, 1440, 60, 10, key="study")
        if st.button("기록 (+1/분)", key="b4", use_container_width=True): 
            if v4>0: add_xp(v4, f"🧠 자기계발 {v4}분", v4)
    with c4:
        st.markdown("**📖 독서**")
        v5 = st.number_input("페이지(쪽)", 0, 1000, 10, 5, key="read")
        if st.button("기록 (+1/쪽)", key="b5", use_container_width=True): 
            if v5>0: add_xp(v5, f"📖 독서 {v5}페이지", v5)

with t3: # 루틴
    b1, b2, b3 = st.columns(3)
    if b1.button("💰 무지출\n(+20XP)", use_container_width=True): add_xp(20, "💰 무지출 챌린지", 0)
    if b2.button("💧 물\n(+10XP)", use_container_width=True): add_xp(10, "💧 물 마시기", 0)
    if b3.button("🧹 방청소\n(+15XP)", use_container_width=True): add_xp(15, "🧹 방 청소/정리", 0)
    
    if st.button("🧘 명상 (+10XP)", use_container_width=True): add_xp(10, "🧘 명상", 0)

st.divider()

# [그래프 & 통계]
st.subheader("📊 성장 그래프 (최근 7일)")
if logs:
    df = pd.DataFrame(logs)
    df['Date'] = df['Time'].apply(lambda x: x.split(' ')[0])
    
    # 날짜별 획득 경험치 합계
    daily_xp = df.groupby('Date')['XP'].sum()
    daily_xp = daily_xp.tail(7)
    
    st.bar_chart(daily_xp, color="#FF4B4B")
else:
    st.info("데이터가 쌓이면 그래프가 나타납니다!")

# [기록 보기 & 취소]
with st.expander("📜 전체 기록 보기"):
    if logs: st.dataframe(pd.DataFrame(logs)[['Time','Action','XP']], use_container_width=True)
    else: st.info("기록 없음")
    
if st.button("↩️ 마지막 기록 취소", type="secondary", use_container_width=True): undo()