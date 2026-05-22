"""재사용 HTML/SVG 컴포넌트 — Streamlit unsafe_allow_html 전용"""


# ── 색상 팔레트 ────────────────────────────────────────────────────────
IG_PURPLE   = "#833ab4"
IG_PINK     = "#e1306c"
IG_ORANGE   = "#f77737"
IG_GRAD     = "linear-gradient(45deg, #833ab4 0%, #e1306c 50%, #f77737 100%)"
IG_GRAD_135 = "linear-gradient(135deg, #833ab4 0%, #c13584 40%, #f77737 100%)"

PRIMARY   = IG_PURPLE
SUCCESS   = "#10b981"
WARNING   = "#f59e0b"
DANGER    = "#ef4444"
BG_CARD   = "#ffffff"
BG_PAGE   = "#eeeae3"
BG_SUBTLE = "#f7f5f2"
BORDER    = "#e4e0d9"
TEXT_MAIN = "#111111"
TEXT_SUB  = "#888888"


def _score_color(score: int) -> str:
    if score >= 75:
        return SUCCESS
    if score >= 50:
        return WARNING
    return DANGER


# ── 원형 게이지 SVG ──────────────────────────────────────────────────
def gauge_svg(score: int, label: str, size: int = 80) -> str:
    color = _score_color(score)
    pct = min(max(score, 0), 100)
    font_size = 9 if pct >= 100 else 10
    return (
        f"<div style='display:flex;flex-direction:column;align-items:center;gap:6px;'>"
        f"<svg viewBox='0 0 36 36' width='{size}' height='{size}'>"
        f"<circle cx='18' cy='18' r='15.9155' fill='none' stroke='#f0ede8' stroke-width='3.5'/>"
        f"<circle cx='18' cy='18' r='15.9155' fill='none'"
        f" stroke='{color}' stroke-width='3.5'"
        f" stroke-dasharray='{pct} 100'"
        f" stroke-linecap='round'"
        f" transform='rotate(-90 18 18)'/>"
        f"<text x='18' y='20' text-anchor='middle'"
        f" font-size='{font_size}' font-weight='700' fill='{color}'>{pct}</text>"
        f"</svg>"
        f"<span style='font-size:11px;color:{TEXT_SUB};font-weight:500;letter-spacing:-0.2px;'>{label}</span>"
        f"</div>"
    )


def gauge_row(scores: dict[str, int]) -> str:
    cells = "".join(
        f"<td style='padding:0 16px;text-align:center;'>{gauge_svg(v, k)}</td>"
        for k, v in scores.items()
    )
    return (
        f"<div style='background:{BG_CARD};border:1px solid {BORDER};"
        f"border-radius:16px;padding:20px 12px;margin:12px 0;"
        f"box-shadow:0 1px 6px rgba(0,0,0,0.05);'>"
        f"<table style='width:100%;border-collapse:collapse;'><tr>{cells}</tr></table>"
        f"</div>"
    )


# ── 가로 점수 바 ──────────────────────────────────────────────────────
def score_bar(score: int, label: str, max_score: int = 100) -> str:
    pct = int(min(max(score, 0), max_score) / max_score * 100)
    color = _score_color(score)
    return (
        f"<div style='margin:6px 0;'>"
        f"<div style='display:flex;justify-content:space-between;margin-bottom:4px;'>"
        f"<span style='font-size:12px;color:{TEXT_SUB};font-weight:500;'>{label}</span>"
        f"<span style='font-size:12px;font-weight:700;color:{color};'>{score}</span>"
        f"</div>"
        f"<div style='height:5px;background:#f0ede8;border-radius:99px;'>"
        f"<div style='height:5px;width:{pct}%;background:{color};"
        f"border-radius:99px;transition:width 0.6s;'></div>"
        f"</div>"
        f"</div>"
    )


# ── 위험도 배지 ───────────────────────────────────────────────────────
def risk_badge(level: str) -> str:
    mapping = {
        "낮음":  ("#dcfce7", "#166534", "낮음"),
        "보통":  ("#fef9c3", "#854d0e", "보통"),
        "높음":  ("#fee2e2", "#991b1b", "높음"),
    }
    bg, fg, label = mapping.get(level, ("#f3f4f6", "#374151", level))
    return (
        f"<span style='background:{bg};color:{fg};padding:3px 10px;"
        f"border-radius:99px;font-size:12px;font-weight:600;'>{label}</span>"
    )


