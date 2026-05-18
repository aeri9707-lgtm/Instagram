import streamlit as st
import pandas as pd
import io
from apify_helper import search_by_keyword, search_by_following, analyze_accounts, search_similar_creators
from dm_templates import classify_group, get_dm, get_group_label, GROUPS
from instagram_dm import login, logout, load_session, send_dms, get_inbox, get_thread, reply_to_thread, check_follow_status, follow_users, get_follower_counts
from nl_parser import parse_nl_query
from campaign_store import save_campaign, list_campaigns, load_campaign, delete_campaign, campaign_exists
from ui_components import (
    global_css, navbar_logo, platform_badge, hero_title,
    search_tips, gauge_row, score_bar,
    risk_badge, cost_banner, group_summary_card, profile_card,
)

st.set_page_config(
    page_title="인플루언서 DM 자동화",
    page_icon="📸",
    layout="wide",
)
st.markdown(global_css(), unsafe_allow_html=True)

# 저장된 세션 자동 복원 (처음 한 번만)
if not st.session_state.get("_ig_session_load_attempted"):
    st.session_state["_ig_session_load_attempted"] = True
    if not st.session_state.get("ig_logged_in"):
        _ok, _uname = load_session()
        if _ok:
            st.session_state["ig_logged_in"] = True
            st.session_state["ig_username"] = _uname

GROUP_COLORS = {
    "A": "#6c757d",
    "B": "#0d6efd",
    "C": "#198754",
    "D": "#fd7e14",
    "E": "#dc3545",
    "E+": "#6f42c1",
}


def fmt_followers(n: int) -> str:
    if n >= 100_000_000:
        s = f"{n / 100_000_000:.1f}"
        return s.rstrip("0").rstrip(".") + "억"
    if n >= 10_000:
        s = f"{n / 10_000:.1f}"
        return s.rstrip("0").rstrip(".") + "만"
    return f"{n:,}"


def _fmt_krw(n: int) -> str:
    if n >= 100_000_000:
        return f"{n / 100_000_000:.0f}억원"
    if n >= 10_000:
        return f"{n // 10_000:,}만원"
    return f"{n:,}원"


# 한국 시장 기준 게시물당 협업 단가 (원화)
# 출처: 한국 MCN 에이전시 관행 + 글로벌 CPM 환산 기준
_COST_TIERS = [
    (1_000_000, 20_000_000, 100_000_000),   # 100만+ → 2천만~1억
    (500_000,   8_000_000,  25_000_000),    # 50만+ → 800만~2,500만
    (100_000,   2_000_000,  8_000_000),     # 10만+ → 200만~800만
    (50_000,    700_000,    2_500_000),     # 5만+  → 70만~250만
    (10_000,    200_000,    700_000),       # 1만+  → 20만~70만
    (5_000,     70_000,     200_000),       # 5천+  → 7만~20만
    (1_000,     20_000,     70_000),        # 1천+  → 2만~7만
]


def estimate_cost_range(followers: int, is_verified: bool = False, er_ratio: float = 1.0) -> str:
    """
    팔로워 수 · 인증 여부 · ER 비율(실제ER÷기대ER)로 게시물당 협업 비용 범위 계산.
    er_ratio > 1 = 기대보다 높은 참여율 → 단가 상향
    """
    for min_f, lo, hi in _COST_TIERS:
        if followers >= min_f:
            mult = min(max(er_ratio, 0.6), 1.8)
            if is_verified:
                mult *= 1.2
            return f"{_fmt_krw(int(lo * mult))} ~ {_fmt_krw(int(hi * mult))}"
    return "-"



# ── 로그인 다이얼로그 ─────────────────────────────────────────────
@st.dialog("계정 설정", width="small")
def _login_dialog():
    _dl = st.session_state.get("ig_logged_in", False)
    _du = st.session_state.get("ig_username", "")
    if _dl:
        st.markdown(
            f"<div style='font-size:15px;font-weight:700;color:#111827;padding:4px 0 2px;'>"
            f"@{_du}</div>"
            f"<div style='font-size:12px;color:#10b981;margin-bottom:12px;'>● 연결됨</div>",
            unsafe_allow_html=True,
        )
        st.markdown("**브랜드명**")
        _bv = st.text_input(
            "브랜드명",
            value=st.session_state.get("brand_name", ""),
            placeholder="예: 라네즈, 이니스프리",
            key="brand_name_dialog",
            label_visibility="collapsed",
        )
        st.session_state["brand_name"] = _bv
        if _bv:
            st.caption(f"✅ DM에 **{_bv}** 자동 적용")
        st.divider()
        if st.button("로그아웃", use_container_width=True, key="dialog_logout_btn"):
            logout()
            st.session_state["ig_logged_in"] = False
            st.session_state["ig_username"] = ""
            st.rerun()
    else:
        st.markdown("**Instagram 로그인**")
        st.caption("로그인하면 age-restricted 계정 팔로워도 확인돼요.")
        _du2 = st.text_input("아이디", key="dialog_ig_user")
        _dp  = st.text_input("비밀번호", type="password", key="dialog_ig_pass")
        if st.button("로그인", type="primary", use_container_width=True, key="dialog_login_btn"):
            if _du2 and _dp:
                with st.spinner("로그인 중..."):
                    ok, msg = login(_du2, _dp)
                if ok:
                    st.session_state["ig_logged_in"] = True
                    st.session_state["ig_username"] = _du2
                    st.rerun()
                else:
                    st.error(msg)
            else:
                st.warning("아이디와 비밀번호를 입력해주세요.")


# ── 네비게이션 바 (로고 + 우상단 로그인) ─────────────────────────
_nav_logo, _nav_space, _nav_login = st.columns([2, 8, 0.6])

with _nav_logo:
    st.markdown(navbar_logo(), unsafe_allow_html=True)

