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
def connect_to_sheet():
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", SCOPE)
    client = gspread.authorize(creds)
    sh = client.open(SHEET_NAME)
    
    try: ws_status = sh.worksheet("Status")
    except: ws_status = sh.add_worksheet("Status", 10, 5)
    try: ws_logs = sh.worksheet("Logs")
    except: 
        ws_logs = sh.add_worksheet("Logs", 1000, 5)
        ws_logs.append_row(["Time", "Action", "XP", "Value"])
    try: ws_col = sh.worksheet("Collection")
    except:
        ws_col = sh.add_worksheet("Collection", 1000, 5)
        ws_col.append_row(["ID", "Name", "Date", "Rarity", "Cost"]) # Cost 추가됨

    return ws_status, ws_logs, ws_col

try: ws_status, ws_logs, ws_col = connect_to_sheet()
except Exception as e: st.error(f"❌ 연결 실패: {e}"); st.stop()

# ==========================================
# 2. 데이터 로드 & 골드 계산 (개선됨)
# ==========================================
def calculate_status(logs_data, col_data):
    total_xp = 0
    for log in logs_data:
        try: total_xp += int(log.get("XP", 0)) if isinstance(log, dict) else int(log[2])
        except: continue

    level = 1
    current_xp = total_xp
    while True:
        if current_xp >= level * 100: current_xp -= level * 100; level += 1
        else: break
            
    # 골드 계산: 총 XP - (도감에 있는 포켓몬들의 Cost 합계)
    used_gold = 0
    if len(col_data) > 1: # 헤더 제외
        for row in col_data[1:]:
            try: used_gold += int(row[4]) # 5번째 칸이 Cost
            except: used_gold += 100 # Cost 정보 없으면 기본 100으로 간주
    
    current_gold = total_xp - used_gold
    return level, current_xp, total_xp, current_gold

def load_data():
    logs_data = ws_logs.get_all_records()
    col_data = ws_col.get_all_values()
    level, cur_xp, tot_xp, gold = calculate_status(logs_data, col_data)
    logs_data.reverse()
    
    my_pokemon = []
    if len(col_data) > 1:
        headers = col_data[0]
        for row in col_data[1:]:
            # 구버전 데이터 호환성 처리
            p_data = dict(zip(headers, row))
            if 'Cost' not in p_data: p_data['Cost'] = 100
            my_pokemon.append(p_data)
            
    return level, cur_xp, tot_xp, logs_data, gold, my_pokemon

level, current_xp, total_xp, logs, gold, my_pokemon = load_data()
next_level_xp = level * 100 