# ── KPI 단가 배너 ─────────────────────────────────────────────────────
def cost_banner(cost_str: str, er_label: str = "") -> str:
    sub = f"<br><span style='font-size:11px;color:#6ee7b7;'>ER 반영 · {er_label}</span>" if er_label else ""
    return (
        f"<div style='background:linear-gradient(135deg,#0f172a,#1e293b);"
        f"border-radius:14px;padding:16px 22px;margin-bottom:16px;"
        f"display:flex;align-items:center;justify-content:space-between;'>"
        f"<div>"
        f"<div style='font-size:11px;color:#94a3b8;font-weight:500;letter-spacing:0.5px;text-transform:uppercase;'>게시물 1개당 예상 협업 단가</div>"
        f"<div style='font-size:26px;font-weight:800;color:#ffffff;margin-top:4px;'>{cost_str}</div>"
        f"{sub}</div>"
        f"<div style='font-size:32px;opacity:0.5;'>💰</div>"
        f"</div>"
    )


# ── 인플루언서 프로필 카드 ────────────────────────────────────────────
def profile_card(p: dict, dm_text: str = "", cost: str = "") -> str:
    verified = "✅ " if p.get("is_verified") else ""
    followers_raw = p.get("followers", 0)
    if followers_raw >= 10_000:
        f_str = f"{followers_raw / 10_000:.1f}만".rstrip("0").rstrip(".") + "만"
    else:
        f_str = f"{followers_raw:,}"

    cat = p.get("category", "") or p.get("카테고리", "")
    region = p.get("region", "")
    bio = (p.get("bio", "") or "")[:60]
    url = p.get("profile_url", f"https://www.instagram.com/{p.get('username', '')}/")

    cat_chip = (
        f"<span style='background:#f0ebfa;color:#6d28d9;padding:2px 9px;"
        f"border-radius:99px;font-size:11px;font-weight:500;margin-right:4px;'>{cat}</span>"
        if cat else ""
    )
    region_chip = (
        f"<span style='background:#e0f2fe;color:#0369a1;padding:2px 9px;"
        f"border-radius:99px;font-size:11px;font-weight:500;'>{region}</span>"
        if region else ""
    )
    cost_line = (
        f"<div style='margin-top:8px;font-size:12px;color:{TEXT_SUB};'>"
        f"예상 단가 <strong style='color:{TEXT_MAIN};'>{cost}</strong></div>"
        if cost else ""
    )
    dm_line = (
        f"<div style='margin-top:10px;padding:10px 14px;"
        f"background:{BG_SUBTLE};border-radius:10px;border-left:3px solid #c4b5fd;"
        f"font-size:12px;color:{TEXT_SUB};line-height:1.6;'>"
        f"{dm_text[:120]}{'…' if len(dm_text) > 120 else ''}"
        f"</div>"
        if dm_text else ""
    )

    return (
        f"<div style='background:{BG_CARD};border:1px solid {BORDER};"
        f"border-radius:16px;padding:18px 22px;margin-bottom:10px;"
        f"box-shadow:0 1px 4px rgba(0,0,0,0.04);'>"
        f"<div style='display:flex;justify-content:space-between;align-items:flex-start;'>"
        f"<div>"
        f"<a href='{url}' target='_blank' style='font-size:15px;font-weight:700;"
        f"color:{TEXT_MAIN};text-decoration:none;'>{verified}@{p.get('username','')}</a>"
        f"<span style='font-size:13px;color:{TEXT_SUB};margin-left:8px;'>{p.get('full_name','')}</span>"
        f"</div>"
        f"<div style='font-size:18px;font-weight:700;color:{TEXT_MAIN};'>{f_str}</div>"
        f"</div>"
        f"<div style='margin-top:8px;'>{cat_chip}{region_chip}</div>"
        + (f"<div style='font-size:12px;color:{TEXT_SUB};margin-top:6px;'>{bio}</div>" if bio else "")
        + cost_line
        + dm_line
        + f"</div>"
    )


