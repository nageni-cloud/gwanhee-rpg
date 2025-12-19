import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import requests
import random
import time

# ==========================================
# 1. 구글 시트 연동
# ==========================================
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
SHEET_NAME = "Gwanhee_Data" 

@st.cache_resource
def connect_db_v40(): # 버전 변경 (캐시 초기화)
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
    else:
        try: creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", SCOPE)
        except: st.error("인증 파일 오류"); st.stop()
            
    client = gspread.authorize(creds)
    sh = client.open(SHEET_NAME)
    
    try: ws_status = sh.worksheet("Status")
    except: ws_status = sh.add_worksheet("Status", 10, 5)
    try: ws_logs = sh.worksheet("Logs")
    except: ws_logs = sh.add_worksheet("Logs", 1000, 5); ws_logs.append_row(["Time", "Action", "XP", "Value"])
    try: ws_col = sh.worksheet("Collection")
    except: ws_col = sh.add_worksheet("Collection", 1000, 6); ws_col.append_row(["ID", "Name", "Date", "Rarity", "Cost", "Type"])

    return ws_status, ws_logs, ws_col

try: ws_status, ws_logs, ws_col = connect_db_v40()
except Exception as e: st.error(f"연결 실패: {e}"); st.stop()

# ==========================================
# 2. 데이터 로드
# ==========================================
def load_data():
    logs_data = ws_logs.get_all_records()
    col_data = ws_col.get_all_values()
    
    total_xp = 0
    claimed_sets = set() 

    for log in logs_data:
        try: 
            xp = int(log.get("XP", 0)) if isinstance(log, dict) else int(log[2])
            act = log.get("Action", "") if isinstance(log, dict) else log[1]
            total_xp += xp
            if "[업적 달성]" in act:
                set_name = act.split("] ")[1]
                claimed_sets.add(set_name)
        except: continue
            
    used_gold = 0
    my_pokemon_counts = {} 
    my_shinies = set() 
    
    if len(col_data) > 1:
        for row in col_data[1:]:
            try:
                pid = int(row[0])
                rarity = row[3]
                cost = int(row[4])
                used_gold += cost
                
                my_pokemon_counts[pid] = my_pokemon_counts.get(pid, 0) + 1
                if "Shiny" in rarity:
                    my_shinies.add(pid)
            except: continue
            
    current_gold = total_xp - used_gold
    
    level = 1
    temp = total_xp
    while temp >= level * 100:
        temp -= level * 100
        level += 1
    current_xp = temp
    
    if isinstance(logs_data, list): logs_data.reverse()
    return level, current_xp, total_xp, current_gold, logs_data, my_pokemon_counts, my_shinies, claimed_sets

level, current_xp, total_xp, gold, logs, my_pokemon_counts, my_shinies, claimed_sets = load_data()
next_level_xp = level * 100

# ==========================================
# 3. 로직 함수 (티어/스트릭/칭호)
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

def get_streak(logs_data):
    if not logs_data: return 0
    try: dates = sorted(list(set([log['Time'].split(' ')[0] for log in logs_data])), reverse=True)
    except: return 0
    if not dates: return 0
    streak = 0
    now_kst = datetime.now() + timedelta(hours=9)
    today_str = now_kst.strftime("%Y-%m-%d")
    check_date = now_kst
    if dates[0] != today_str: check_date = now_kst - timedelta(days=1)
    for i in range(len(dates)):
        target = (check_date - timedelta(days=streak)).strftime("%Y-%m-%d")
        if target in dates: streak += 1
        else: break
    return streak
current_streak = get_streak(logs)

def get_unlocked_titles(counts, shinies):
    titles = ["신참 트레이너"] 
    if len(counts) >= 10: titles.append("오박사의 조수")
    if len(counts) >= 50: titles.append("베테랑")
    if len(counts) >= 100: titles.append("포켓몬 마스터")
    if len(shinies) > 0: titles.append("✨ 빛의 탐구자")
    if 129 in counts: titles.append("낚시꾼") 
    if 25 in counts: titles.append("피카츄 찐팬")
    if 150 in counts or 151 in counts: titles.append("유전자 연구원")
    if 133 in counts: titles.append("브이즈 마니아")
    return titles

