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
        ws_col.append_row(["ID", "Name", "Date", "Rarity", "Cost", "Type"])

    return ws_status, ws_logs, ws_col

try: ws_status, ws_logs, ws_col = connect_to_sheet()
except Exception as e: st.error(f"❌ 연결 실패: {e}"); st.stop()

# ==========================================
# 2. 데이터 로드 & 골드 계산
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
            
    used_gold = 0
    if len(col_data) > 1:
        for row in col_data[1:]:
            try: used_gold += int(row[4])
            except: used_gold += 100
    
    current_gold = total_xp - used_gold
    return level, current_xp, total_xp, current_gold

def load_data():
    logs_data = ws_logs.get_all_records()
    col_data = ws_col.get_all_values()
    level, cur_xp, tot_xp, gold = calculate_status(logs_data, col_data)
    logs_data.reverse()
    
    my_pokemon = {} # 딕셔너리로 변경 (검색 속도 향상)
    if len(col_data) > 1:
        headers = col_data[0]
        for row in col_data[1:]:
            p_data = dict(zip(headers, row))
            # ID를 키로 저장
            my_pokemon[int(p_data['ID'])] = p_data
            
    return level, cur_xp, tot_xp, logs_data, gold, my_pokemon

level, current_xp, total_xp, logs, gold, my_pokemon = load_data()
next_level_xp = level * 100 

# ==========================================
# 3. 유틸리티 함수 (한글, CSS, 상성)
# ==========================================
def get_korean_name(eng_name):
    # 주요 포켓몬 한글 매핑 (필요시 계속 추가 가능)
    korea_map = {
        "Arceus": "아르세우스", "Mewtwo": "뮤츠", "Rayquaza": "레쿠쟈", 
        "Lugia": "루기아", "Ho-oh": "칠색조", "Dialga": "디아루가", "Palkia": "펄기아",
        "Garchomp": "한카리아스", "Metagross": "메타그로스", "Tyranitar": "마기라스",
        "Dragonite": "망나뇽", "Charizard": "리자몽", "Lucario": "루카리오",
        "Gengar": "팬텀", "Gyarados": "갸라도스", "Pikachu": "피카츄",
        "Eevee": "이브이", "Snorlax": "잠만보", "Bulbasaur": "이상해씨",
        "Charmander": "파이리", "Squirtle": "꼬부기", "Chikorita": "치코리타",
        "Magikarp": "잉어킹", "Caterpie": "캐터피", "Ditto": "메타몽", "Mew": "뮤",
        "Articuno": "프리져", "Zapdos": "썬더", "Moltres": "파이어"
    }
    return korea_map.get(eng_name, eng_name)

def get_type_icon(type_name):
    icons = {
        "fire": "🔥", "water": "💧", "grass": "🌿", "electric": "⚡", 
        "psychic": "🔮", "fighting": "👊", "dragon": "🐲", "normal": "⚪",
        "ghost": "👻", "steel": "🔩", "ground": "🏜️", "flying": "🕊️",
        "bug": "🐛", "poison": "☠️", "ice": "❄️", "rock": "🪨"
    }
    return icons.get(type_name, "❓")

def get_damage_multiplier(atk_type, def_type):
    super_eff = {"fire": ["grass", "ice", "bug", "steel"], "water": ["fire", "ground", "rock"], "grass": ["water", "ground", "rock"], "electric": ["water", "flying"]}
    if def_type in super_eff.get(atk_type, []): return 2.0
    return 1.0