# ── 전체 CSS ──────────────────────────────────────────────────────────
def global_css() -> str:
    return """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="st-"], .stMarkdown, .stText,
button, input, select, textarea, label, p, h1, h2, h3, h4, h5, h6 {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo',
                 'Noto Sans KR', sans-serif !important;
}

[data-baseweb="popover"],
[data-baseweb="menu"],
[data-baseweb="select"] [role="listbox"] {
    z-index: 99999 !important;
}

/* ── 페이지 배경 ── */
.stApp { background: #eeeae3 !important; }

/* ── 메인 컨테이너 — 투명 (카드 없음) ── */
.main .block-container {
    background: transparent !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    padding-top: 1.5rem !important;
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    padding-bottom: 2rem !important;
    max-width: 760px !important;
}

@media (max-width: 768px) {
    .main .block-container {
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
}

/* ── 탭 패널 — 흰색 카드 ── */
[data-baseweb="tab-panel"] {
    background: white !important;
    border-radius: 20px !important;
    box-shadow: 0 2px 24px rgba(0,0,0,0.07) !important;
    margin-top: 10px !important;
    padding: 32px 36px !important;
}

@media (min-width: 1024px) {
    [data-baseweb="tab-panel"] {
        padding: 40px 52px !important;
    }
}

#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
.stDeployButton { display: none !important; }

/* ── 탭 ── */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(255,255,255,0.55) !important;
    border-radius: 99px !important;
    padding: 5px !important;
    gap: 2px !important;
    border-bottom: none !important;
    box-shadow: 0 1px 8px rgba(0,0,0,0.06) !important;
    justify-content: center !important;
}
/* 탭 하단 밑줄 indicator 완전 제거 */
.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"] {
    display: none !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 99px !important;
    padding: 9px 24px !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    color: #666 !important;
    background: transparent !important;
    border: none !important;
    border-bottom: none !important;
    transition: all 0.15s !important;
    white-space: nowrap !important;
}
.stTabs [aria-selected="true"] {
    background: #ffffff !important;
    color: #111 !important;
    font-weight: 600 !important;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1) !important;
    border-bottom: none !important;
}

/* ── Primary 버튼 ── */
.stButton > button[kind="primary"] {
    background: linear-gradient(45deg, #833ab4 0%, #c13584 45%, #f77737 100%) !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    color: white !important;
    font-size: 14px !important;
    box-shadow: 0 3px 14px rgba(131,58,180,0.3) !important;
    transition: transform 0.15s, box-shadow 0.15s, opacity 0.15s !important;
}
.stButton > button[kind="primary"]:hover {
    opacity: 0.9 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(131,58,180,0.4) !important;
}
.stButton > button[kind="primary"]:active {
    transform: translateY(0) !important;
}

/* ── Secondary 버튼 ── */
.stButton > button[kind="secondary"] {
    border-radius: 10px !important;
    font-weight: 500 !important;
    font-size: 13px !important;
    border: 1px solid #e4e0d9 !important;
    background: #faf8f5 !important;
    color: #444 !important;
    transition: all 0.15s !important;
}
.stButton > button[kind="secondary"]:hover {
    border-color: #833ab4 !important;
    color: #833ab4 !important;
    background: white !important;
}

/* ── Metric 카드 ── */
[data-testid="stMetric"] {
    background: #faf8f5 !important;
    border: 1px solid #e4e0d9 !important;
    border-radius: 14px !important;
    padding: 14px 16px !important;
    box-shadow: none !important;
}
[data-testid="stMetricLabel"] > div {
    font-size: 11px !important;
    font-weight: 600 !important;
    color: #999 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
}
[data-testid="stMetricValue"] > div {
    font-size: 20px !important;
    font-weight: 700 !important;
    color: #111 !important;
}

/* ── Expander ── */
[data-testid="stExpander"] {
    border: 1px solid #e4e0d9 !important;
    border-radius: 16px !important;
    background: white !important;
    box-shadow: none !important;
    overflow: visible !important;
    margin-bottom: 10px !important;
}
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary div {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont,
                 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif !important;
    font-weight: 600 !important;
    color: #111 !important;
    font-size: 14px !important;
}
[data-testid="stExpander"] summary {
    padding: 12px 18px !important;
    background: #faf8f5 !important;
    border-bottom: 1px solid #e4e0d9 !important;
    border-radius: 16px 16px 0 0 !important;
}
[data-testid="stExpander"] summary:hover {
    background: #f5f3ef !important;
}
[data-testid="stExpander"] summary span {
    display: none !important;
}

/* ── Input 필드 ── */
.stTextInput > div > div > input,
.stNumberInput > div > div > input {
    border-radius: 10px !important;
    border: 1px solid #e4e0d9 !important;
    font-size: 14px !important;
    padding: 10px 14px !important;
    background: #faf8f5 !important;
    color: #111 !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}
.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus {
    border-color: #833ab4 !important;
    box-shadow: 0 0 0 3px rgba(131,58,180,0.1) !important;
    outline: none !important;
    background: white !important;
}

/* ── TextArea ── */
.stTextArea > div > div > textarea {
    border-radius: 14px !important;
    border: 1px solid #e4e0d9 !important;
    font-size: 14px !important;
    background: #faf8f5 !important;
    color: #111 !important;
    line-height: 1.6 !important;
    padding: 14px 16px !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}
.stTextArea > div > div > textarea:focus {
    border-color: #833ab4 !important;
    box-shadow: 0 0 0 3px rgba(131,58,180,0.08) !important;
    background: white !important;
}

/* ── SelectBox ── */
.stSelectbox > div > div {
    border-radius: 10px !important;
    border: 1px solid #e4e0d9 !important;
    background: #faf8f5 !important;
}

/* ── Multiselect ── */
.stMultiSelect > div > div {
    border-radius: 10px !important;
    border: 1px solid #e4e0d9 !important;
    background: #faf8f5 !important;
}
.stMultiSelect span[data-baseweb="tag"] {
    background: #833ab4 !important;
    color: white !important;
    border-radius: 6px !important;
}

/* ── Progress bar ── */
[data-testid="stProgressBar"] > div > div > div {
    background: linear-gradient(90deg, #833ab4, #e1306c, #f77737) !important;
    border-radius: 99px !important;
}
[data-testid="stProgressBar"] > div > div {
    background: #f0ede8 !important;
    border-radius: 99px !important;
    height: 5px !important;
}

/* ── DataFrames ── */
[data-testid="stDataFrame"] {
    border-radius: 14px !important;
    overflow: hidden !important;
    border: 1px solid #e4e0d9 !important;
    box-shadow: none !important;
}

/* ── Alert ── */
[data-testid="stAlert"] { border-radius: 12px !important; text-align: center !important; }
[data-testid="stAlert"] p { text-align: center !important; }

/* ── White card containers ── */
.st-key-campaign_card,
.st-key-dm_card {
    background: #ffffff !important;
    border-radius: 20px !important;
    box-shadow: 0 2px 24px rgba(0,0,0,0.07) !important;
    border: 1px solid #e4e0d9 !important;
    padding: 24px 32px !important;
    margin-top: 12px !important;
}

/* ── Divider ── */
hr, [data-testid="stDivider"] {
    display: none !important;
}

/* ── Slider ── */
[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {
    background: #833ab4 !important;
    border-color: #833ab4 !important;
}

/* ── Radio ── */
.stRadio [data-baseweb="radio"] [data-checked="true"] > div {
    background-color: #833ab4 !important;
    border-color: #833ab4 !important;
}

/* ── Checkbox ── */
.stCheckbox [data-baseweb="checkbox"] [data-checked="true"] > div {
    background-color: #833ab4 !important;
    border-color: #833ab4 !important;
}

/* ── Spinner ── */
.stSpinner > div {
    border-top-color: #833ab4 !important;
}

/* ── 로그인 아바타 버튼 ── */
.st-key-login_toggle_btn button {
    background: linear-gradient(45deg, #833ab4, #e1306c, #f77737) !important;
    border: none !important;
    border-radius: 50% !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    font-size: 15px !important;
    width: 40px !important;
    height: 40px !important;
    min-height: 40px !important;
    padding: 0 !important;
    line-height: 40px !important;
    box-shadow: 0 2px 10px rgba(131,58,180,0.35) !important;
    transition: all 0.15s !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    margin-left: auto !important;
}
.st-key-login_toggle_btn button:hover {
    opacity: 0.88 !important;
    transform: scale(1.06) !important;
    box-shadow: 0 4px 14px rgba(131,58,180,0.5) !important;
}

/* ── 상단 컨트롤 바 ── */
.st-key-top_controls > div:first-child {
    background: white;
    border-radius: 16px;
    border: 1px solid #e4e0d9;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    padding: 12px 20px;
    margin-bottom: 4px;
}

/* 상단 모드 라디오 — 가로 pill */
.st-key-top_controls .stRadio {
    margin: 0 !important;
}
.st-key-top_controls .stRadio [data-baseweb="radio"] {
    margin-right: 8px !important;
}
.st-key-top_controls .stRadio label {
    font-size: 13px !important;
    font-weight: 500 !important;
    color: #555 !important;
}
.st-key-top_controls .stRadio [data-checked="true"] + div label {
    color: #833ab4 !important;
    font-weight: 700 !important;
}

/* 메인 패널 */
.st-key-main_panel > div:first-child {
    background: white;
    border-radius: 20px;
    border: 1px solid #e4e0d9;
    box-shadow: 0 2px 16px rgba(0,0,0,0.05);
    padding: 32px 40px;
}

/* 모드 탭 (메인 패널 상단) */
.st-key-main_panel .stTabs [data-baseweb="tab-list"] {
    justify-content: flex-start !important;
    background: #f5f3ef !important;
    border-radius: 12px !important;
    padding: 4px !important;
    margin-bottom: 24px !important;
}
.st-key-main_panel .stTabs [data-baseweb="tab"] {
    font-size: 13px !important;
    padding: 8px 20px !important;
}

/* 탭 패널 내부는 배경 없앰 (메인 패널이 이미 흰색) */
.st-key-main_panel [data-baseweb="tab-panel"] {
    background: transparent !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin-top: 0 !important;
}

/* PC 카드 그리드 ── */
.pc-card-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 12px;
}
.pc-card-grid > div {
    margin-bottom: 0 !important;
}

/* ── PC 상단 컨트롤 sticky ── */
@media (min-width: 900px) {
    .st-key-top_controls > div:first-child {
        position: sticky;
        top: 0.5rem;
        z-index: 100;
    }
}

/* ── 예시 chip 버튼 ── */
[data-testid="stHorizontalBlock"] [data-testid="stButton"] button[kind="secondary"] {
    background: #f5f3ef !important;
    border: 1px solid #e4e0d9 !important;
    border-radius: 99px !important;
    color: #555 !important;
    font-size: 12px !important;
    font-weight: 400 !important;
    padding: 6px 14px !important;
    box-shadow: none !important;
    transition: all 0.15s !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}
[data-testid="stHorizontalBlock"] [data-testid="stButton"] button[kind="secondary"] p,
[data-testid="stHorizontalBlock"] [data-testid="stButton"] button[kind="secondary"] span {
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}
[data-testid="stHorizontalBlock"] [data-testid="stButton"] button[kind="secondary"]:hover {
    background: #111 !important;
    border-color: transparent !important;
    color: white !important;
}
</style>
"""


