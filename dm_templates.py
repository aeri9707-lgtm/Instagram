"""
그룹별 DM 템플릿 — 3가지 스타일 × 3개 규모 티어
{username}       : 인플루언서 계정명
{brand}          : 브랜드명
{product}        : 상품명
{category}       : 제품 카테고리
{content_theme}  : 인플루언서 콘텐츠 주제
{usp1~3}         : 핵심 강점
{manager}        : 담당자명
{kakao}          : 카톡 ID
{phone}          : 연락처
{homepage}       : 홈페이지
"""

GROUPS = {
    "A": {"label": "1만 미만",  "min": 0,      "max": 9_999},
    "B": {"label": "1만~3만",   "min": 10_000, "max": 29_999},
    "C": {"label": "3만~5만",   "min": 30_000, "max": 49_999},
    "D": {"label": "5만~7만",   "min": 50_000, "max": 69_999},
    "E": {"label": "7만~10만",  "min": 70_000, "max": 100_000},
}

STYLES = {
    "basic":    "기본형 (★) — 깔끔한 소싱 제안",
    "advanced": "전환형 (★★★) — 계정 분석 기반 전환형",
    "health":   "건강식품 브랜드형 — 웰니스/건강 전용",
}

# ─────────────────────────────────────────────────────────────
# 소규모 (A·B) — 따뜻하고 캐주얼한 톤
# 중간 (C·D)  — 전문적 & 설득적 톤
# 대형 (E·E+) — 공식·격식체 톤
# ─────────────────────────────────────────────────────────────