with _nav_login:
    _is_logged = st.session_state.get("ig_logged_in", False)
    _uname     = st.session_state.get("ig_username", "")
    _btn_label = _uname[0].upper() if _is_logged and _uname else "👤"
    if st.button(_btn_label, key="login_toggle_btn", use_container_width=True):
        _login_dialog()

st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

# ── 플랫폼 배지 ──────────────────────────────────────────────────────
st.markdown(platform_badge(), unsafe_allow_html=True)

# ── ① 검색 방식 탭 (AI 우선) ─────────────────────────────────────
tab_ai, tab_following, tab_similar = st.tabs([
    "🔍 크리에이터 검색", "🏢 브랜드 역추적", "🔄 유사 계정 탐색"
])

# ── ② 공통 지역 필터 (탭 바로 아래, 인라인) ─────────────────────
_rf, _spacer_col = st.columns([3, 5])
with _rf:
    region_setting = st.radio(
        "",
        options=["전체", "한국", "해외"],
        horizontal=True,
        label_visibility="collapsed",
        key="region_setting",
        help="한국=한국 계정 우선 / 해외=해외 계정만",
    )
st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)


with tab_following:
    st.markdown("**기준 계정**(브랜드·인플루언서)의 게시물에서 인플루언서를 발굴해요.")
    col1, col2 = st.columns([4, 1])
    with col1:
        fw_input = st.text_input("기준 계정명 (@없이 입력)", placeholder="예: laneige_kr, innisfree_official", key="fw_input")
    with col2:
        fw_limit = st.number_input("수집 수", 10, 50, 30, key="fw_limit")

    if st.button("👥 팔로잉 탐색", type="primary", key="fw_btn", use_container_width=True):
        if not fw_input.strip():
            st.warning("계정명을 입력해주세요.")
        else:
            status2 = st.empty()
            bar2 = st.progress(0)
            def fw_progress(msg):
                status2.info(f"⏳ {msg}")
                bar2.progress(40 if "1/2" in msg else 75)
            profiles_raw, err = search_by_following(fw_input.strip(), fw_limit, fw_progress)
            bar2.progress(100)
            if err:
                status2.error(err)
            else:
                status2.success(f"@{fw_input.strip()} 탐색 완료 — {len(profiles_raw)}개 계정 발견!")
                st.session_state["profiles"] = profiles_raw
                st.session_state["search_label"] = fw_input.strip()

with tab_similar:
    st.markdown("계정 하나를 입력하면 **비슷한 계정**을 자동 발굴해요. (relatedProfiles + 해시태그 기반)")
    col1, col2 = st.columns([4, 1])
    with col1:
        sim_input = st.text_input("기준 계정명 (@없이)", placeholder="예: ddo_dam, _sseunnii", key="sim_input")
    with col2:
        sim_limit = st.number_input("최대 결과 수", 5, 30, 15, key="sim_limit")

    if st.button("🔄 유사 계정 탐색", type="primary", key="sim_btn", use_container_width=True):
        if not sim_input.strip():
            st.warning("계정명을 입력해주세요.")
        else:
            status3 = st.empty()
            bar3 = st.progress(0)
            _sim_steps = {"1/4": 20, "2/4": 45, "3/4": 70, "4/4": 90}
            def sim_progress(msg):
                status3.info(f"⏳ {msg}")
                for k, v in _sim_steps.items():
                    if k in msg:
                        bar3.progress(v)
                        break
            similar_raw, err = search_similar_creators(sim_input.strip(), sim_limit, sim_progress)
            bar3.progress(100)
            if err:
                status3.error(err)
            elif not similar_raw:
                status3.warning("유사 계정을 찾지 못했어요.")
            else:
                status3.success(f"@{sim_input.strip()} 기준 유사 계정 {len(similar_raw)}개 발견!")
                st.session_state["profiles"] = similar_raw
                st.session_state["search_label"] = f"{sim_input.strip()} 유사 계정"

                sim_df_rows = []
                for p in similar_raw:
                    sim_df_rows.append({
                        "계정명":   p["username"],
                        "실명/채널명": p["full_name"],
                        "팔로워 수": fmt_followers(p["followers"]),
                        "유사도":   f"{p.get('유사도', 0)}점",
                        "카테고리": p.get("category", ""),
                        "인증":     "✅" if p.get("is_verified") else "",
                        "예상 단가": estimate_cost_range(p["followers"], p.get("is_verified", False)),
                        "프로필 URL": p["profile_url"],
                    })
                sim_df = pd.DataFrame(sim_df_rows)
                st.dataframe(
                    sim_df,
                    use_container_width=True,
                    column_config={
                        "프로필 URL": st.column_config.LinkColumn("프로필"),
                        "유사도": st.column_config.TextColumn("유사도", width="small"),
                    },
                    hide_index=True,
                )