# ── 네비게이션 바 로고 ────────────────────────────────────────────────
def navbar_logo() -> str:
    return (
        "<div style='display:flex;align-items:center;gap:10px;padding:6px 0;'>"
        "<div style='width:34px;height:34px;"
        "background:linear-gradient(135deg,#833ab4,#e1306c,#f77737);"
        "border-radius:9px;display:flex;align-items:center;justify-content:center;"
        "font-size:17px;flex-shrink:0;'>📸</div>"
        "<span style='font-size:16px;font-weight:800;color:#111;letter-spacing:-0.4px;'>"
        "AI Creator Finder</span>"
        "</div>"
    )


def platform_badge() -> str:
    return (
        "<div style='text-align:center;padding:14px 0 2px;'>"
        "<span style='font-size:10px;font-weight:600;color:#aaa;"
        "letter-spacing:2.5px;text-transform:uppercase;margin-right:14px;'>PLATFORM</span>"
        "<span style='background:#111;border-radius:99px;padding:6px 18px;"
        "font-size:13px;font-weight:600;color:white;'>"
        "Instagram"
        "</span>"
        "</div>"
    )


def hero_title() -> str:
    return (
        "<div style='text-align:center;padding:24px 0 18px;'>"
        "<div style='font-size:32px;font-weight:800;color:#111;"
        "letter-spacing:-1px;line-height:1.2;'>"
        "찾고 싶은 크리에이터를 설명하세요"
        "</div>"
        "<div style='font-size:14px;color:#999;margin-top:10px;font-weight:400;'>"
        "원하는 조건을 입력하고, 나중에 필터로 세분화하세요"
        "</div>"
        "</div>"
    )