DM_TEMPLATES = {

    # ──────────────────────────────────────────────────────────
    # 기본형 (★) — 깔끔한 소싱 제안
    # ──────────────────────────────────────────────────────────
    "basic": {
        "small": """\
안녕하세요, {brand} 운영팀입니다 :)
현재 {category} 제품을 운영하고 있으며, 평소 올려주시는 {content_theme} 콘텐츠를 인상 깊게 보고 연락드리게 되었습니다.

팔로워분들의 반응을 보았을 때 저희 제품과 타겟 적합도가 높다고 판단되어 공동구매 제안드립니다.

{product}은
✔ {usp1}
✔ {usp2}
✔ {usp3}
강점이 있는 제품이며, 실제 사용 기반 콘텐츠와 잘 어울릴 것 같아요.

진행 시에는
• 실사용 후기 콘텐츠
• 릴스/스토리 기반 구매 전환 콘텐츠
• 할인 혜택 연계 공동구매
형태로 함께 기획 가능하며, {username}님 스타일에 맞춰 유연하게 협의드리고 싶습니다 :)

가능하시다면 담당자 연결 혹은 회신 부탁드립니다!
• 브랜드 : {brand}
• 담당자 : {manager}
• 카톡 : {kakao}
• 연락처 : {phone}
• 홈페이지 : {homepage}\
""",

        "mid": """\
안녕하세요, {brand} 운영팀입니다 :)
현재 {category} 제품을 운영하고 있으며, 평소 올려주시는 {content_theme} 콘텐츠를 인상 깊게 보고 연락드리게 되었습니다.

특히 최근 업로드하신 릴스 반응과 팔로워분들의 댓글 분위기를 보았을 때
저희 제품과 타겟 적합도가 높다고 판단되어 공동구매 제안드립니다.

{product}은
✔ {usp1}
✔ {usp2}
✔ {usp3}
강점이 있는 제품이며, 실제 사용 기반 콘텐츠와 잘 어울릴 것으로 기대하고 있습니다.

진행 시에는
• 실사용 후기 콘텐츠
• 릴스/스토리 기반 구매 전환 콘텐츠
• 할인 혜택 연계 공동구매
형태로 함께 기획 가능하며, {username}님 스타일에 맞춰 유연하게 협의드리고 싶습니다 :)

가능하시다면 담당자 연결 혹은 회신 부탁드립니다!
• 브랜드 : {brand}
• 담당자 : {manager}
• 카톡 : {kakao}
• 연락처 : {phone}
• 홈페이지 : {homepage}\
""",

        "large": """\
안녕하세요, {brand} 입니다.
{username}님의 채널을 꾸준히 팔로우하며 {content_theme} 콘텐츠 방향성과 영향력을 주목하고 있었습니다.

{category} 브랜드로서 {username}님과 공식 파트너십을 제안드리고 싶어 연락드렸습니다.

{product}의 핵심 강점:
✔ {usp1}
✔ {usp2}
✔ {usp3}

협업 형태, 조건, 콘텐츠 방향 모두 충분히 논의하여 최선의 방식으로 진행하고 싶습니다.

담당자 연결 혹은 회신 부탁드립니다.
• 브랜드 : {brand}
• 담당자 : {manager}
• 카톡 : {kakao}
• 연락처 : {phone}
• 홈페이지 : {homepage}\
""",
    },

    # ──────────────────────────────────────────────────────────
    # 전환형 (★★★) — "계정 분석하고 연락한 느낌" 전환형
    # ──────────────────────────────────────────────────────────
    "advanced": {
        "small": """\
안녕하세요, {brand} 입니다 :)
평소 계정 잘 보고 있었는데, {content_theme} 관련 콘텐츠 반응이 좋아 연락드리게 되었습니다.

팔로워분들의 반응을 보니 실제 구매 전환이 나오는 팔로워층이라고 판단되어 공동구매 제안드립니다.

저희는 {category} 브랜드이며, 현재 {product} 제품을 운영 중입니다.

특히
• {usp1}
• {usp2}
• {usp3}
에 관심 높은 고객 반응이 좋아, {username}님 콘텐츠와 결이 잘 맞을 것 같았습니다.

공구 진행 시 아래 방향으로 콘텐츠 기획 생각하고 있습니다.
① 실제 사용 후기 릴스
② Before/After 변화형 콘텐츠
③ 팔로워 공감형 스토리
④ 할인 오픈형 구매 전환 콘텐츠

단순 협찬보다는 브랜드 + {username}님 같이 키우는 방식으로 길게 운영하고 싶어 연락드렸습니다 :)

관심 있으시다면 담당자 연결 가능하실까요?
• 브랜드 : {brand}
• 담당자 : {manager}
• 카톡 : {kakao}
• 연락처 : {phone}\
""",

        "mid": """\
안녕하세요, {brand} 입니다 :)
평소 계정 잘 보고 있었는데, 특히 최근 올리신 {content_theme} 관련 릴스 반응이 좋아 연락드리게 되었습니다.

댓글/저장/공감 반응을 보니 단순 조회형 계정보다는
"실제 구매 전환이 나오는 팔로워층" 이라고 판단되어 공동구매 제안드립니다.

저희는 {category} 브랜드이며, 현재 {product} 제품을 운영 중입니다.

특히
• {usp1}
• {usp2}
• {usp3}
에 관심 높은 고객 반응이 좋아, {username}님 콘텐츠 결과물과 결이 잘 맞을 것 같았습니다.

공구 진행 시 아래 방향으로 콘텐츠 기획 생각하고 있습니다.
① 실제 사용 후기 릴스
② Before/After or 변화형 콘텐츠
③ 팔로워 공감형 스토리
④ 할인 오픈형 구매 전환 콘텐츠

단순 협찬보다는
"브랜드 + 인플루언서 같이 키우는 방식" 으로 길게 운영하고 싶어 연락드렸습니다 :)

관심 있으시다면 담당자 연결 가능하실까요?
• 브랜드 : {brand}
• 담당자 : {manager}
• 카톡 : {kakao}
• 연락처 : {phone}\
""",

        "large": """\
안녕하세요, {brand} 입니다.
{username}님의 {content_theme} 콘텐츠를 꾸준히 모니터링해왔으며,
특히 팔로워분들의 참여도와 구매 의향 댓글 흐름이 인상적이어서 연락드렸습니다.

저희 {category} 브랜드에서 {username}님과 공동구매 협업을 공식 제안드립니다.

{product}의 핵심 특장점:
• {usp1}
• {usp2}
• {usp3}

공구 진행 방향:
① 실제 사용 후기 릴스
② Before/After 변화형 콘텐츠
③ 팔로워 공감형 스토리
④ 할인 오픈형 구매 전환 콘텐츠

일회성 협찬이 아닌, 장기 파트너십 형태로 함께 성장하는 방식을 선호합니다.

관심 있으시면 담당자 연결 부탁드립니다.
• 브랜드 : {brand}
• 담당자 : {manager}
• 카톡 : {kakao}
• 연락처 : {phone}\
""",
    },

    # ──────────────────────────────────────────────────────────
    # 건강식품 브랜드형 — 웰니스/건강 카테고리 전용
    # ──────────────────────────────────────────────────────────
    "health": {
        "small": """\
안녕하세요, {brand} 입니다 :)
평소 올려주시는 {content_theme} 콘텐츠를 관심 있게 보고 연락드렸습니다.

팔로워분들의 반응을 보며 제품 적합도가 높다고 판단되어 공동구매 제안드립니다.

저희는 {brand} {category} 브랜드이며, 현재 {product} 제품을 운영 중입니다.

실제로
• {usp1}
• {usp2}
• {usp3}
관심도가 높은 고객 반응이 좋아 콘텐츠 전환이 잘 나오는 편입니다.

진행하게 된다면
① 실제 섭취/사용 후기
② 루틴형 브이로그 콘텐츠
③ 공감형 릴스
④ 공동구매 오픈 콘텐츠
형태로 함께 기획드릴 예정입니다.

{username}님 톤앤무드에 맞춰 자연스럽게 진행 가능하며,
장기 협업도 열어두고 있습니다 :)

가능하시다면 담당자 연결 부탁드리겠습니다!
• 브랜드 : {brand}
• 담당자 : {manager}
• 카톡 : {kakao}
• 연락처 : {phone}\
""",

        "mid": """\
안녕하세요, {brand} 입니다 :)
평소 올려주시는 {content_theme} 콘텐츠를 관심 있게 보고 연락드렸습니다.

특히 최근 콘텐츠 반응과 댓글 문의 흐름을 보며
팔로워분들과 제품 적합도가 높다고 판단되어 공동구매 제안드립니다.

저희는 {brand} {category} 브랜드이며, 현재 {product} 제품을 운영 중입니다.

실제로
• {usp1}
• {usp2}
• {usp3}
관심도가 높은 고객 반응이 좋아 콘텐츠 전환이 잘 나오는 편입니다.

진행하게 된다면
① 실제 섭취/사용 후기
② 루틴형 브이로그 콘텐츠
③ 공감형 릴스
④ 공동구매 오픈 콘텐츠
형태로 함께 기획드릴 예정입니다.

{username}님 톤앤무드에 맞춰 자연스럽게 진행 가능하며,
장기 협업도 열어두고 있습니다 :)

가능하시다면 담당자 연결 부탁드리겠습니다!
• 브랜드 : {brand}
• 담당자 : {manager}
• 카톡 : {kakao}
• 연락처 : {phone}\
""",

        "large": """\
안녕하세요, {brand} 입니다.
{username}님의 {content_theme} 콘텐츠와 팔로워분들의 반응을 분석한 결과,
저희 {product} 제품과의 파트너십을 공식 제안드리고자 합니다.

{product}의 핵심 강점:
• {usp1}
• {usp2}
• {usp3}

진행 방향:
① 실제 섭취/사용 후기
② 루틴형 브이로그
③ 공감형 릴스
④ 공동구매 오픈 콘텐츠

{username}님 채널 분위기에 맞춰 자연스럽게 기획하며,
장기 파트너십 형태로 협업하고 싶습니다.

담당자 연결 부탁드립니다.
• 브랜드 : {brand}
• 담당자 : {manager}
• 카톡 : {kakao}
• 연락처 : {phone}\
""",
    },
}