with tab_ai:
    st.markdown(hero_title(), unsafe_allow_html=True)
    # ── 검색 입력 (중앙 정렬) ──────────────────────────────────────
    # 칩 클릭 시 _ai_query_pending에 저장 → 위젯 생성 전에 적용
    if "_ai_query_pending" in st.session_state:
        st.session_state["ai_query"] = st.session_state.pop("_ai_query_pending")

    _, _ai_c, _ = st.columns([1, 6, 1])
    with _ai_c:
        ai_query = st.text_area(
            "",
            placeholder="찾고 싶은 인플루언서를 설명해주세요.\n예시) '팔로워 1만~5만의 K-뷰티 스킨케어 전문가'",
            key="ai_query",
            height=90,
            label_visibility="collapsed",
        )

    # ── 예시 chip — 클릭하면 검색창에 세팅 (2줄) ───────────────────
    _CHIPS = [
        "20대 뷰티 마이크로인플루언서",
        "한국 육아 맘 팔로워 5만 이상",
        "패션 코디 나노 인플루언서",
        "다이어트 헬스 매크로 계정",
        "요리 먹방 한국 인플루언서",
    ]
    st.markdown("<div style='text-align:center;margin:6px 0 2px;font-size:11px;color:#b07090;'>예시 →</div>", unsafe_allow_html=True)
    _sp1, _ch1, _ch2, _ch3, _sp2 = st.columns([1, 2, 2, 2, 1])
    for _ci, (_cc, _cl) in enumerate(zip([_ch1, _ch2, _ch3], _CHIPS[:3])):
        with _cc:
            if st.button(_cl, key=f"ai_chip_{_ci}", use_container_width=True):
                st.session_state["_ai_query_pending"] = _cl
                st.rerun()
    _sp3, _ch4, _ch5, _sp4 = st.columns([2, 2, 2, 2])
    for _ci, (_cc, _cl) in enumerate(zip([_ch4, _ch5], _CHIPS[3:])):
        with _cc:
            if st.button(_cl, key=f"ai_chip_{_ci+3}", use_container_width=True):
                st.session_state["_ai_query_pending"] = _cl
                st.rerun()

    # ── 팁 섹션 ───────────────────────────────────────────────────
    st.markdown(search_tips(), unsafe_allow_html=True)

    ai_limit = st.number_input("최대 결과 수", 5, 50, 20, key="ai_limit")

    if st.button("🔍 크리에이터 검색", type="primary", key="ai_btn", use_container_width=True):
        if not ai_query.strip():
            st.warning("검색 요청을 입력해주세요.")
        else:
            parsed = parse_nl_query(ai_query.strip())
            tags = parsed["detected_tags"]

            # 파싱 결과 미리보기
            tag_html = " ".join(
                f"<span style='background:#e8f4fd;color:#0d6efd;padding:3px 10px;"
                f"border-radius:20px;font-size:13px;margin:2px;display:inline-block;'>{t}</span>"
                for t in tags
            ) if tags else "<span style='color:#999'>자동 감지된 조건 없음 — 원문 키워드로 검색해요</span>"
            st.markdown(f"**감지된 조건:** {tag_html}", unsafe_allow_html=True)
            _hi_label = "무제한" if parsed["follower_max"] > 10_000_000 else f"{parsed['follower_max']:,}"
            st.caption(f"검색 키워드: **{parsed['keyword']}** | 팔로워 범위: {parsed['follower_min']:,} ~ {_hi_label}")

            status_ai = st.empty()
            bar_ai = st.progress(0)
            def ai_progress(msg):
                status_ai.info(f"⏳ {msg}")
                bar_ai.progress(50)

            profiles_raw, err = search_by_keyword(parsed["keyword"], ai_limit, ai_progress)
            bar_ai.progress(100)

            if err:
                status_ai.error(err)
            else:
                # 팔로워 범위 필터 적용
                f_min, f_max = parsed["follower_min"], parsed["follower_max"]
                filtered = [p for p in profiles_raw if f_min <= p["followers"] <= f_max]

                # 지역 필터 (AI가 감지한 경우에만)
                if parsed["region"] != "전체":
                    filtered = [p for p in filtered if p.get("region", "해외") == parsed["region"]]

                # 팔로워 0 계정 보완 (로그인 시)
                zero_users = [p["username"] for p in filtered if p["followers"] == 0]
                if zero_users and st.session_state.get("ig_logged_in"):
                    status_ai.info(f"⏳ 팔로워 미확인 {len(zero_users)}개 계정 보완 중...")
                    real_counts = get_follower_counts(zero_users)
                    for p in filtered:
                        if p["username"] in real_counts:
                            p["followers"] = real_counts[p["username"]]
                    filtered = [p for p in filtered if f_min <= p["followers"] <= f_max]

                status_ai.success(f"'{ai_query.strip()}' 검색 완료 — {len(filtered)}개 계정 발견!")
                st.session_state["profiles"] = filtered
                st.session_state["search_label"] = ai_query.strip()

st.divider()