def add_xp(amt, act, val):
    ts = (datetime.now() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")
    ws_logs.append_row([ts, act, int(amt), val])
    st.toast("✅ 저장 완료!", icon="💾"); st.rerun()

def save_pokemon(poke_id, name, rarity, cost, p_type):
    now = (datetime.now() + timedelta(hours=9)).strftime("%Y-%m-%d")
    ws_col.append_row([poke_id, name, now, rarity, cost, p_type])
    st.toast(f"🎉 {name} 구매 성공!", icon="ball")
    st.balloons()
    time.sleep(1.5)
    st.rerun()

def reset_collection():
    ws_col.clear()
    ws_col.append_row(["ID", "Name", "Date", "Rarity", "Cost", "Type"])
    st.rerun()

# 🏥 포켓몬 센터 로직 (가격 자동 산정)
def get_poke_market_info(poke_id):
    try:
        url = f"https://pokeapi.co/api/v2/pokemon/{poke_id}"
        res = requests.get(url).json()
        stats = {s['stat']['name']: s['base_stat'] for s in res['stats']}
        total_stats = sum(stats.values()) # 종족값 총합
        
        # 가격 정책: 종족값 * 10 (기본)
        price = total_stats * 10
        
        # 전설/환상 프리미엄 (종족값 580 이상이면 폭등)
        rarity = "Normal"
        if total_stats >= 600: 
            price = int(price * 5) # 600족 이상은 5배
            rarity = "Legendary"
        elif total_stats >= 500:
            price = int(price * 1.5) # 꽤 강함
            rarity = "Rare"
            
        p_type = res['types'][0]['type']['name']
        eng_name = res['name'].capitalize()
        kor_name = get_korean_name(eng_name)
        
        return total_stats, res['sprites']['front_default'], kor_name, p_type, price, rarity
    except: return 0, "", "Unknown", "normal", 0, "Normal"

# ==========================================
# 4. UI 구성
# ==========================================
st.set_page_config(page_title="관희의 성장 RPG", page_icon="⚔️", layout="centered")

# ◼️ 실루엣 처리를 위한 CSS 매직
st.markdown("""
<style>
    .shadow-img { filter: brightness(0) opacity(0.2); transition: 0.3s; }
    .color-img { filter: brightness(1); transition: 0.3s; }
    .shadow-img:hover { opacity: 0.5; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ 관리")
    st.write(f"보유 골드: **{gold} G**")
    if st.button("⚠️ 도감 초기화"): reset_collection()

# [헤더]
c1, c2 = st.columns([2,1])
with c1: st.markdown(f"<h2 style='margin:0;'>Lv.{level} 관희 <span style='font-size:16px; color:#555'>({current_xp}/{next_level_xp} XP)</span></h2>", unsafe_allow_html=True)
with c2: st.markdown(f"<div style='text-align:right; font-size:20px; font-weight:bold; color:#D4AC0D;'>💰 {gold} G</div>", unsafe_allow_html=True)
st.progress(min(current_xp/next_level_xp, 1.0))
st.divider()

menu = st.radio("", ["🏠 홈 (성장)", "🏥 포켓몬 센터", "⚔️ 배틀 스테이지", "🎒 내 도감"], horizontal=True)

# ----------------------------------------------------------------
# 🏠 홈 (성장)
# ----------------------------------------------------------------
if menu == "🏠 홈 (성장)":
    t1, t2 = st.tabs(["📝 기록하기", "📜 지난 기록"])
    with t1:
        st.subheader("🏃‍♂️ 피지컬")
        c1, c2, c3 = st.columns(3)
        with c1:
            val = st.number_input("달리기 (km)", 0.0, 42.195, 5.0, 0.1)
            if st.button("기록 (50G/km)", key="run", use_container_width=True):
                if val>0: add_xp(val*50, f"🏃 달리기 {val}km", val)
        with c2:
            val = st.number_input("푸쉬업 (회)", 0, 1000, 30, 5)
            if st.button("기록 (0.5G/회)", key="push", use_container_width=True):
                if val>0: add_xp(val*0.5, f"💪 푸쉬업 {val}회", val)
        with c3:
            val = st.number_input("스쿼트 (회)", 0, 1000, 50, 5)
            if st.button("기록 (0.5G/회)", key="squat", use_container_width=True):
                if val>0: add_xp(val*0.5, f"🦵 스쿼트 {val}회", val)

        st.subheader("🧠 뇌지컬")
        c4, c5 = st.columns(2)
        with c4:
            val = st.number_input("자기계발 (분)", 0, 1440, 60, 10)
            if st.button("기록 (1G/분)", key="study", use_container_width=True):
                if val>0: add_xp(val, f"🧠 자기계발 {val}분", val)
        with c5:
            val = st.number_input("독서 (쪽)", 0, 1000, 20, 5)
            if st.button("기록 (1G/쪽)", key="read", use_container_width=True):
                if val>0: add_xp(val, f"📖 독서 {val}쪽", val)

        st.subheader("🛡️ 습관")
        ch1, ch2, ch3 = st.columns(3)
        if ch1.button("💰 무지출 (20G)", use_container_width=True): add_xp(20, "💰 무지출", 0)
        if ch2.button("💧 물 마시기 (10G)", use_container_width=True): add_xp(10, "💧 물 마시기", 0)
        if ch3.button("🧹 방 청소 (15G)", use_container_width=True): add_xp(15, "🧹 방 청소", 0)

    with t2:
        if logs: st.dataframe(pd.DataFrame(logs)[['Time','Action','XP']], use_container_width=True)
        if st.button("↩️ 취소", type="secondary"): 
            if logs: ws_logs.delete_rows(len(ws_logs.get_all_values())); st.rerun()

# ----------------------------------------------------------------
# 🏥 포켓몬 센터 (전종 구매 시스템)
# ----------------------------------------------------------------
elif menu == "🏥 포켓몬 센터":
    st.info("💡 원하는 포켓몬의 도감 번호를 입력하면 시세가 조회됩니다.")
    
    col_search, col_res = st.columns([1, 2])
    with col_search:
        target_id = st.number_input("도감 번호 입력 (1~649)", 1, 649, 1)
        check_btn = st.button("🔍 시세 조회", use_container_width=True)
    
    if check_btn or 'market_id' in st.session_state:
        if check_btn: st.session_state['market_id'] = target_id
        
        mid = st.session_state.get('market_id', 1)
        cp, img, name, p_type, price, rarity = get_poke_market_info(mid)
        
        with col_res:
            with st.container(border=True):
                c_img, c_info = st.columns([1, 2])
                with c_img: st.image(img, width=100)
                with c_info:
                    st.subheader(f"No.{mid} {name}")
                    st.write(f"속성: {get_type_icon(p_type)} | 등급: **{rarity}**")
                    st.write(f"종족값 합계: **{cp}**")
                    st.markdown(f"### 🏷️ 가격: {price} G")
                    
                    if st.button("🛒 구매하기", type="primary", use_container_width=True):
                        if mid in my_pokemon:
                            st.warning("이미 가지고 있는 포켓몬이야!")
                        elif gold >= price:
                            save_pokemon(mid, name, rarity, price, p_type)
                            del st.session_state['market_id'] # 구매 후 초기화
                        else:
                            st.error(f"골드가 부족해! ({price - gold} G 부족)")

    st.divider()
    st.caption("※ 가격은 포켓몬의 강함(종족값)에 따라 자동 책정됩니다.")
    st.caption("※ 전설의 포켓몬은 프리미엄이 붙어 훨씬 비쌉니다.")

# ----------------------------------------------------------------
# ⚔️ 배틀 스테이지
# ----------------------------------------------------------------
elif menu == "⚔️ 배틀 스테이지":
    st.title("🔥 속성 배틀")
    
    if not my_pokemon:
        st.warning("출전할 포켓몬이 없습니다.")
    else:
        # 내 포켓몬
        my_names = [f"{v['Name']} (No.{k})" for k, v in my_pokemon.items()]
        choice = st.selectbox("내 포켓몬 선택:", my_names)
        my_id = int(choice.split("No.")[1].replace(")",""))
        my_cp, my_img, my_name, my_type, _, _ = get_poke_market_info(my_id)
        
        # 적 포켓몬
        if 'enemy_id' not in st.session_state: st.session_state['enemy_id'] = random.randint(1, 150)
        en_id = st.session_state['enemy_id']
        en_cp, en_img, en_name, en_type, _, _ = get_poke_market_info(en_id)
        
        c1, c2, c3 = st.columns([2,1,2])
        with c1:
            st.image(my_img, width=120)
            st.markdown(f"**{my_name}** ({get_type_icon(my_type)})")
            st.caption(f"CP: {my_cp}")
        with c2: st.markdown("## VS")
        with c3:
            st.image(en_img, width=120)
            st.markdown(f"**Wild {en_name}** ({get_type_icon(en_type)})")
            st.caption(f"CP: {en_cp}")
            
        st.divider()
        if st.button("⚔️ 배틀 시작!", type="primary", use_container_width=True):
            multiplier = get_damage_multiplier(my_type, en_type)
            final_my = my_cp * multiplier + random.randint(-20, 50)
            final_en = en_cp + random.randint(-20, 50)
            
            st.write(f"⚔️ 결과: {int(final_my)} vs {int(final_en)}")
            if multiplier > 1: st.success("효과가 굉장했다! (2배)")
            
            if final_my >= final_en:
                st.success("🏆 승리!")
                st.balloons()
                ts = (datetime.now() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")
                ws_logs.append_row([ts, "⚔️ 배틀 승리", 0, 1])
                st.session_state['enemy_id'] = random.randint(1, 649)
            else:
                st.error("💀 패배...")
                st.session_state['enemy_id'] = random.randint(1, 649)
        
        if st.button("다른 적 찾기"):
            st.session_state['enemy_id'] = random.randint(1, 649); st.rerun()

# ----------------------------------------------------------------
# 🎒 내 도감 (실루엣 시스템)
# ----------------------------------------------------------------
elif menu == "🎒 내 도감":
    st.title(f"🎒 포켓몬 도감 ({len(my_pokemon)} / 649)")
    
    # 세대별 탭 나누기 (렉 방지)
    gens = st.tabs(["1세대(1-151)", "2세대(152-251)", "3세대(252-386)", "4세대(387-493)", "5세대(494-649)"])
    
    gen_ranges = [(1, 151), (152, 251), (252, 386), (387, 493), (494, 649)]
    
    for i, tab in enumerate(gens):
        with tab:
            start, end = gen_ranges[i]
            # 그리드 형태로 표시
            cols = st.columns(4) # 한 줄에 4마리씩
            
            # 주의: 이미지 로딩이 많으므로 렌더링 시간 걸릴 수 있음
            for pid in range(start, end + 1):
                with cols[(pid - start) % 4]:
                    img_url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{pid}.png"
                    
                    if pid in my_pokemon:
                        # 보유 중 -> 컬러 이미지 + 이름
                        st.markdown(f"""
                        <div style="text-align:center;">
                            <img src="{img_url}" width="80" class="color-img">
                            <div style="font-size:12px; font-weight:bold;">No.{pid}</div>
                            <div style="font-size:12px;">{my_pokemon[pid]['Name']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        # 미보유 -> 그림자(실루엣) 처리
                        st.markdown(f"""
                        <div style="text-align:center; opacity:0.6;">
                            <img src="{img_url}" width="80" class="shadow-img">
                            <div style="font-size:12px; color:#ccc;">No.{pid}</div>
                            <div style="font-size:12px; color:#ccc;">???</div>
                        </div>
                        """, unsafe_allow_html=True)