def _group_tier(group: str) -> str:
    if group in ("A", "B"):
        return "small"
    if group in ("C", "D"):
        return "mid"
    return "large"  # E, E+


def classify_group(followers: int) -> str:
    for code, info in GROUPS.items():
        if info["min"] <= followers <= info["max"]:
            return code
    if followers > 100_000:
        return "E+"
    return "A"


def get_dm(group: str, username: str, influencer_category: str = "",
           brand_info: dict | None = None, style: str = "basic") -> str:
    if brand_info is None:
        brand_info = {}

    style_map = DM_TEMPLATES.get(style, DM_TEMPLATES["basic"])
    tier = _group_tier(group)
    template = style_map.get(tier, style_map["mid"])

    content_theme = influencer_category or "라이프스타일"

    return template.format(
        username=username,
        content_theme=content_theme,
        brand=brand_info.get("brand") or "[브랜드명]",
        product=brand_info.get("product") or "[상품명]",
        category=brand_info.get("category") or "[카테고리]",
        usp1=brand_info.get("usp1") or "[핵심 USP 1]",
        usp2=brand_info.get("usp2") or "[핵심 USP 2]",
        usp3=brand_info.get("usp3") or "[핵심 USP 3]",
        manager=brand_info.get("manager") or "[담당자명]",
        kakao=brand_info.get("kakao") or "[카톡 ID]",
        phone=brand_info.get("phone") or "[연락처]",
        homepage=brand_info.get("homepage") or "[홈페이지]",
    )


def get_group_label(group: str) -> str:
    if group == "E+":
        return "10만 초과"
    return str(GROUPS.get(group, {}).get("label", "-"))