def search_tips() -> str:
    tips = [
        ("<strong style='color:#111;'>넓게 시작한 후 필터링:</strong>"
         " \"한국 스킨케어 크리에이터\""
         "<br><span style='color:#bbb;font-size:12px;'>→ 이후 필터: 팔로워 1만~5만, 서울 기반</span>"),
        ("<strong style='color:#111;'>감성 표현 사용:</strong>"
         " \"미니멀\", \"럭셔리\", \"내추럴\", \"트렌디\" 같은 단어 활용"),
    ]
    items = "".join(
        f"<div style='display:flex;gap:10px;margin-bottom:10px;align-items:flex-start;'>"
        f"<span style='color:#833ab4;font-size:13px;flex-shrink:0;margin-top:2px;'>✓</span>"
        f"<span style='font-size:13px;color:#555;line-height:1.6;'>{t}</span>"
        f"</div>"
        for t in tips
    )
    return (
        f"<div style='background:#faf8f5;border:1px solid #e4e0d9;border-radius:16px;"
        f"padding:18px 22px;margin-top:14px;'>"
        f"<div style='font-size:13px;font-weight:600;color:#111;margin-bottom:14px;'>"
        f"💡 더 나은 결과를 위한 팁"
        f"</div>"
        f"{items}"
        f"</div>"
    )