# ==========================================
# 3. 기능 함수들 (상점, 배틀)
# ==========================================
def add_xp(amt, act, val):
    ts = (datetime.now() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")
    ws_logs.append_row([ts, act, int(amt), val])
    st.toast("✅ 기록 완료!", icon="💾"); st.rerun()

def save_pokemon(poke_id, name, rarity, cost):
    now = (datetime.now() + timedelta(hours=9)).strftime("%Y-%m-%d")
    ws_col.append_row([poke_id, name, now, rarity, cost])
    st.toast(f"🎉 {name} 획득 성공!", icon="ball")
    st.balloons()
    time.sleep(1.5) # 축하할 시간 주기
    st.rerun()

def get_poke_stats(poke_id):
    try:
        url = f"https://pokeapi.co/api/v2/pokemon/{poke_id}"
        res = requests.get(url).json()
        stats = {s['stat']['name']: s['base_stat'] for s in res['stats']}
        hp = stats.get('hp', 50)
        attack = stats.get('attack', 50)
        defense = stats.get('defense', 50)
        speed = stats.get('speed', 50)
        # 전투력(CP) 대충 계산
        cp = hp + attack + defense + speed
        return cp, res['sprites']['front_default'], res['name'].capitalize()
    except: return 0, "", "Unknown"

# ==========================================
# 4. UI 구성
# ==========================================
st.set_page_config(page_title="관희의 성장 RPG", page_icon="⚔️", layout="centered")

# [헤더] 심플하게 변경 (육각형 삭제)
c1, c2 = st.columns([2,1])
with c1: 
    tier_colors = ["#717171", "#8C7853", "#808B96", "#D4AC0D", "#27AE60", "#2980B9", "#8E44AD", "#F1C40F"]
    tier_idx = min((level-1)//12, 7)
    st.markdown(f"<h2 style='color:{tier_colors[tier_idx]}; margin:0;'>Lv.{level} 관희 <span style='font-size:16px; color:#555'>({current_xp}/{next_level_xp} XP)</span></h2>", unsafe_allow_html=True)
with c2: 
    st.markdown(f"<div style='text-align:right; font-size:20px; font-weight:bold;'>💰 {gold} G</div>", unsafe_allow_html=True)

st.progress(min(current_xp/next_level_xp, 1.0))

# [메인 메뉴]
menu = st.radio("", ["🏠 홈 (성장)", "🏪 상점 (교환)", "⚔️ 배틀 스테이지", "🎒 내 도감"], horizontal=True)
st.divider()

# ----------------------------------------------------------------
# 🏠 홈 (기록)
# ----------------------------------------------------------------
if menu == "🏠 홈 (성장)":
    t1, t2 = st.tabs(["📝 기록하기", "📜 지난 기록"])
    with t1:
        c_a, c_b = st.columns(2)
        with c_a:
            if st.button("🏃 달리기 5km (+100G)", use_container_width=True): add_xp(100, "🏃 달리기 5km", 5)
            if st.button("💪 푸쉬업 50회 (+25G)", use_container_width=True): add_xp(25, "💪 푸쉬업 50회", 50)
            if st.button("🦵 스쿼트 50회 (+25G)", use_container_width=True): add_xp(25, "🦵 스쿼트 50회", 50)
        with c_b:
            if st.button("🧠 공부 1시간 (+60G)", use_container_width=True): add_xp(60, "🧠 자기계발 60분", 60)
            if st.button("📖 독서 20쪽 (+20G)", use_container_width=True): add_xp(20, "📖 독서 20쪽", 20)
            if st.button("🧹 방 청소 (+15G)", use_container_width=True): add_xp(15, "🧹 방 청소", 0)
    with t2:
        if logs: st.dataframe(pd.DataFrame(logs)[['Time','Action','XP']], use_container_width=True)
        if st.button("↩️ 마지막 기록 취소"): 
            if logs: ws_logs.delete_rows(len(ws_logs.get_all_values())); st.rerun()

# ----------------------------------------------------------------
# 🏪 상점 (교환소) - 업데이트됨!
# ----------------------------------------------------------------
elif menu == "🏪 상점 (교환)":
    st.subheader("🎲 랜덤 뽑기 (Gacha)")
    if st.button("❓ 랜덤 포켓몬 뽑기 (100 G)", type="primary", use_container_width=True):
        if gold >= 100:
            pid = random.randint(1, 649)
            res = requests.get(f"https://pokeapi.co/api/v2/pokemon/{pid}").json()
            name = res['name'].capitalize()
            rarity = "Legendary" if random.randint(1,100)>98 else "Normal"
            save_pokemon(pid, name, rarity, 100)
        else: st.toast("돈이 부족해!", icon="💸")

    st.divider()
    st.subheader("💎 확정 교환소 (Special Shop)")
    
    # [인기 포켓몬 리스트] - 가격 차별화
    shop_list = [
        {"id": 150, "name": "Mewtwo", "price": 3000, "desc": "최강의 전설"},
        {"id": 6, "name": "Charizard", "price": 1500, "desc": "리자몽 (인기 폭발)"},
        {"id": 448, "name": "Lucario", "price": 1000, "desc": "루카리오 (간지)"},
        {"id": 25, "name": "Pikachu", "price": 500, "desc": "근본 피카츄"},
        {"id": 133, "name": "Eevee", "price": 300, "desc": "귀여운 이브이"},
        {"id": 129, "name": "Magikarp", "price": 10, "desc": "잉어킹 (세일 중)"},
        {"id": 10, "name": "Caterpie", "price": 10, "desc": "캐터피 (떨이)"},
    ]
    
    for p in shop_list:
        c_img, c_info, c_btn = st.columns([1, 2, 1])
        with c_img:
            st.image(f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{p['id']}.png", width=60)
        with c_info:
            st.write(f"**{p['name']}**")
            st.caption(p['desc'])
        with c_btn:
            if st.button(f"{p['price']} G", key=f"buy_{p['id']}"):
                if gold >= p['price']:
                    rarity = "Shop"
                    save_pokemon(p['id'], p['name'], rarity, p['price'])
                else: st.toast("돈이 부족해!", icon="💸")

# ----------------------------------------------------------------
# ⚔️ 배틀 스테이지 - NEW!
# ----------------------------------------------------------------
elif menu == "⚔️ 배틀 스테이지":
    st.title("🔥 포켓몬 배틀")
    
    if not my_pokemon:
        st.warning("싸울 포켓몬이 없어! 상점에서 먼저 뽑아와.")
    else:
        # 1. 내 포켓몬 선택
        my_names = [f"{p['Name']} (No.{p['ID']})" for p in my_pokemon]
        choice = st.selectbox("출전할 포켓몬을 선택해:", my_names)
        my_idx = my_names.index(choice)
        my_p = my_pokemon[my_idx]
        
        # 2. 야생 포켓몬 생성 (세션 상태 사용)
        if 'enemy_id' not in st.session_state:
            st.session_state['enemy_id'] = random.randint(1, 150) # 1세대 위주
            
        # 3. 배틀 화면
        c_my, c_vs, c_enemy = st.columns([2, 1, 2])
        
        # 내 포켓몬 정보
        my_cp, my_img, my_real_name = get_poke_stats(my_p['ID'])
        with c_my:
            st.image(my_img, width=120)
            st.markdown(f"**{my_real_name}**")
            st.caption(f"전투력(CP): {my_cp}")
            
        with c_vs:
            st.markdown("<h1 style='text-align:center; padding-top:30px;'>VS</h1>", unsafe_allow_html=True)
            
        # 적 포켓몬 정보
        en_cp, en_img, en_name = get_poke_stats(st.session_state['enemy_id'])
        with c_enemy:
            st.image(en_img, width=120)
            st.markdown(f"**Wild {en_name}**")
            st.caption(f"전투력(CP): {en_cp}")
            
        st.divider()
        
        # 4. 배틀 액션
        if st.button("🔥 공격 개시! (Battle Start)", type="primary", use_container_width=True):
            # 승패 로직 (약간의 랜덤성 추가)
            my_final_power = my_cp + random.randint(-20, 50)
            en_final_power = en_cp + random.randint(-20, 50)
            
            st.write(f"⚔️ 나의 파워: **{my_final_power}** vs 적의 파워: **{en_final_power}**")
            
            if my_final_power >= en_final_power:
                win_xp = 50
                st.success(f"🏆 승리! 적을 쓰러뜨렸다! (+{win_xp} XP)")
                st.balloons()
                # 승리 보상 (자동 기록)
                ts = (datetime.now() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")
                ws_logs.append_row([ts, "⚔️ 배틀 승리", win_xp, 1])
                # 적 리셋
                st.session_state['enemy_id'] = random.randint(1, 649)
                time.sleep(2)
                st.rerun()
            else:
                st.error("💀 패배... 적이 너무 강했다.")
                # 적 리셋
                st.session_state['enemy_id'] = random.randint(1, 649)
        
        if st.button("다른 적 찾기 (패스)"):
            st.session_state['enemy_id'] = random.randint(1, 649)
            st.rerun()

# ----------------------------------------------------------------
# 🎒 내 도감
# ----------------------------------------------------------------
elif menu == "🎒 내 도감":
    st.title(f"🎒 내 가방 ({len(my_pokemon)}마리)")
    if my_pokemon:
        cols = st.columns(3)
        for i, mon in enumerate(my_pokemon):
            with cols[i % 3]:
                st.image(f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{mon['ID']}.png", width=80)
                st.caption(f"**{mon['Name']}**")
                # 희귀도 표시
                if mon.get('Rarity') == 'Legendary': st.write("🌟 **전설**")
                elif mon.get('Rarity') == 'Shop': st.write("🛒 **구매**")
    else:
        st.info("아직 포켓몬이 없어!")