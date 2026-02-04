import streamlit as st
import random
import re
import pandas as pd
import io
from openai import OpenAI
import google.generativeai as genai
from mistralai import Mistral

# --- 페이지 설정 ---
st.set_page_config(page_title="위기대응 시뮬레이터 v14", page_icon="🛡️", layout="wide")

# --- CSS ---
st.markdown("""
<style>
    .scenario-box { border-left: 5px solid #ff4b4b; background-color: #fff0f0; padding: 15px; border-radius: 5px; margin-bottom: 10px; }
    .secret-box { border-left: 5px solid #2b2b2b; background-color: #e0e0e0; padding: 15px; border-radius: 5px; margin-bottom: 20px; color: #333; }
    .result-box { padding: 20px; border-radius: 10px; margin-top: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .mentor-box { border: 2px solid #1565C0; background-color: #e3f2fd; padding: 20px; border-radius: 10px; margin-top: 10px; }
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
if 'mentor_solution' not in st.session_state: st.session_state.mentor_solution = None # 멘토 답안 저장용
if 'history' not in st.session_state: st.session_state.history = []

# --- 텍스트 정제 함수 ---
def clean_ai_response(text):
    if not text: return ""
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n", "", text)
    text = re.sub(r"\n```$", "", text)
    return text.strip()

# --- AI 호출 함수 ---
def call_ai_brain(provider, api_key, system_role, user_prompt, temperature=0.5):
    try:
        if provider == "OpenAI (GPT-4o)":
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o", 
                messages=[{"role": "system", "content": system_role}, {"role": "user", "content": user_prompt}],
                temperature=temperature,
                max_tokens=2000 # 토큰 수 넉넉하게
            )
            return response.choices[0].message.content

        elif provider == "Google Gemini":
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(
                f"{system_role}\n\n[상황/요청]\n{user_prompt}",
                generation_config=genai.types.GenerationConfig(temperature=temperature, max_output_tokens=2000)
            )
            return response.text

        elif provider == "Mistral AI":
            client = Mistral(api_key=api_key)
            response = client.chat.complete(
                model="mistral-small-latest",
                messages=[{"role": "system", "content": system_role}, {"role": "user", "content": user_prompt}],
                temperature=temperature,
                max_tokens=2000
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
    st.title("🔮 Crisis Ops v14")
    st.markdown("---")
    provider = st.selectbox("🤖 AI 모델", ["Mistral AI", "Google Gemini", "OpenAI (GPT-4o)"])

    # 👇 [추가] 미스트랄 선택 시 발급 링크 버튼 표시
    if provider == "Mistral AI":
        st.link_button(
            label="🔑 Mistral API Key 발급받기", 
            url="https://docs.google.com/presentation/d/1xTUWrusNROIonDWL5hEWpybNCqo2W8kYHr4czDPWnok/edit?slide=id.p#slide=id.p",
            help="클릭하면 발급 가이드 페이지로 이동합니다."
        )
    
    # ... (API Key 입력창 코드) ...
    api_key = st.text_input(f"{provider} API Key", type="password", placeholder="sk-...")
    
    st.markdown("---")
    persona_mode = st.radio(
        "🧠 AI 성향 설정",
        ["👮‍♂️ 논리적/보수적 (FM)", "⚖️ 밸런스형 (추천)", "🎭 창의적/드라마틱"],
        index=1
    )
    
    if "논리적" in persona_mode: current_temp = 0.3
    elif "창의적" in persona_mode: current_temp = 0.7 
    else: current_temp = 0.5

    st.markdown("---")
    
    # [수정] 엑셀 다운로드 (데이터 컬럼 정리)
    if st.session_state.history:
        st.markdown("### 🏆 시뮬레이션 기록")
        df = pd.DataFrame(st.session_state.history)
        
        # 컬럼 순서 및 이름 보기 좋게 정렬 (옵션)
        # df = df[['Genre', 'Score', 'Risk', 'Crisis', 'User_Action', 'User_Notice', 'Feedback']]
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Log')
        
        st.download_button(
            label="💾 전체 기록 엑셀 다운로드",
            data=output.getvalue(),
            file_name="Crisis_Ops_Log.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="내가 작성한 공지와 AI 피드백이 모두 저장됩니다."
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
                
                hard_keywords = {
                    "MMORPG": "경제 붕괴(골드 인플레), 아이템 복사 버그, 랭커/방송인 특혜 논란, 공성전 서버 다운, 작업장/매크로 방치, 강화 확률 조작 의혹, 특정 길드 편파 운영, 운영자 계정 남용",
                    "수집형 RPG (가챠)": "매출 관련 이슈, 확률 조작(천장 미적용), 일러스트 검열/표절(트레이싱), 픽업 일정 통수(이중 픽업), 캐릭터 성능 잠수함 너프, 사료(보상) 차별, 한정 캐릭터 복각 논란",
                    "FPS/TPS (슈팅)": "신종 핵(ESP/에임봇) 창궐, 넷코드(핑) 이슈, 밸런스 붕괴(사기총 방치), 맵 글리치(벽뚫기), 대회 공정성(방플), 티밍(어뷰징), 키보드/마우스 컨버터 논란",
                    "MOBA (AOS)": "서버 팅김(재접 불가), 치명적 버그(스킬 쿨타임 0초), 트롤/패작/대리 제재 미흡, 신챔프 OP 논란, 매칭 시스템(다인큐) 불공정, 닷지 버그 악용, 오브젝트 버그",
                    "스포츠/레이싱": "라이선스 만료(선수/차량 삭제), 물리 엔진 오류(차량 날아감/선수 끼임), P2W(현질) 밸런스 붕괴, 렉/핑으로 인한 승패 판정 오류, 랭킹 어뷰징, 카드깡 확률 논란",
                    "퍼즐/캐주얼": "클리어 불가능한 스테이지(난이도 조절 실패), 과도한 광고 노출(플레이 방해), 타 게임 리소스 도용/표절, 데이터 초기화/백섭, 소셜 기능(하트 보내기) 오류, 랭킹 조작",
                    "서브컬처 비주얼 노벨": "스토리/대사 사상 검증(혐오 표현), 번역 퀄리티(오역/밈 남발), 성우 논란(계약 해지), 굿즈 퀄리티 불량, 운영진의 유저 비하 발언, 설정 붕괴"
                }

                if "어려움" in difficulty:
                    level_instruction = (
                        "서비스의 존폐가 걸린 **심각한 위기**를 생성해라. 유저들의 분노가 극에 달해 있다. "
                        "단, **'수습 불가능한 수치'(예: 유저 90% 이탈, 전수 조사 결과 100% 표절 등)는 피해라.** "
                        "CM의 역량에 따라 **회생할 수 있는 여지**를 아주 조금은 남겨둬라."
                    )
                    raw_triggers = hard_keywords.get(genre, "치명적인 버그, 운영 신뢰도 붕괴")
                elif "보통" in difficulty:
                    level_instruction = "유저들이 큰 불편을 겪어 불만을 표출하지만, **적절한 사과와 보상으로 충분히 수습 가능한** 수준의 위기를 생성해라."
                    raw_triggers = "점검 시간 연장, 툴팁/텍스트 오기재, 이벤트 보상 미지급, 경미한 밸런스 불만, 번역 어색함"
                else:
                    level_instruction = "신입 CM이 처리할 수 있는 **가벼운 해프닝이나 단순 실수**를 생성해라."
                    raw_triggers = "단순 오탈자, 공지사항 링크 실수, 10분 내외의 접속 불안정, 이벤트 날짜 표기 혼동"

                trigger_list = [t.strip() for t in raw_triggers.split(',')]
                pick_count = random.choices([0, 1, 2, 3], weights=[20, 40, 30, 10])[0]
                
                if pick_count == 0: selected_triggers = "지정된 키워드 없음. (창의적으로 생성)"
                else: selected_triggers = ", ".join(random.sample(trigger_list, min(pick_count, len(trigger_list))))

                random_seed = random.randint(1, 10000)

                sys_msg_public = (
                    f"너는 게임 운영 시뮬레이터의 상황 브리핑 AI다. **'{genre}'({platform})** 게임의 위기 상황을 보고해라.\n"
                    f"난이도: **'{difficulty}'**\n"
                    f"지침: {level_instruction}\n"
                    f"이번 시나리오의 핵심 소재: **[{selected_triggers}]**\n\n"
                    f"**[필수 출력 형식]**\n"
                    f"다음 3가지 항목만 포함해서 마크다운으로 작성해라:\n"
                    f"1. **사건 개요 (Background)**: 무엇이 문제인가? (구체적인 수치 포함)\n"
                    f"2. **유저 반응 (Reactions)**: 커뮤니티 여론, 주요 불만 내용, 시위 여부 등\n"
                    f"3. **현재 지표 (Current Status)**: 평점, 동접자 수, 환불 요청 건수 등\n\n"
                    f"**[절대 금지 사항]**\n"
                    f"- 게임사의 대응(공지, 보상, 해명 등)을 절대 미리 적지 마라.\n"
                    f"- 결과(Outcome)나 미래 예측을 적지 마라.\n"
                    f"- 오직 '발생한 상황'까지만 보고해라."
                )
                user_msg_public = "지금 발생한 위기 상황을 브리핑해. (형식 엄수)"
                public_text = clean_ai_response(call_ai_brain(provider, api_key, sys_msg_public, user_msg_public, temperature=current_temp))

                sys_msg_secret = (
                    "너는 게임 개발팀의 테크니컬 리드(TD)다. 발생한 위기 상황의 **기술적/내부적 진짜 원인**을 보고해라.\n"
                    "감정을 배제하고 **건조하고 논리적**으로 사실만 서술해라.\n"
                    "유저들의 추측이 맞을 수도 있고, 전혀 다른 엉뚱한 개발자 실수일 수도 있다."
                )
                user_msg_secret = f"[상황]\n{public_text}\n\n위 상황의 진짜 내부 원인(Secret)을 3줄 내외로 요약 보고해."
                secret_text = clean_ai_response(call_ai_brain(provider, api_key, sys_msg_secret, user_msg_secret, temperature=0.3))
                
                st.session_state.scenario_data = {"public": public_text, "cause": secret_text, "genre": genre}
                st.session_state.evaluation_result = None
                st.session_state.mentor_solution = None # 초기화
                st.rerun()

# [Phase 2 & 3] 대응 및 평가
else:
    left_col, right_col = st.columns(2, gap="large")
    
    with left_col:
        st.subheader("📡 상황 모니터링")
        st.error("🔥 **[Public] 현재 상황**")
        st.markdown(st.session_state.scenario_data['public'])
        st.write("")
        with st.expander("🔒 [1급 기밀] 진짜 원인 확인하기 (클릭)", expanded=False):
            st.warning("🤫 **[Secret] 내부 진실**")
            st.markdown(st.session_state.scenario_data['cause'])
        
        # [결과 리포트]
        if st.session_state.evaluation_result:
            res = st.session_state.evaluation_result
            cleaned_feedback = clean_ai_response(res.get('text', ''))
            score = parse_eval_score(cleaned_feedback)
            if score >= 80: result_box = st.success
            elif score >= 50: result_box = st.warning
            else: result_box = st.error
            result_box(f"📊 **대응 평가 결과** (점수: {score}점)")
            st.markdown(cleaned_feedback)

        # [멘토 솔루션 (탈주하기 버튼 결과)]
        if st.session_state.mentor_solution:
            st.markdown("---")
            st.info("💡 **멘토의 모범 답안 (Cheat Sheet)**")
            st.markdown(f"""
            <div class="mentor-box">
                <div class="header-text">👨‍🏫 멘토: "사표 쓰기 전에 이렇게 한번 해보세요."</div>
                <div class="content-text">{st.session_state.mentor_solution}</div>
            </div>
            """, unsafe_allow_html=True)

            # === [좌측] 상황판 및 결과 ===
            with left_col:
                # ... (상황판, 시크릿 박스, 평가 결과, 멘토 솔루션 코드 생략) ...

                # [기존 코드 아래에 추가] 
                # 평가 결과나 멘토 답안이 화면에 떠 있을 때만 주의 문구 표시
                if st.session_state.evaluation_result or st.session_state.mentor_solution:
                    st.write("") # 약간의 여백
                    st.info("ℹ️ **Notice:** AI의 평가와 제안은 참고용일 뿐 정답이 아닙니다. 실제 업무 적용 시에는 회사의 톤앤매너와 내부 규정에 따라 달라질 수 있으므로, 반드시 동료 및 유관부서와 논의하시기 바랍니다.")

    with right_col:
        st.subheader("⌨️ 작전 통제실")
        
        with st.form("response_form"):
            st.markdown("**1. 내부 조치 (Internal Action)**")
            action = st.text_area("action", height=100, label_visibility="collapsed", placeholder="예: 개발팀에 원복 요청...")
            
            st.markdown("**2. 유저 공지사항 (Public Notice)**")
            notice = st.text_area("notice", height=250, label_visibility="collapsed", placeholder="[공지] 사과드립니다...")
            
            # 버튼 2개 배치
            col_submit, col_giveup = st.columns(2)
            with col_submit:
                submit = st.form_submit_button("결재 및 미래 예측 (SIMULATE)", type="primary", use_container_width=True)
            with col_giveup:
                # [추가] 사표 쓰고 탈주하기 버튼
                give_up = st.form_submit_button("🏃‍♂️ 망했다...! 사표 쓰고 탈주하기 (멘토 찬스)", use_container_width=True)
            
        if st.button("🔄 초기화", use_container_width=True):
            st.session_state.scenario_data = {}
            st.session_state.evaluation_result = None
            st.session_state.mentor_solution = None
            st.rerun()
            
        # [로직 1] 정상 제출
        if submit:
            if not api_key: st.error("키 없음")
            elif not action or not notice: st.warning("내용 입력 필요")
            else:
                with st.spinner("🔮 미래의 타임라인을 계산 중입니다..."):
                    sys_msg = (
                        "너는 게임 운영의 신이자, 친절한 멘토다. CM(사용자)의 대응을 평가해라. "
                        "**[말투 가이드]**\n"
                        "- 딱딱한 보고서체(~함, ~임) 금지. **부드럽고 정중한 해요체(~입니다, ~하셨군요)** 사용.\n"
                        "- 사용자를 격려하면서도, 고쳐야 할 점은 명확하게 지적.\n\n"
                        "**[출력 형식]**\n"
                        "[[점수: 0~100]]\n[[리스크: 0~100]]\n\n"
                        "## 🔮 미래 시뮬레이션\n"
                        "**🌞 [희망편]:**\n**⛈️ [절망편]:**\n\n"
                        "## 📝 멘토의 피드백\n"
                        "**💬 총평:**\n**✍️ [첨삭 지도]:** (공지사항 문구 수정 제안)"
                    )
                    user_msg = f"""
                    [상황] {st.session_state.scenario_data['public']}
                    [진실] {st.session_state.scenario_data['cause']}
                    [조치] {action}
                    [공지] {notice}
                    """
                    text = clean_ai_response(call_ai_brain(provider, api_key, sys_msg, user_msg, temperature=current_temp))
                    st.session_state.evaluation_result = {"text": text}
                    st.session_state.mentor_solution = None # 멘토 답안은 숨김

                    # [수정] 로그 저장 시 전체 데이터 포함
                    st.session_state.history.append({
                        "Genre": st.session_state.scenario_data['genre'],
                        "Score": parse_eval_score(text),
                        "Risk": parse_risk_score(text),
                        "Crisis": st.session_state.scenario_data['public'], # 전체 내용
                        "User_Action": action, # 내 조치
                        "User_Notice": notice, # 내 공지
                        "Feedback": text
                    })
                    st.rerun()

        # [로직 2] 탈주하기 (멘토 찬스)
        if give_up:
            if not api_key: st.error("키 없음")
            else:
                with st.spinner("🏃‍♂️ 사표 수리 중... (멘토가 대신 수습하는 중)"):
                    sys_msg = (
                        "너는 업계 최고의 위기 관리 전문가다. 현재 상황과 내부 진실을 고려하여 **가장 이상적인 대응책(정답)**을 제시해라.\n"
                        "**[필수 포함 내용]**\n"
                        "1. **추천 내부 조치:** 개발팀/유관부서에 지시해야 할 현실적인 액션 아이템.\n"
                        "2. **추천 공지사항:** 유저의 분노를 잠재우고 신뢰를 회복할 수 있는 완벽한 사과문(또는 안내문) 초안."
                    )
                    user_msg = f"""
                    [현재 상황] {st.session_state.scenario_data['public']}
                    [내부 진실] {st.session_state.scenario_data['cause']}
                    
                    이 상황을 타개할 모범 답안을 작성해줘.
                    """
                    sol_text = clean_ai_response(call_ai_brain(provider, api_key, sys_msg, user_msg, temperature=0.5))
                    st.session_state.mentor_solution = sol_text
                    st.rerun()