# ── ③ 결과 출력 ───────────────────────────────────────────────────
if "profiles" in st.session_state and st.session_state["profiles"]:

    active_region = region_setting
    follower_filter = st.multiselect(
        "팔로워 그룹 필터 (선택 안 하면 전체 표시)",
        options=list(GROUPS.keys()),
        format_func=lambda k: f"그룹 {k}  ({GROUPS[k]['label']})",
    )

    rows = []
    for p in st.session_state["profiles"]:
        group  = classify_group(p["followers"])
        region = p.get("region", "해외")
        if follower_filter and group not in follower_filter:
            continue
        if active_region != "전체" and region != active_region:
            continue
        dm_text = get_dm(group, p["username"], p.get("category", ""))
        brand = st.session_state.get("brand_name", "")
        if brand:
            dm_text = dm_text.replace("[브랜드명]", brand)
        rows.append({
            "지역":       region,
            "그룹":       f"그룹 {group}",
            "그룹명":     get_group_label(group),
            "계정명":     p["username"],
            "실명/채널명": p["full_name"],
            "팔로워":     p["followers"],
            "팔로워 수":  fmt_followers(p["followers"]),
            "예상 단가":  estimate_cost_range(p["followers"], p.get("is_verified", False)),
            "카테고리":   p["category"],
            "인증":       "✅" if p["is_verified"] else "",
            "프로필 URL": p["profile_url"],
            "DM 문구":    dm_text,
        })

    label = st.session_state.get("search_label", "")

    if not rows:
        st.info("조건에 맞는 계정이 없어요. 지역 설정이나 키워드를 바꿔보세요.")
        st.stop()

    df = pd.DataFrame(rows)

    # ── 캠페인 저장 ──────────────────────────────────────────────────
    with st.expander("캠페인으로 저장", expanded=False):
        _default_name = label or "캠페인"
        _camp_name = st.text_input(
            "캠페인 이름",
            value=_default_name,
            key="camp_name_input",
            placeholder="예: 2024 뷰티 캠페인 A",
        )
        _overwrite_warn = campaign_exists(_camp_name) if _camp_name else False
        if _overwrite_warn:
            st.warning(f"'{_camp_name}' 캠페인이 이미 있어요. 저장하면 덮어써요.")
        if st.button("💾 저장", key="camp_save_btn", type="primary"):
            _name_clean = (_camp_name or "").strip()
            if _name_clean:
                save_campaign(_name_clean, st.session_state["profiles"], label)
                st.success(f"'{_name_clean}' 캠페인으로 저장했어요! ({len(st.session_state['profiles'])}개 계정)")
            else:
                st.warning("캠페인 이름을 입력해주세요.")

    # 팔로우 상태 확인 (로그인 시에만)
    if st.session_state.get("ig_logged_in"):
        if st.button("🔍 팔로우 상태 확인", help="계정 수에 따라 시간이 걸릴 수 있어요."):
            usernames = df["계정명"].tolist()
            with st.spinner(f"{len(usernames)}개 계정 팔로우 상태 확인 중..."):
                status_map = check_follow_status(usernames)
            st.session_state["follow_status"] = status_map

    FOLLOW_OPTIONS = ["🤝 맞팔", "👤 팔로워", "➡️ 팔로잉", "➖ 없음"]

    if "follow_status" in st.session_state:
        df["팔로우 상태"] = df["계정명"].map(st.session_state["follow_status"]).fillna("➖ 없음")
        follow_filter = st.multiselect(
            "팔로우 상태 필터 (선택 안 하면 전체 표시)",
            options=FOLLOW_OPTIONS,
            key="follow_filter",
        )
        if follow_filter:
            df = df[df["팔로우 상태"].isin(follow_filter)]

    region_badge = {"한국": "🇰🇷 한국", "해외": "🌐 해외", "전체": "🌏 전체"}.get(active_region, "")
    st.subheader(f"결과 — {label} {region_badge} ({len(df)}개 계정)")

    # 그룹별 요약 카드
    group_counts = df["그룹"].value_counts().sort_index()
    cols = st.columns(max(len(group_counts), 1))
    for i, (grp, cnt) in enumerate(group_counts.items()):
        code = str(grp).replace("그룹 ", "")
        color = GROUP_COLORS.get(code, "#999")
        with cols[i]:
            st.markdown(
                group_summary_card(code, cnt, get_group_label(code), color),
                unsafe_allow_html=True,
            )

    st.divider()

    result_tab1, result_tab2, result_tab3, result_tab4 = st.tabs(["📋 전체 리스트", "✉️ 그룹별 DM 문구", "📤 DM 발송", "📊 릴스 분석"])

    with result_tab1:
        _view = st.radio(
            "보기 방식",
            ["📋 테이블", "🃏 카드"],
            horizontal=True,
            label_visibility="collapsed",
            key="result_view_mode",
        )
        disp = ["계정명", "실명/채널명", "팔로워 수", "예상 단가", "그룹명", "지역", "카테고리", "인증", "프로필 URL"]
        if "팔로우 상태" in df.columns:
            disp = ["팔로우 상태"] + disp
        if _view == "📋 테이블":
            st.dataframe(
                df[disp],
                use_container_width=True,
                hide_index=True,
                column_config={"프로필 URL": st.column_config.LinkColumn("프로필")},
            )
        else:
            _card_profiles = st.session_state.get("profiles", [])
            _profile_lookup = {p["username"]: p for p in _card_profiles}
            for row in rows:
                p = _profile_lookup.get(row["계정명"], {})
                if p:
                    st.markdown(
                        profile_card(p, row.get("DM 문구", ""), row.get("예상 단가", "")),
                        unsafe_allow_html=True,
                    )

    with result_tab2:
        for grp in sorted(df["그룹"].unique()):
            code = str(grp).replace("그룹 ", "")
            color = GROUP_COLORS.get(code, "#999")
            grp_df = df[df["그룹"] == grp]
            st.markdown(
                f"<h4 style='color:{color};'>그룹 {code} — {get_group_label(code)} ({len(grp_df)}명)</h4>",
                unsafe_allow_html=True,
            )
            sample = grp_df.iloc[0]
            with st.expander(f"DM 문구 미리보기 (샘플: @{sample['계정명']})", expanded=True):
                st.text_area("", value=sample["DM 문구"], height=190, key=f"dm_{code}")
                st.caption(f"이 그룹 {len(grp_df)}명 전체에 동일 형식으로 적용돼요.")
            st.dataframe(
                grp_df[["계정명", "실명/채널명", "팔로워 수", "예상 단가", "프로필 URL"]],
                use_container_width=True,
                hide_index=True,
                column_config={"프로필 URL": st.column_config.LinkColumn("프로필")},
            )
            st.divider()

    # ── DM 발송 탭 ────────────────────────────────────────────────
    with result_tab3:
        if not st.session_state.get("ig_logged_in"):
            st.warning("👈 왼쪽 사이드바에서 Instagram 로그인을 먼저 해주세요.")
        else:
            st.markdown(f"**로그인 계정:** `{st.session_state['ig_username']}`")
            st.caption("발송할 계정을 선택하고 DM 발송 버튼을 눌러주세요. 계정 보호를 위해 발송 간격이 자동 적용돼요.")

            select_all = st.checkbox("전체 선택", key="select_all_checkbox")

            df_select = df[["계정명", "실명/채널명", "팔로워 수", "예상 단가", "그룹", "DM 문구"]].copy()
            df_select.insert(0, "발송", select_all)

            edited = st.data_editor(
                df_select,
                column_config={
                    "발송": st.column_config.CheckboxColumn("발송", default=False),
                },
                hide_index=True,
                use_container_width=True,
                key=f"dm_select_editor_{select_all}",
            )

            selected = edited[edited["발송"] == True]
            st.caption(f"선택된 계정: {len(selected)}개")

            if len(selected) > 30:
                st.warning("⚠️ 하루 30건 초과 시 계정 제한 위험이 있어요. 30건 이하로 선택해주세요.")

            btn_col1, btn_col2 = st.columns(2)

            with btn_col1:
                if st.button(
                    f"📤 선택한 {len(selected)}개 계정에 DM 발송",
                    type="primary",
                    disabled=len(selected) == 0,
                    use_container_width=True,
                ):
                    targets = [
                        {"username": row["계정명"], "dm_text": row["DM 문구"]}
                        for _, row in selected.iterrows()
                    ]
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    def on_progress(i, total, username):
                        progress_bar.progress((i + 1) / total)
                        status_text.info(f"⏳ ({i+1}/{total}) @{username} DM 발송 중...")

                    results = send_dms(targets, on_progress)
                    progress_bar.progress(1.0)
                    success = sum(1 for r in results if "성공" in r["status"])
                    fail = len(results) - success
                    status_text.success(f"완료! 성공 {success}건 / 실패 {fail}건")
                    st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)

            with btn_col2:
                if st.button(
                    f"➕ 선택한 {len(selected)}개 계정 팔로우",
                    disabled=len(selected) == 0,
                    use_container_width=True,
                ):
                    usernames = selected["계정명"].tolist()
                    progress_bar2 = st.progress(0)
                    status_text2 = st.empty()

                    def on_follow_progress(i, total, username):
                        progress_bar2.progress((i + 1) / total)
                        status_text2.info(f"⏳ ({i+1}/{total}) @{username} 팔로우 중...")

                    follow_results = follow_users(usernames, on_follow_progress)
                    progress_bar2.progress(1.0)
                    success2 = sum(1 for r in follow_results if "완료" in r["status"])
                    fail2 = len(follow_results) - success2
                    status_text2.success(f"완료! 팔로우 성공 {success2}건 / 실패 {fail2}건")
                    st.dataframe(pd.DataFrame(follow_results), use_container_width=True, hide_index=True)

    # ── 릴스 분석 탭 ─────────────────────────────────────────────
    with result_tab4:
        st.caption("계정의 최근 게시물을 분석해 시딩·공구 적합도, 팬덤 강도, 위험도를 점수화해요.")
        st.caption("⚠️ 계정당 Apify 크레딧이 추가 소모돼요. 필요한 계정만 선택하세요.")

        analysis_usernames = st.multiselect(
            "분석할 계정 선택",
            options=df["계정명"].tolist(),
            key="analysis_select",
        )
        posts_limit = st.slider("계정당 최근 게시물 수 (많을수록 정확, 크레딧 소모↑)", 10, 50, 30, key="posts_limit")

        if st.button("📊 선택한 계정 종합 분석", type="primary",
                     disabled=len(analysis_usernames) == 0, use_container_width=True):
            analysis_bar = st.progress(0)
            analysis_status = st.empty()

            def on_analysis_progress(i, total, uname):
                analysis_bar.progress((i + 1) / total)
                analysis_status.info(f"⏳ ({i+1}/{total}) @{uname} 분석 중...")

            profile_map = {p["username"]: p for p in st.session_state["profiles"]}
            _results, _errors = analyze_accounts(
                analysis_usernames, posts_limit, on_analysis_progress, profile_map
            )
            analysis_bar.progress(1.0)
            for e in _errors:
                st.warning(e)
            if _results:
                analysis_status.success(f"분석 완료! {len(_results)}개 계정")
                st.session_state["analysis_results"] = _results

        if st.session_state.get("analysis_results"):
            _res = st.session_state["analysis_results"]
            follower_map = dict(zip(df["계정명"], df["팔로워"]))

            # ── 종합 점수 비교표 ──────────────────────────────────
            st.subheader("📊 종합 점수 비교")

            def _score_badge(score: int) -> str:
                if score >= 75: return f"🟢 {score}"
                if score >= 50: return f"🟡 {score}"
                return f"🔴 {score}"

            summary_rows = []
            for r in _res:
                interval = r.get("평균 포스팅 주기(일)")
                summary_rows.append({
                    "계정명":         r["계정명"],
                    "팔로워":         fmt_followers(follower_map.get(r["계정명"], 0)),
                    "평균 조회수":    fmt_followers(r["평균 조회수"]),
                    "참여 추세":      r.get("참여 추세", ""),
                    "댓글률":         f"{r['댓글률(%)']:.2f}%",
                    "광고 비율":      f"{r['광고 비율(%)']:.0f}%",
                    "광고 반응 저하": f"{r.get('광고 반응 저하(%)', 0):.0f}%",
                    "유령 팔로워":    f"{r.get('유령 팔로워 추정(%)', 0):.0f}%",
                    "포스팅 주기":    f"{interval}일" if interval else "-",
                    "🎯 시딩":        _score_badge(r["시딩 점수"]),
                    "🛒 공구":        _score_badge(r["공구 적합도"]),
                    "💳 구매전환":    _score_badge(r["구매전환 점수"]),
                    "❤️ 팬덤":        _score_badge(r["팬덤 점수"]),
                    "위험도":         r["위험도"],
                    "추천 카테고리":  r["추천 카테고리"],
                    "💰 정밀 단가 추정": estimate_cost_range(
                        follower_map.get(r["계정명"], 0),
                        False,
                        (r.get("실제 참여율(%)", 0) / r["기대 참여율(%)"])
                        if r.get("기대 참여율(%)", 0) > 0 else 1.0,
                    ),
                })
            st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

            # ── 개별 상세 분석 카드 ───────────────────────────────
            st.subheader("📋 개별 계정 상세 분석")
            for r in _res:
                with st.expander(
                    f"@{r['계정명']}  |  시딩 {r['시딩 점수']}점  공구 {r['공구 적합도']}점  {r['위험도']}",
                    expanded=False,
                ):
                    # ── 종합 점수 + 단가 ──────────────────────────
                    _er_r = (
                        r.get("실제 참여율(%)", 0) / r["기대 참여율(%)"]
                        if r.get("기대 참여율(%)", 0) > 0 else 1.0
                    )
                    _cost = estimate_cost_range(
                        follower_map.get(r["계정명"], 0), False, _er_r
                    )
                    st.markdown(
                        cost_banner(_cost, "한국 시장 기준 · ER 반영"),
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        gauge_row({
                            "🎯 시딩": r["시딩 점수"],
                            "🛒 공구": r["공구 적합도"],
                            "💳 구매전환": r["구매전환 점수"],
                            "❤️ 팬덤": r["팬덤 점수"],
                        }),
                        unsafe_allow_html=True,
                    )
                    _bars = "".join([
                        score_bar(r["시딩 점수"], "🎯 시딩"),
                        score_bar(r["공구 적합도"], "🛒 공구"),
                        score_bar(r["구매전환 점수"], "💳 구매전환"),
                        score_bar(r["팬덤 점수"], "❤️ 팬덤"),
                    ])
                    st.markdown(
                        f"<div style='padding:0 8px;margin-bottom:4px;'>{_bars}</div>",
                        unsafe_allow_html=True,
                    )

                    st.divider()

                    # ── 도달력 지표 ────────────────────────────────
                    st.caption("📡 도달력")
                    m1, m2, m3, m4, m5 = st.columns(5)
                    m1.metric("평균 조회수", fmt_followers(r["평균 조회수"]))
                    m2.metric("최고 조회수", fmt_followers(r["최고 조회수"]))
                    m3.metric("조회수 편차", f"{r['조회수 편차']:.1f}x",
                              help="최고÷평균. 2이하=안정, 10이상=바이럴 원툴")
                    m4.metric("10만+ 릴스", f"{r['10만+ 릴스']}개")
                    m5.metric("100만+ 릴스", f"{r['100만+ 릴스']}개")

                    # ── 참여 지표 ──────────────────────────────────
                    st.caption("💬 참여 품질")
                    e1, e2, e3, e4 = st.columns(4)
                    e1.metric("댓글률", f"{r['댓글률(%)']:.2f}%",
                              help="0.1%=평균, 0.3%=우수, 0.5%+=팬덤")
                    e2.metric("참여율", f"{r['참여율(%)']:.2f}%",
                              help="(좋아요+댓글)÷조회수")
                    e3.metric("평균 좋아요", fmt_followers(r["평균 좋아요"]))
                    e4.metric("평균 댓글",   fmt_followers(r["평균 댓글"]))

                    # ── 참여 추세 ──────────────────────────────────
                    if r.get("참여 추세"):
                        st.caption("📈 참여 추세 (최근 5개 vs 이전 10개 비교)")
                        t1, t2 = st.columns(2)
                        t1.metric("추세", r["참여 추세"])
                        interval = r.get("평균 포스팅 주기(일)")
                        t2.metric("평균 포스팅 주기",
                                  f"{interval}일" if interval else "-",
                                  help="짧을수록 활성 계정. 7일 이하=활발, 14일 이상=비활성")

                    st.divider()

                    # ── 팔로워 퀄리티 ─────────────────────────────
                    st.caption("👥 팔로워 퀄리티 (Buffer 2024 기준)")
                    fq1, fq2, fq3, fq4 = st.columns(4)
                    fq1.metric("기대 참여율", f"{r.get('기대 참여율(%)', 0):.1f}%",
                               help="팔로워 규모 대비 업계 평균")
                    fq2.metric("실제 참여율", f"{r.get('실제 참여율(%)', 0):.2f}%")
                    ghost = r.get("유령 팔로워 추정(%)", 0)
                    fq3.metric("유령 팔로워 추정", f"{ghost:.0f}%",
                               help="실제ER÷기대ER 괴리. 40%+=주의, 60%+=위험")
                    rreach = r.get("릴스 도달률(%)", 0)
                    ereach = r.get("기대 도달률(%)", 0)
                    fq4.metric("릴스 도달률",
                               f"{rreach:.1f}% / 기대 {ereach:.0f}%",
                               help="views÷followers. 기대치 30% 미만이면 팔로워 품질 의심")

                    cl_ratio = r.get("댓글/좋아요 비율(%)", 0)
                    ff_ratio = r.get("팔로워/팔로잉", 0)
                    fq5, fq6 = st.columns(2)
                    fq5.metric("댓글/좋아요 비율", f"{cl_ratio:.1f}%",
                               help="정상 3~10%. 0.3% 미만=좋아요 구매 의심")
                    fq6.metric("팔로워/팔로잉 비율", f"{ff_ratio:.0f}:1",
                               help="10:1 이상이면 건강. 팔로잉 5000+ 계정은 팔언팔 패턴 의심")

                    st.divider()

                    # ── 광고 vs 일반 성과 비교 ────────────────────
                    st.caption("📢 광고 vs 일반 콘텐츠 성과 (가장 중요한 지표)")
                    ad_er   = r.get("광고 콘텐츠 ER(%)", 0)
                    org_er  = r.get("일반 콘텐츠 ER(%)", 0)
                    penalty = r.get("광고 반응 저하(%)", 0)
                    a1, a2, a3, a4 = st.columns(4)
                    a1.metric("광고 게시물 비율", f"{r['광고 비율(%)']:.0f}%",
                              help="20~30%=건강, 50%+=피로도, 70%+=광고계정")
                    a2.metric("일반 콘텐츠 ER",   f"{org_er:.2f}%")
                    a3.metric("광고 콘텐츠 ER",   f"{ad_er:.2f}%")
                    a4.metric("광고 반응 저하",    f"{penalty:.0f}%",
                              help="광고가 일반 대비 반응이 낮은 정도. 30%+=피로 감지")
                    emv = r.get("게시물당 EMV(원)", 0)
                    if emv:
                        st.caption(f"💰 게시물 1개당 예상 미디어 가치(EMV): **{emv:,}원**  "
                                   f"*(Ayzenberg 인덱스 기반)*")

                    # ── 댓글 품질 ──────────────────────────────────
                    if r["분석 댓글 수"] > 0:
                        st.divider()
                        st.caption(f"💬 댓글 품질 분석 ({r['분석 댓글 수']}개 기준)")
                        cq1, cq2 = st.columns(2)
                        cq1.metric("🛍️ 구매 의도 댓글", f"{r['구매의도 댓글(%)']:.1f}%",
                                   help="'어디서 사요?', '공구 언제?', '링크' 등")
                        cq2.metric("⚠️ 저품질 댓글",    f"{r['저품질 댓글(%)']:.1f}%",
                                   help="이모지만, 3자 이하, 반복 패턴")

                    # ── 위험도 배지 + 위험 신호 ────────────────────
                    st.markdown(
                        f"위험도: {risk_badge(r['위험도'])}",
                        unsafe_allow_html=True,
                    )
                    if r["위험 신호"]:
                        st.warning("⚠️ 위험 신호: " + " · ".join(r["위험 신호"]))

                    st.divider()
                    st.markdown("**🤖 AI 분석 리포트**")
                    st.info(r["AI 리포트"])
                    st.success(f"✅ 추천 제품 카테고리: **{r['추천 카테고리']}**")

            # ── CSV 다운로드 ──────────────────────────────────────
            _export_cols = [
                "계정명", "분석 게시물 수", "릴스/영상 수",
                "평균 조회수", "최고 조회수", "조회수 편차",
                "10만+ 릴스", "50만+ 릴스", "100만+ 릴스",
                "평균 좋아요", "평균 댓글",
                "댓글률(%)", "참여율(%)", "광고 비율(%)",
                "참여 추세", "평균 포스팅 주기(일)",
                "기대 참여율(%)", "실제 참여율(%)", "유령 팔로워 추정(%)",
                "릴스 도달률(%)", "기대 도달률(%)",
                "댓글/좋아요 비율(%)", "팔로워/팔로잉",
                "광고 콘텐츠 ER(%)", "일반 콘텐츠 ER(%)", "광고 반응 저하(%)",
                "게시물당 EMV(원)",
                "구매의도 댓글(%)", "저품질 댓글(%)", "분석 댓글 수",
                "시딩 점수", "공구 적합도", "구매전환 점수", "팬덤 점수",
                "위험도", "추천 카테고리", "AI 리포트",
            ]
            _df_res = pd.DataFrame(_res)
            _adf = _df_res[[c for c in _export_cols if c in _df_res.columns]]
            buf2 = io.StringIO()
            _adf.to_csv(buf2, index=False, encoding="utf-8-sig")
            st.download_button(
                "📥 분석 결과 CSV 다운로드",
                data=buf2.getvalue().encode("utf-8-sig"),
                file_name="인플루언서_종합분석.csv",
                mime="text/csv",
            )

    # ── CSV 다운로드 ──────────────────────────────────────────────
    st.divider()
    st.subheader("📥 발송 리스트 다운로드")
    buf = io.StringIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    st.download_button(
        label="CSV 다운로드 (엑셀에서 바로 열립니다)",
        data=buf.getvalue().encode("utf-8-sig"),
        file_name=f"인플루언서_DM리스트_{label}.csv",
        mime="text/csv",
        type="primary",
        use_container_width=True,
    )
    st.caption("DM 문구 + 팔로워 그룹 분류 + 프로필 링크가 모두 포함돼요.")