# ── 예시 chip 행 (HTML 전용, 미사용) ─────────────────────────────────
_EXAMPLE_QUERIES = [
    "20대 뷰티 마이크로인플루언서",
    "한국 육아 맘 팔로워 5만 이상",
    "패션 코디 나노 인플루언서",
    "다이어트 헬스 매크로 계정",
    "요리 먹방 한국 인플루언서",
]


def example_chips(selected: str = "") -> str:
    chips = ""
    for q in _EXAMPLE_QUERIES:
        active = "background:#111;color:white;border-color:#111;" if q == selected else \
                 "background:#f5f3ef;color:#555;border-color:#e4e0d9;"
        chips += (
            f"<span style='{active}padding:5px 14px;"
            f"border-radius:99px;font-size:12px;font-weight:400;border:1px solid;"
            f"cursor:pointer;white-space:nowrap;display:inline-block;margin:3px;'>{q}</span>"
        )
    return (
        f"<div style='text-align:center;padding:8px 0 4px;'>"
        f"<span style='font-size:11px;color:#bbb;margin-right:8px;'>예시 →</span>"
        f"{chips}"
        f"</div>"
    )


def card_grid(cards: list[str]) -> str:
    """여러 profile_card HTML을 PC에서 2열 그리드로 묶어 반환."""
    inner = "".join(f"<div>{c}</div>" for c in cards)
    return f"<div class='pc-card-grid'>{inner}</div>"


# ── 네비게이션 구분선 ─────────────────────────────────────────────────
def nav_divider() -> str:
    return (
        "<hr style='border:none;border-top:1px solid #e4e0d9;"
        "margin:0 0 18px 0;'/>"
    )


# ── 그룹 요약 카드 ────────────────────────────────────────────────────
def group_summary_card(code: str, cnt: int, label: str, color: str) -> str:
    return (
        f"<div style='text-align:center;padding:16px 12px;border-radius:16px;"
        f"background:white;border:1.5px solid {color}20;"
        f"box-shadow:none;'>"
        f"<div style='font-size:28px;font-weight:800;color:{color};'>{cnt}</div>"
        f"<div style='font-size:11px;color:#999;margin-top:4px;font-weight:500;'>"
        f"그룹 {code}<br>{label}"
        f"</div>"
        f"</div>"
    )