COLLECTION_SETS = [
    {"name": "태초마을의 시작", "desc": "오박사님이 주신 선택받은 세 마리.", "ids": [1, 4, 7], "reward": 1000},
    {"name": "상록숲의 악몽", "desc": "풀숲에 들어가면 끝도 없이 나오는 친구들.", "ids": [10, 13, 16, 19], "reward": 500},
    {"name": "니드런 왕실", "desc": "왕과 여왕, 그리고 그들의 아이들.", "ids": [29, 32, 31, 34], "reward": 1200},
    {"name": "이브이 4형제", "desc": "가능성은 무한대! 진화의 돌이 필요해.", "ids": [133, 134, 135, 136], "reward": 1500},
    {"name": "곤충 채집 소년", "desc": "상록숲의 진정한 지배자들.", "ids": [12, 15, 49, 123, 127], "reward": 1000},
    {"name": "로켓단의 음모", "desc": "이 세계의 파괴를 막기 위해!", "ids": [23, 24, 52, 109, 110], "reward": 1200},
    {"name": "격투 도장", "desc": "노란시티 격투 도장의 챔피언들.", "ids": [57, 68, 106, 107], "reward": 1500},
    {"name": "초능력자", "desc": "숟가락 구부리기의 달인들.", "ids": [65, 97, 122], "reward": 1500},
    {"name": "폭포오르기", "desc": "약한 잉어킹이 흉폭한 용이 되기까지.", "ids": [129, 130], "reward": 1000},
    {"name": "고대 화석의 비밀", "desc": "박물관에서 되살려낸 고대의 존재.", "ids": [139, 141, 142], "reward": 2000},
    {"name": "전설의 새", "desc": "관동 지방 하늘을 지배하는 전설.", "ids": [144, 145, 146], "reward": 3000},
    {"name": "최강의 유전자", "desc": "환상의 포켓몬과 그 복제물.", "ids": [150, 151], "reward": 5000}
]