# ── ④ 캠페인 관리 & 비교 ──────────────────────────────────────────
st.divider()
st.subheader("📁 캠페인")

_all_camps = list_campaigns()
if not _all_camps:
    st.caption("아직 저장된 캠페인이 없어요.")
else:
    for _c in _all_camps:
        _cc1, _cc2, _cc3 = st.columns([5, 1, 1])
        with _cc1:
            st.markdown(
                f"<div style='padding:6px 0;font-size:13px;'>"
                f"<strong>{_c['label']}</strong>"
                f"<span style='color:#6b7280;font-size:12px;margin-left:8px;'>{_c['count']}개 · {_c['saved_at']}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with _cc2:
            if st.button("불러오기", key=f"load_camp_{_c['name']}", use_container_width=True):
                _loaded = load_campaign(_c["name"])
                if _loaded:
                    st.session_state["profiles"] = _loaded
                    st.session_state["search_label"] = _c["label"]
                    st.rerun()
        with _cc3:
            if st.button("삭제", key=f"del_camp_{_c['name']}", use_container_width=True):
                delete_campaign(_c["name"])
                st.rerun()

if len(_all_camps) < 2:
    st.caption("캠페인을 2개 이상 저장하면 비교할 수 있어요.")
else:
    _camp_names = [c["name"] for c in _all_camps]
    _camp_labels = {c["name"]: f"{c['label']} ({c['count']}개, {c['saved_at']})" for c in _all_camps}

    _cmp_col1, _cmp_col2 = st.columns(2)
    with _cmp_col1:
        _sel_a = st.selectbox("캠페인 A", _camp_names, format_func=lambda n: _camp_labels[n], key="cmp_a")
    with _cmp_col2:
        _default_b = _camp_names[1] if len(_camp_names) > 1 else _camp_names[0]
        _sel_b = st.selectbox("캠페인 B", _camp_names,
                              index=min(1, len(_camp_names)-1),
                              format_func=lambda n: _camp_labels[n], key="cmp_b")

    if st.button("비교하기", key="cmp_btn", type="primary"):
        _prof_a = load_campaign(_sel_a)
        _prof_b = load_campaign(_sel_b)

        def _camp_stats(profiles: list[dict]) -> dict:
            if not profiles:
                return {}
            followers = [p.get("followers", 0) for p in profiles]
            verified = sum(1 for p in profiles if p.get("is_verified"))
            from dm_templates import classify_group
            groups: dict[str, int] = {}
            for p in profiles:
                g = classify_group(p.get("followers", 0))
                groups[g] = groups.get(g, 0) + 1
            return {
                "계정 수": len(profiles),
                "평균 팔로워": int(sum(followers) / len(followers)) if followers else 0,
                "최대 팔로워": max(followers) if followers else 0,
                "인증 계정": verified,
                "주요 그룹": max(groups, key=lambda k: groups[k]) if groups else "-",
            }

        _stats_a = _camp_stats(_prof_a)
        _stats_b = _camp_stats(_prof_b)

        _label_a = _camp_labels.get(_sel_a, _sel_a)
        _label_b = _camp_labels.get(_sel_b, _sel_b)

        _hdr, _col_a, _col_b = st.columns([2, 2, 2])
        _hdr.markdown("**항목**")
        _col_a.markdown(f"**{_sel_a}**")
        _col_b.markdown(f"**{_sel_b}**")

        for _key in ["계정 수", "평균 팔로워", "최대 팔로워", "인증 계정", "주요 그룹"]:
            _r, _ca, _cb = st.columns([2, 2, 2])
            _va = _stats_a.get(_key, "-")
            _vb = _stats_b.get(_key, "-")
            _r.write(_key)
            if isinstance(_va, int) and isinstance(_vb, int) and _key != "인증 계정":
                _ca.write(fmt_followers(_va))
                _cb.write(fmt_followers(_vb))
            else:
                _ca.write(str(_va))
                _cb.write(str(_vb))

        # 계정 겹침 분석
        _names_a = {p["username"] for p in _prof_a}
        _names_b = {p["username"] for p in _prof_b}
        _overlap = _names_a & _names_b
        st.caption(f"공통 계정: {len(_overlap)}개  |  A만: {len(_names_a - _names_b)}개  |  B만: {len(_names_b - _names_a)}개")
        if _overlap:
            st.write("공통 계정:", ", ".join(f"@{u}" for u in sorted(_overlap)[:10])
                     + ("..." if len(_overlap) > 10 else ""))

# ── ⑤ 받은 DM 관리 ───────────────────────────────────────────────
st.divider()
st.subheader("📥 받은 DM 관리")

if not st.session_state.get("ig_logged_in"):
    st.info("우측 상단 로그인 버튼으로 Instagram 계정을 연결하면 사용할 수 있어요.")
else:
    col_refresh, col_empty = st.columns([1, 5])
    with col_refresh:
        if st.button("🔄 새로고침", key="inbox_refresh"):
            with st.spinner("받은 DM 불러오는 중..."):
                threads, err = get_inbox(20)
            if err:
                st.error(err)
            else:
                st.session_state["inbox_threads"] = threads
                st.session_state["selected_thread_id"] = None

    if "inbox_threads" not in st.session_state:
        st.caption("🔄 새로고침 버튼을 눌러 받은 DM을 불러오세요.")
    elif not st.session_state["inbox_threads"]:
        st.info("받은 DM이 없어요.")
    else:
        threads = st.session_state["inbox_threads"]

        inbox_col, chat_col = st.columns([1, 2])

        with inbox_col:
            st.markdown("**대화 목록**")
            for t in threads:
                label = f"{'🔴 ' if t['읽지 않음'] else ''}{t['상대방']}"
                preview = t["마지막 메시지"][:30] + ("..." if len(t["마지막 메시지"]) > 30 else "")
                if st.button(f"{label}\n{preview}", key=f"thread_{t['thread_id']}", use_container_width=True):
                    st.session_state["selected_thread_id"] = t["thread_id"]
                    msgs, err = get_thread(t["thread_id"])
                    if err:
                        st.session_state["thread_messages"] = []
                        st.session_state["thread_error"] = err
                    else:
                        st.session_state["thread_messages"] = msgs
                        st.session_state["thread_error"] = None
                    st.rerun()

        with chat_col:
            if not st.session_state.get("selected_thread_id"):
                st.caption("왼쪽에서 대화를 선택하세요.")
            else:
                selected_id = st.session_state["selected_thread_id"]
                partner = next((t["상대방"] for t in threads if t["thread_id"] == selected_id), "")
                st.markdown(f"**@{partner} 와의 대화**")

                if st.session_state.get("thread_error"):
                    st.error(st.session_state["thread_error"])
                else:
                    msgs = st.session_state.get("thread_messages", [])
                    chat_box = st.container(height=400)
                    with chat_box:
                        for m in msgs:
                            is_me = m["보낸이"] == "나"
                            align = "right" if is_me else "left"
                            bg = "#DCF8C6" if is_me else "#F0F0F0"
                            st.markdown(
                                f"<div style='text-align:{align};margin:4px 0;'>"
                                f"<span style='background:{bg};padding:6px 12px;border-radius:12px;"
                                f"display:inline-block;max-width:80%;word-break:break-word;'>"
                                f"{m['내용']}</span></div>",
                                unsafe_allow_html=True,
                            )

                    reply_text = st.text_area("답장 입력", key="reply_input", height=80)
                    if st.button("📤 답장 보내기", type="primary", use_container_width=True):
                        if reply_text.strip():
                            ok, msg = reply_to_thread(selected_id, reply_text.strip())
                            if ok:
                                st.success(msg)
                                new_msgs, _ = get_thread(selected_id)
                                st.session_state["thread_messages"] = new_msgs
                                st.rerun()
                            else:
                                st.error(msg)
                        else:
                            st.warning("답장 내용을 입력해주세요.")
