import streamlit as st
import random
import re
import pandas as pd
import io
from openai import OpenAI
import google.generativeai as genai
from mistralai import Mistral

# --- 페이지 설정 ---
st.set_page_config(page_title="위기대응 시뮬레이터 v8", page_icon="🛡️", layout="wide")

# --- CSS ---
st.markdown("""
<style>
    .scenario-box { border-left: 5px solid #ff4b4b; background-color: #fff0f0; padding: 15px; border-radius: 5px; margin-bottom: 10px; }
    .secret-box { border-left: 5px solid #2b2b2b; background-color: #e0e0e0; padding: 15px; border-radius: 5px; margin-bottom: 20px; color: #333; }
    .result-box { padding: 20px; border-radius: 10px; margin-top: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .header-text { font-weight: bold; font-size: 1.1em; margin-bottom: 5px; }
    .content-text { font-family: 'Nanum Gothic', sans-serif; line-height: 1.6; white-space: pre-wrap; }
    .risk-label { font-weight: bold; font-size: 1.2em; }
    .risk-high { color: #d32f2f; }
    .risk-mid { color: #f57c00; }
    .risk-low { color: #388e3c; }
</style>
""", unsafe_allow_html=True)

# --- 상태 초기화 ---
if 'scenario_data' not in st.session_state: st.session_state.scenario_data = {}
if 'evaluation_result' not in st.session_state: st.session_state.evaluation_result = None
if 'history' not in st.session_state: st.session_state.history = []

# --- AI 호출 함수 ---
def call_ai_brain(provider, api_key, system_role, user_prompt):
    try:
        if provider == "OpenAI (GPT-4/3.5)":
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o", 
                messages=[{"role": "system", "content": system_role}, {"role": "user", "content": user_prompt}]
            )
            return response.choices[0].message.content

        elif provider == "Google Gemini":
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            full_prompt = f"{system_role}\n\n[상황/요청]\n{user_prompt}"
            response = model.generate_content(full_prompt)
            return response.text

        elif provider == "Mistral AI":
            client = Mistral(api_key=api_key)
            response = client.chat.complete(
                model="mistral-small-latest",
                messages=[{"role": "system", "content": system_role}, {"role": "user", "content": user_prompt}]
            )
            return response.choices[0].message.content
            
    except Exception as e:
        return f"⚠ AI 통신 오류 발생: {str(e)}"

# --- 유틸리티 ---
def parse_risk_score(text):
    match = re.search(r"\[\[리스크:\s*(\d{1,3})\]\]", text)
    return int(match.group(1)) if match else 50

def parse_eval_score(text):
    match = re.search(r"\[\[점수:\s*(\d{1,3})\]\]", text)
    return int(match.group(1)) if match else 0

def get_risk_color(score):
    if score >= 80: return "risk-high", "🚨 위험 (DANGER)"
    elif score >= 50: return "risk-mid", "⚠️ 주의 (CAUTION)"
    else: return "risk-low", "✅ 안전 (SAFE)"