# ==========================================
# 4. 액션 함수
# ==========================================
def add_xp(amt, act, val):
    ts = (datetime.now() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")
    ws_logs.append_row([ts, act, int(amt), val])
    try: ws_status.update_cell(2, 1, level)
    except: pass
    st.toast(f"✅ 기록 완료! (+{int(amt)}G)", icon="🔥")
    time.sleep(0.5)
    st.rerun()

def claim_set_reward(set_name, reward):
    ts = (datetime.now() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")
    ws_logs.append_row([ts, f"[업적 달성] {set_name}", reward, 0])
    st.balloons()
    st.success(f"🏆 업적 달성! [{set_name}] 보상 {reward}G 지급!")
    time.sleep(2)
    st.rerun()

def undo():
    if logs:
        ws_logs.delete_rows(len(ws_logs.get_all_values()))
        st.toast("↩️ 취소됨", icon="🗑️")
        st.rerun()

def process_gacha(pid, name, rarity, cost, p_type, is_duplicate, current_count, is_shiny):
    now = (datetime.now() + timedelta(hours=9)).strftime("%Y-%m-%d")
    ts = (datetime.now() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")
    
    final_rarity = rarity
    if is_shiny:
        final_rarity = "Shiny" 
        name = f"🌟 {name}"
    
    ws_col.append_row([pid, name, now, final_rarity, cost, p_type])
    
    if is_shiny:
        st.balloons()
        st.success(f"✨ 대박! 이로치 {name} 등장!")
        time.sleep(2)
        st.rerun()
    elif is_duplicate:
        payback = 250
        ws_logs.append_row([ts, f"♻️ 페이백 ({name})", payback, 0])
        st.toast(f"😢 중복.. 250G 환급", icon="♻️")
        time.sleep(1.5)
        st.rerun()
    else:
        st.balloons()
        st.toast(f"🎉 NEW! {name} 획득!", icon="📦")
        time.sleep(1.5)
        st.rerun()

KOR_NAMES = {
    1:"이상해씨", 2:"이상해풀", 3:"이상해꽃", 4:"파이리", 5:"리자드", 6:"리자몽",
    7:"꼬부기", 8:"어니부기", 9:"거북왕", 10:"캐터피", 11:"단데기", 12:"버터플",
    13:"뿔충이", 14:"딱충이", 15:"독침붕", 16:"구구", 17:"피죤", 18:"피죤투", 19:"꼬렛",
    23:"아보", 24:"아보크", 25:"피카츄", 26:"라이츄", 29:"니드런♀", 31:"니드퀸", 32:"니드런♂", 34:"니드킹",
    39:"푸린", 52:"나옹", 54:"고라파덕", 57:"성원숭", 59:"윈디", 65:"후딘", 68:"괴력몬", 74:"꼬마돌", 94:"팬텀", 95:"롱스톤",
    97:"슬리퍼", 106:"시라소몬", 107:"홍수몬", 109:"또가스", 110:"또도가스", 122:"마임맨", 123:"스라이크", 127:"쁘사이저",
    129:"잉어킹", 130:"갸라도스", 131:"라프라스", 133:"이브이", 134:"샤미드", 135:"쥬피썬더", 136:"부스터",
    139:"암스타", 141:"투구푸스", 142:"프테라",
    143:"잠만보", 144:"프리져", 145:"썬더", 146:"파이어",
    149:"망나뇽", 150:"뮤츠", 151:"뮤"
}
def get_poke_info_fast(pid):
    try:
        url = f"https://pokeapi.co/api/v2/pokemon/{pid}"
        res = requests.get(url, timeout=2).json()
        p_type = res['types'][0]['type']['name']
        k_name = KOR_NAMES.get(pid, res['name'].capitalize())
        stats = sum([s['base_stat'] for s in res['stats']])
        rarity = "Normal"
        if stats >= 580: rarity = "Legend"
        elif stats >= 500: rarity = "Rare"
        if pid in [1,4,7,25,133,143,149,150,151]: rarity = "Special"
        return k_name, rarity, p_type
    except: return "Unknown", "Normal", "normal"

# ==========================================
# 5. UI 구성
# ==========================================
st.set_page_config(page_title="관희의 성장 RPG", page_icon="🔥", layout="centered")

st.markdown("""
<style>
    .shadow-img { filter: brightness(0) opacity(0.2); width: 40px; margin-right: 5px; }
    .color-img { filter: brightness(1); width: 60px; }
    .poke-box { background-color: #f9f9f9; border-radius: 8px; padding: 5px; text-align: center; border: 1px solid #eee; margin-bottom: 5px; }
    .shiny-box { background-color: #FFF8E1; border: 2px solid #FFD700; border-radius: 8px; padding: 5px; text-align: center; margin-bottom: 5px; }
    .set-card { border: 1px solid #ddd; padding: 15px; border-radius: 12px; margin-bottom: 12px; background-color: #ffffff; }
</style>
""", unsafe_allow_html=True)

# [칭호 로직]
unlocked_titles = get_unlocked_titles(my_pokemon_counts, my_shinies)
if 'my_title' not in st.session_state: st.session_state['my_title'] = unlocked_titles[-1]

with st.sidebar:
    st.markdown("### 🏷️ 칭호 설정")
    st.session_state['my_title'] = st.selectbox("칭호를 선택하세요", unlocked_titles, index=len(unlocked_titles)-1)

# [헤더]
st.title(f"🔥 [{st.session_state['my_title']}] 관희")

# [날짜 & D-Day 표시 (KST 적용)]
now_kst = datetime.now() + timedelta(hours=9)
today_str = now_kst.strftime("%Y년 %m월 %d일")
target_date = datetime(2026, 1, 1) # 2026년 1월 1일 목표
d_day_val = (target_date.date() - now_kst.date()).days
d_day_str = f"D-{d_day_val}" if d_day_val > 0 else (f"D+{abs(d_day_val)}" if d_day_val < 0 else "D-Day")
st.caption(f"📅 {today_str} | 🚀 2026년까지 {d_day_str}")

c1, c2 = st.columns([2,1])
with c1: 
    st.markdown(f"<h3 style='color:{cur_c}; margin:0;'>{cur_n} Tier</h3>", unsafe_allow_html=True)
    st.caption(f"Lv.{level} | {current_xp}/{next_level_xp} XP")
with c2: 
    if current_streak > 0: 
        st.markdown(f"<div style='text-align:right; color:#FF4B4B;'><b>🔥 {current_streak}일 연속!</b></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='text-align:right; font-weight:bold; color:#D4AC0D;'>💰 {gold} G</div>", unsafe_allow_html=True)

st.progress(min(current_xp/next_level_xp, 1.0))
st.divider()

tab1, tab2, tab3 = st.tabs(["🏠 성장", "🏥 뽑기", "🎒 도감/업적"])

# 1. 성장
with tab1:
    st.subheader("📊 성장 그래프 (7일)")
    if logs:
        df = pd.DataFrame(logs)
        df['Date'] = df['Time'].apply(lambda x: x.split(' ')[0])
        daily_xp = df.groupby('Date')['XP'].sum().tail(7)
        st.bar_chart(daily_xp, color="#FF4B4B")

    st.subheader("📝 오늘의 기록")
    t_phy, t_brain, t_routine = st.tabs(["⚔️ 피지컬", "🧠 뇌지컬", "🛡️ 루틴"])
    
    with t_phy:
        c1, c2 = st.columns(2)
        with c1:
            v1 = st.number_input("달리기(km)", 0.0, 42.0, 5.0, 0.1, key="run")
            if st.button("기록 (+50G/km)", key="b1", type="primary", use_container_width=True): 
                if v1>0: add_xp(v1*50, f"🏃 달리기 {v1}km", v1)
        with c2:
            v2 = st.number_input("근력운동(회)", 0, 1000, 30, 10, key="gym")
            if st.button("기록 (+0.5G/회)", key="b2", type="primary", use_container_width=True): 
                if v2>0: add_xp(v2*0.5, f"💪 근력운동 {v2}회", v2)

    with t_brain:
        c3, c4 = st.columns(2)
        with c3:
            v3 = st.number_input("자기계발(분)", 0, 1440, 60, 10, key="study")
            if st.button("기록 (+1G/분)", key="b3", type="primary", use_container_width=True): 
                if v3>0: add_xp(v3, f"🧠 자기계발 {v3}분", v3)
        with c4:
            v4 = st.number_input("독서(쪽)", 0, 1000, 10, 5, key="read")
            if st.button("기록 (+1G/쪽)", key="b4", type="primary", use_container_width=True): 
                if v4>0: add_xp(v4, f"📖 독서 {v4}쪽", v4)

    with t_routine:
        r1, r2, r3 = st.columns(3)
        if r1.button("💰 무지출\n(20G)", type="primary", use_container_width=True): add_xp(20, "💰 무지출", 0)
        if r2.button("💧 물 마시기\n(10G)", type="primary", use_container_width=True): add_xp(10, "💧 물 마시기", 0)
        if r3.button("🧹 방 청소\n(15G)", type="primary", use_container_width=True): add_xp(15, "🧹 방 청소", 0)

    with st.expander("📜 최근 기록 보기"):
        if logs: st.dataframe(pd.DataFrame(logs)[['Time','Action','XP']], use_container_width=True)
        if st.button("↩️ 마지막 기록 취소"): undo()

# 2. 뽑기
with tab2:
    st.markdown("### ❓ 운명의 뽑기 (1세대)")
    st.info(f"현재 보유 골드: **{gold} G**")
    
    st.markdown("""
    - **중복 환급:** 250G
    - **✨ 이로치 확률:** **4% (1/25)**
    - **확률 보정:** 보유할수록 등장 확률 감소
    """)
    st.write("")
    
    if st.button("🔮 500G 뽑기!", type="primary", use_container_width=True):
        if gold >= 500:
            all_ids = list(range(1, 152))
            weights = []
            for pid in all_ids:
                count = my_pokemon_counts.get(pid, 0)
                w = 1.0 / (2 ** count)
                weights.append(w)
            
            pid = random.choices(all_ids, weights=weights, k=1)[0]
            is_shiny = random.random() < 0.04
            
            k_name, rarity, p_type = get_poke_info_fast(pid)
            current_count = my_pokemon_counts.get(pid, 0)
            is_dup = current_count > 0
            
            process_gacha(pid, k_name, rarity, 500, p_type, is_dup, current_count, is_shiny)
            
        else: st.error("골드가 부족합니다! 성장 탭에서 운동하세요!")

# 3. 도감 & 업적
with tab3:
    sub_t1, sub_t2 = st.tabs(["📖 전체 도감", "🏆 컬렉션 업적"])
    
    with sub_t1:
        if 'dex_page' not in st.session_state: st.session_state['dex_page'] = 0
        PER_PAGE = 24
        
        page = st.session_state['dex_page']
        start = page * PER_PAGE + 1
        end = min(start + PER_PAGE, 152)
        
        c_p1, c_p2, c_p3 = st.columns([1, 2, 1])
        with c_p1: 
            if page > 0: 
                if st.button("◀"): st.session_state['dex_page'] -= 1; st.rerun()
        with c_p2: st.markdown(f"<div style='text-align:center;'><b>No.{start} ~ {end-1}</b></div>", unsafe_allow_html=True)
        with c_p3: 
            if end < 151: 
                if st.button("▶"): st.session_state['dex_page'] += 1; st.rerun()
                
        st.divider()
        
        poke_ids = list(range(start, end))
        for i in range(0, len(poke_ids), 3):
            row_cols = st.columns(3)
            for j in range(3):
                if i + j < len(poke_ids):
                    pid = poke_ids[i+j]
                    
                    if pid in my_shinies:
                        img_url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/shiny/{pid}.png"
                        box_class = "shiny-box"
                    else:
                        img_url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{pid}.png"
                        box_class = "poke-box"
                    
                    with row_cols[j]:
                        if pid in my_pokemon_counts:
                            k_name = KOR_NAMES.get(pid, f"No.{pid}")
                            if pid in my_shinies: k_name = f"🌟 {k_name}"
                            st.markdown(f"""<div class="{box_class}"><img src="{img_url}" class="color-img"><div style="font-size:11px; font-weight:bold;">{k_name}</div></div>""", unsafe_allow_html=True)
                        else:
                            st.markdown(f"""<div class="poke-box" style="opacity:0.5;"><img src="{img_url}" class="shadow-img"><div style="font-size:11px; color:#ccc;">{pid}</div></div>""", unsafe_allow_html=True)

    with sub_t2:
        st.info("💡 실루엣을 보고 필요한 포켓몬을 모아보세요!")
        
        for p_set in COLLECTION_SETS:
            collected = [pid for pid in p_set['ids'] if pid in my_pokemon_counts]
            is_complete = len(collected) == len(p_set['ids'])
            is_claimed = p_set['name'] in claimed_sets
            
            with st.container():
                st.markdown(f"""
                <div class="set-card">
                    <div style="font-weight:bold; font-size:16px;">{p_set['name']} <span style='color:#D4AC0D; font-size:13px;'>({p_set['reward']}G)</span></div>
                    <div style="font-size:12px; color:#666; margin-bottom:8px;">{p_set['desc']}</div>
                </div>
                """, unsafe_allow_html=True)
                
                cols = st.columns(len(p_set['ids']))
                for idx, pid in enumerate(p_set['ids']):
                    img_url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{pid}.png"
                    with cols[idx]:
                        st.markdown(f"<div style='text-align:center;'><img src='{img_url}' class='shadow-img' style='width:35px;'></div>", unsafe_allow_html=True)
                
                st.write("")
                col_btn, col_prog = st.columns([1, 2])
                with col_btn:
                    if is_claimed:
                        st.button("✅ 완료", key=f"c_{p_set['name']}", disabled=True)
                    elif is_complete:
                        if st.button("🎁 받기", key=f"get_{p_set['name']}", type="primary"):
                            claim_set_reward(p_set['name'], p_set['reward'])
                    else:
                        st.button("🔒 미달성", key=f"lk_{p_set['name']}", disabled=True)
                with col_prog:
                    st.progress(len(collected) / len(p_set['ids']))
                    st.caption(f"{len(collected)} / {len(p_set['ids'])}")
            
            st.divider()