# --- 사이드바 ---
with st.sidebar:
    st.title("🔮 Crisis Ops v8")
    st.markdown("---")
    provider = st.selectbox("🤖 AI 모델", ["Mistral AI", "Google Gemini", "OpenAI (GPT-4/3.5)"])
    api_key = st.text_input(f"{provider} API Key", type="password", placeholder="sk-...")
    st.markdown("---")
    
    # 엑셀 다운로드
    if st.session_state.history:
        st.markdown("### 🏆 시뮬레이션 기록")
        df = pd.DataFrame(st.session_state.history)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Log')
        
        st.download_button(
            label="💾 기록 엑셀 다운로드",
            data=output.getvalue(),
            file_name="Crisis_Ops_Log.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# --- 메인 로직 ---
st.title("🔮 미래 예지형 위기대응 시뮬레이터")

# [Phase 1] 설정 및 시작
if not st.session_state.scenario_data:
    st.info("장르와 플랫폼, 그리고 훈련 난이도를 선택하세요.")
    
    c1, c2, c3 = st.columns(3)
    with c1: genre = st.selectbox("🎮 장르", ["MMORPG", "수집형 RPG (가챠)", "FPS/TPS (슈팅)", "MOBA (AOS)", "스포츠/레이싱", "퍼즐/캐주얼", "서브컬처 비주얼 노벨"])
    with c2: platform = st.selectbox("💻 플랫폼", ["모바일", "PC", "멀티플랫폼"])
    with c3: difficulty = st.selectbox("🔥 난이도", ["쉬움 (Easy)", "보통 (Normal)", "어려움 (Hard)"])

    if st.button("💣 위기 상황 발령", type="primary", use_container_width=True):
        if not api_key:
            st.error("API 키를 입력해주세요.")
        else:
            with st.spinner(f"⚠️ [{difficulty}] 등급의 상황을 시뮬레이션 중..."):
                
                # 1. 난이도별 키워드
                hard_keywords = {
                    "MMORPG": "경제 붕괴(골드 인플레), 아이템 복사 버그, 랭커/방송인 특혜 논란, 공성전 서버 다운, 작업장/매크로 방치, 강화 확률 조작 의혹, 특정 길드 편파 운영",
                    "수집형 RPG (가챠)": "매출 관련 이슈, 확률 조작(천장 미적용), 일러스트 검열/표절(트레이싱), 픽업 일정 통수(이중 픽업), 캐릭터 성능 잠수함 너프, 사료(보상) 차별",
                    "FPS/TPS (슈팅)": "신종 핵(ESP/에임봇) 창궐, 넷코드(핑) 이슈, 밸런스 붕괴(사기총 방치), 맵 글리치(벽뚫기), 대회 공정성(방플), 티밍(어뷰징), 키보드/마우스 컨버터 논란",
                    "MOBA (AOS)": "서버 팅김(재접 불가), 치명적 버그(스킬 쿨타임 0초), 트롤/패작/대리 제재 미흡, 신챔프 OP 논란, 매칭 시스템(다인큐) 불공정, 닷지 버그 악용",
                    "스포츠/레이싱": "라이선스 만료(선수/차량 삭제), 물리 엔진 오류(차량 날아감/선수 끼임), P2W(현질) 밸런스 붕괴, 렉/핑으로 인한 승패 판정 오류, 랭킹 어뷰징, 카드깡 확률 논란",
                    "퍼즐/캐주얼": "클리어 불가능한 스테이지(난이도 조절 실패), 과도한 광고 노출(플레이 방해), 타 게임 리소스 도용/표절, 데이터 초기화/백섭, 소셜 기능(하트 보내기) 오류, 랭킹 조작",
                    "서브컬처 비주얼 노벨": "스토리/대사 사상 검증(혐오 표현), 번역 퀄리티(오역/밈 남발), 성우 논란(계약 해지), 굿즈 퀄리티 불량, 운영진의 유저 비하 발언, 설정 붕괴"
                }

                # 2. 난이도별 프롬프트 조절
                if "어려움" in difficulty:
                    level_instruction = "서비스 종료가 거론될 정도의 **최악의 위기**를 생성해라. 유저들이 환불 시위, 트럭 시위, 법적 대응을 언급하며 격분하는 상황이어야 한다."
                    current_triggers = hard_keywords.get(genre, "치명적인 버그, 운영 신뢰도 붕괴, 데이터 유실")
                    
                elif "보통" in difficulty:
                    level_instruction = "유저들이 불편을 겪어 불만을 표출하지만, **적절한 사과와 보상으로 수습 가능한** 운영 이슈를 생성해라. (예: 점검 연장, 툴팁 표기 오류, 버그 악용자 발생 등)"
                    current_triggers = "점검 시간 연장, 툴팁/텍스트 오기재, 이벤트 보상 미지급, 경미한 밸런스 불만, 번역 어색함, 특정 기기 팅김 현상"
                    
                else:
                    level_instruction = "신입 CM이 처리할 수 있는 **가벼운 해프닝이나 단순 실수**를 생성해라. 유저들도 심각하게 화내기보다 '일 안 하냐' 정도로 놀리거나 가볍게 건의하는 수준이어야 한다."
                    current_triggers = "단순 오탈자, 공지사항 링크 실수, 10분 내외의 접속 불안정, 이벤트 날짜 표기 혼동, 아이콘 이미지 깨짐"

                # 3. 상황 생성 요청
                sys_msg = (
                    f"너는 게임 운영 시뮬레이터다. **'{genre}'({platform})** 게임에서 발생한 상황을 브리핑해라.\n"
                    f"이번 시뮬레이션의 난이도는 **'{difficulty}'** 이다.\n"
                    f"난이도 가이드: {level_instruction}\n"
                    f"참고 키워드: [{current_triggers}]\n\n"
                    f"**[지시사항]**\n"
                    f"1. 난이도에 맞는 적절한 수위의 사고를 쳐라.\n"
                    f"2. 반드시 **[현상]**과 **[진짜 원인(Secret)]**을 구분해서 출력해라. 구분자는 '///' 를 사용해라."
                )
                user_msg = "위기 상황 브리핑해. 형식:\n[현상] 유저들이 겪는 문제와 반응\n///\n[진실] 개발팀이 파악한 진짜 원인 (CM만 알아야 함)"
                
                raw_text = call_ai_brain(provider, api_key, sys_msg, user_msg)
                parts = raw_text.split("///")
                
                st.session_state.scenario_data = {
                    "public": parts[0].strip(),
                    "cause": parts[1].strip() if len(parts) > 1 else "원인 불명",
                    "genre": genre
                }
                st.rerun()

# [Phase 2 & 3] 대응 및 평가
else:
    left_col, right_col = st.columns(2, gap="large")
    
    # === [좌측] 상황판 ===
    with left_col:
        st.subheader("📡 상황 모니터링")
        
        st.markdown(f"""
        <div class="scenario-box">
            <div class="header-text">🔥 [Public] 현재 상황</div>
            <div class="content-text">{st.session_state.scenario_data['public']}</div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("🔒 [1급 기밀] 진짜 원인 확인하기 (클릭)", expanded=False):
            st.markdown(f"""
            <div class="secret-box">
                <div class="header-text">🤫 [Secret] 내부 진실</div>
                <div class="content-text">{st.session_state.scenario_data['cause']}</div>
            </div>
            """, unsafe_allow_html=True)

        # 결과 리포트
        if st.session_state.evaluation_result:
            res = st.session_state.evaluation_result
            score = parse_eval_score(res.get('text', ''))
            risk = parse_risk_score(res.get('text', ''))
            risk_class, risk_msg = get_risk_color(risk)
            
            st.markdown(f"""
            <div class="result-box" style="border: 2px solid {'#2e7d32' if score >= 80 else '#c62828'};">
                <div class="header-text">📊 대응 평가: {score}점</div>
                <div class="risk-label {risk_class}">📉 미래 리스크: {risk}점 ({risk_msg})</div>
                <hr>
                <div class="content-text">{res.get('text', '')}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # [추가] 안전장치 문구
            st.info("ℹ️ **Notice:** AI의 평가와 제안은 참고용일 뿐 정답이 아닙니다. 실제 업무 적용 시에는 회사의 톤앤매너와 내부 규정에 따라 달라질 수 있으므로, 반드시 동료 및 유관부서와 논의하시기 바랍니다.")

    # === [우측] 대응 입력 ===
    with right_col:
        st.subheader("⌨️ 작전 통제실")
        
        with st.form("response_form"):
            st.markdown("**1. 내부 조치 (보고, 이후 행동 등)**")
            action = st.text_area("action", height=100, label_visibility="collapsed", placeholder="예: 개발팀에 원복 요청, 보상안 계산 지시...")
            
            st.markdown("**2. 유저 공지사항 (실제 게시물)**")
            notice = st.text_area("notice", height=250, label_visibility="collapsed", placeholder="[공지] 사과드립니다...")
            
            submit = st.form_submit_button("결재 및 미래 예측 (SIMULATE)", type="primary", use_container_width=True)
            
        if st.button("🔄 초기화", use_container_width=True):
            st.session_state.scenario_data = {}
            st.session_state.evaluation_result = None
            st.rerun()
            
        if submit:
            if not api_key: st.error("키 없음")
            elif not action or not notice: st.warning("내용 입력 필요")
            else:
                with st.spinner("🔮 미래의 타임라인을 계산 중입니다..."):
                    # 평가 프롬프트
                    sys_msg = (
                        "너는 베테랑 게임 운영자이자 미래학자다. CM의 대응을 평가해라. "
                        "형식은 아래를 엄수해라:\n"
                        "[[점수: 0~100]]\n[[리스크: 0~100]] (0=안전, 100=서비스종료위기)\n\n"
                        "## 🔮 미래 시뮬레이션\n"
                        "**🌞 [희망편]:** (긍정적 결과)\n"
                        "**⛈️ [절망편]:** (부정적 결과)\n\n"
                        "## 📝 피드백\n"
                        "**💬 총평:** (전반적인 평가)\n"
                        "**✍️ [첨삭 및 개선안]:** (공지사항 내용 중 구체적으로 고쳐야 할 문장이나 표현을 지적하고, 더 나은 수정안을 제시해라. 예를 들어 '죄송합니다' 보다는 '고개 숙여 사과드립니다'가 낫다 등.)"
                    )
                    user_msg = f"""
                    [상황] {st.session_state.scenario_data['public']}
                    [진실] {st.session_state.scenario_data['cause']}
                    [조치] {action}
                    [공지] {notice}
                    """
                    
                    text = call_ai_brain(provider, api_key, sys_msg, user_msg)
                    st.session_state.evaluation_result = {"text": text}
                    
                    st.session_state.history.append({
                        "Genre": st.session_state.scenario_data['genre'],
                        "Crisis": st.session_state.scenario_data['public'][:30],
                        "Score": parse_eval_score(text),
                        "Risk": parse_risk_score(text),
                        "Feedback": text
                    })
                    st.rerun()