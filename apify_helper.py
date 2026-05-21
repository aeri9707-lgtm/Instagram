import os
import re
from datetime import datetime, timezone
from apify_client import ApifyClient
from dotenv import load_dotenv

load_dotenv()

KEYWORD_ACTOR     = "patient_discovery/instagram-search-users"  # 키워드 → 계정 직접 검색
HASHTAG_ACTOR     = "apify/instagram-hashtag-scraper"           # 해시태그 → 게시물 작성자 수집
PROFILE_ACTOR     = "apify/instagram-profile-scraper"           # 사용자명 → 상세 프로필
POST_ACTOR        = "apify/instagram-scraper"                   # 계정 게시물 수집
SEARCH_ACTOR      = "apify/google-search-scraper"               # 웹 검색 (브랜드 언급 시그널)
USER_FILTER_ACTOR = "instaprism/instagram-user-filter"          # 정밀 팔로워/참여율 필터링

# 정밀 필터 비용 상수 ($7 / 1,000 결과 기준, 1달러 = 1,400원)
_PRECISE_FILTER_COST_PER_ACCOUNT = 7 / 1000 * 1400  # ≈ ₩9.8/계정

# 카테고리별 bio/username 검색 키워드 — Instagram 검색창 기반
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "육아":     ["육아맘", "맘스타그램", "육아크리에이터", "맘인플루언서"],
    "뷰티":     ["뷰티크리에이터", "뷰티인플루언서", "메이크업아티스트", "스킨케어"],
    "반려동물": ["펫인플루언서", "반려동물", "강아지크리에이터", "고양이"],
    "다이어트": ["피트니스인플루언서", "다이어터", "헬스크리에이터", "운동"],
    "요리":     ["푸드인플루언서", "홈쿡", "요리크리에이터", "집밥"],
    "패션":     ["패션인플루언서", "스타일리스트", "패션크리에이터", "ootd"],
    "여행":     ["여행인플루언서", "여행크리에이터", "트래블인플루언서"],
    "인테리어": ["인테리어크리에이터", "홈스타그램", "인테리어인플루언서"],
    "재테크":   ["재테크인플루언서", "경제크리에이터", "주식인플루언서"],
    "게임":     ["게임인플루언서", "게이머", "스트리머"],
    "음악":     ["뮤지션", "싱어송라이터", "음악크리에이터"],
    "사진":     ["사진작가", "포토그래퍼", "photography"],
}

# Google 검색용 쿼리 템플릿
_CATEGORY_GOOGLE_QUERIES: dict[str, list[str]] = {
    "육아":     ["site:instagram.com 육아맘 팔로워", "instagram 육아 인플루언서 맘크리에이터"],
    "뷰티":     ["site:instagram.com 뷰티크리에이터 팔로워", "instagram 뷰티 인플루언서 메이크업"],
    "반려동물": ["site:instagram.com 반려동물 펫인플루언서", "instagram 강아지 고양이 크리에이터"],
    "다이어트": ["site:instagram.com 다이어트 피트니스인플루언서", "instagram 헬스 운동 크리에이터"],
    "요리":     ["site:instagram.com 요리크리에이터 홈쿡", "instagram 푸드인플루언서 집밥"],
    "패션":     ["site:instagram.com 패션인플루언서 코디", "instagram 패션 스타일리스트 ootd"],
    "여행":     ["site:instagram.com 여행인플루언서", "instagram 여행 크리에이터 트래블"],
    "인테리어": ["site:instagram.com 인테리어크리에이터", "instagram 홈스타그램 인테리어"],
    "재테크":   ["site:instagram.com 재테크인플루언서", "instagram 경제 주식 크리에이터"],
}

# ── 분석용 상수 ─────────────────────────────────────────────────────
_AD_KEYWORDS = frozenset({
    "광고", "협찬", "공구", "유료광고", "제공받아", "파트너스", "제품제공",
    "#ad", "#sponsored", "pr ", "[광고]", "[협찬]",
})

# 상업 활동 시그널
_SHOPPING_DOMAINS = [
    "linktr.ee", "linkin.bio", "lnk.bio", "shop.app", "ltk.app",
    "smartstore", "cafe24", "coupang", "musinsa", "29cm",
    "ohou.se", "balaan", "ably", "zigzag", "brandi", "lotteon",
]
_SHOPPING_CTA_KW = [
    "바이오 링크", "프로필 링크", "링크는 바이오", "bio link", "link in bio",
    "구매링크", "쇼핑링크", "할인코드", "쿠폰코드", "할인 코드",
    "지금 구매", "구매하러", "주문하기", "shop now", "buy now", "order now",
    "공동구매", "공구 오픈", "공구해요", "한정 수량", "선착순",
    "제 코드", "내 코드", "my code", "use code", "코드 입력",
]
_COLLAB_SIGNAL_KW = [
    "협찬", "협업", "콜라보", "파트너십", "pr제공", "제공받",
    "#ad", "#sponsored", "#collaboration", "#partnership",
    "kindly gifted", "gifted by", "brand ambassador",
]

_PURCHASE_INTENT = [
    "어디서 사", "링크 주", "따라 해볼", "저도 샀", "공구 언제", "어디서 파",
    "살 수 있", "파는 곳", "구매링크", "사고 싶", "얼마예요", "어디서 구",
    "공구해", "어디서 살", "구매", "링크", "어디서",
]

_LOW_QUALITY = ["ㅋㅋ", "ㅎㅎ", "wow", "nice", "good", "great", "lol", "ㄷㄷ", "대박"]

_EMOJI_ONLY_RE = re.compile(
    r'^[\U0001F000-\U0001FFFF\U00002600-\U000027BF\U0001F300-\U0001FAFF'
    r'\U00002702-\U000027B0\s🔥👍❤️😍✨💕👏🙏😭🥰💯🌟⭐️]+$'
)

_BRAND_KEYWORDS: dict[str, list[str]] = {
    "뷰티":        ["뷰티", "화장", "스킨케어", "메이크업", "피부", "립", "beauty", "skin", "makeup", "cosmetic"],
    "다이어트·건강": ["다이어트", "헬스", "운동", "건강", "단백질", "diet", "health", "fitness", "workout"],
    "패션":        ["패션", "코디", "옷", "스타일", "ootd", "outfit", "fashion"],
    "육아":        ["육아", "아기", "아이", "엄마", "임신", "출산", "baby", "mom"],
    "식품·요리":   ["요리", "음식", "맛집", "레시피", "먹방", "food", "recipe", "cooking"],
    "라이프스타일": ["인테리어", "홈", "여행", "라이프", "일상", "lifestyle", "travel", "home"],
    "반려동물":    ["강아지", "고양이", "반려", "펫", "dog", "cat", "pet"],
    "게임":        ["게임", "스트리머", "game", "gaming", "streamer"],
    "음악":        ["음악", "뮤직", "가수", "music", "singer", "musician"],
    "사진":        ["사진", "포토", "photo", "photography", "photographer"],
}


def _detect_category_from_bio(bio: str, full_name: str = "") -> str:
    """바이오·채널명 텍스트로 콘텐츠 카테고리 감지"""
    text = f"{bio} {full_name}".lower()
    best_cat, best_score = "", 0
    for cat, kws in _BRAND_KEYWORDS.items():
        score = sum(1 for kw in kws if kw in text)
        if score > best_score:
            best_score, best_cat = score, cat
    return best_cat if best_score > 0 else ""

# Buffer 2024-2025 (27M+ 게시물) — (likes+comments)/followers × 100 기반
_ER_BENCHMARKS: list[tuple[int, float]] = [
    (500_000, 3.7), (100_000, 3.5), (50_000, 3.6),
    (10_000, 3.7),  (5_000,  4.1),  (1_000,  4.6), (0, 5.2),
]

# Statista 2024 — 릴스 평균 도달률 (views/followers × 100)
_REELS_REACH_BENCHMARKS: list[tuple[int, float]] = [
    (1_000_000, 20.0), (100_000, 30.0), (5_000, 40.0), (0, 70.0),
]


def _get_client(apify_token: str | None = None) -> ApifyClient | None:
    token = apify_token or os.getenv("APIFY_API_TOKEN")
    if not token:
        try:
            import streamlit as st
            token = st.secrets.get("APIFY_API_TOKEN")
        except Exception:
            pass
    if not token:
        return None
    return ApifyClient(token)


_KR_KEYWORDS = {
    "korea", "korean", "한국", "서울", "부산", "대구", "인천",
    "광주", "대전", "울산", "제주", "경기", "강남", "홍대",
    "kbeauty", "k-beauty", "kdrama", "kpop", "k-pop",
}
_KR_USERNAME_PATTERNS = ("_kr", ".kr", "kr_", "korea", "korean", "seoul", "busan")

# 도시명 감지 맵: 표시명 → 감지 키워드 목록
_KR_CITY_MAP: list[tuple[str, list[str]]] = [
    ("서울",  ["서울", "seoul", "강남", "강북", "홍대", "신촌", "이태원", "종로", "잠실", "명동", "압구정", "판교", "여의도"]),
    ("부산",  ["부산", "busan", "해운대", "광안리", "서면"]),
    ("인천",  ["인천", "incheon", "송도"]),
    ("대구",  ["대구", "daegu"]),
    ("광주",  ["광주", "gwangju"]),
    ("대전",  ["대전", "daejeon"]),
    ("울산",  ["울산", "ulsan"]),
    ("제주",  ["제주", "jeju"]),
    ("경기",  ["경기", "수원", "성남", "고양", "용인", "안양", "의정부", "파주", "김포"]),
    ("강원",  ["강원", "춘천", "강릉", "원주"]),
    ("충청",  ["충청", "청주", "천안", "충주"]),
    ("전라",  ["전라", "전주", "여수", "순천"]),
    ("경상",  ["경상", "창원", "진주", "포항", "경주"]),
]


def _detect_city(bio: str, full_name: str) -> str:
    """바이오·채널명에서 한국 도시 감지. 감지 불가 시 빈 문자열 반환."""
    text = f"{bio} {full_name}".lower()
    for city_name, keywords in _KR_CITY_MAP:
        if any(kw in text for kw in keywords):
            return city_name
    return ""


def _has_hangul(text: str) -> bool:
    return any("가" <= ch <= "힣" for ch in text)


def _detect_region(bio: str, full_name: str, username: str, country_code: str) -> str:
    if country_code and country_code.upper() == "KR":
        return "한국"
    if _has_hangul(bio) or _has_hangul(full_name) or _has_hangul(username):
        return "한국"
    text = f"{bio} {full_name}".lower()
    if any(kw in text for kw in _KR_KEYWORDS):
        return "한국"
    uname_lower = username.lower()
    if any(pat in uname_lower for pat in _KR_USERNAME_PATTERNS):
        return "한국"
    return "해외"


def _parse_count(val) -> int | None:
    """숫자, 문자열('110K', '1.2M', '1,234') 모두 int로 변환"""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val).strip().replace(",", "").replace(" ", "")
    if not s:
        return None
    s_upper = s.upper()
    try:
        if s_upper.endswith("M"):
            return int(float(s_upper[:-1]) * 1_000_000)
        if s_upper.endswith("K"):
            return int(float(s_upper[:-1]) * 1_000)
        return int(float(s))
    except (ValueError, TypeError):
        return None


def _pick_int(item: dict, *keys: str) -> int:
    for key in keys:
        result = _parse_count(item.get(key))
        if result is not None and result > 0:
            return result
    return 0


def _normalize_profile(item: dict) -> dict:
    uname     = item.get("username") or item.get("ownerUsername", "")
    bio       = item.get("biography") or item.get("description", "")
    full_name = item.get("fullName") or item.get("ownerFullName", "")
    cc        = item.get("countryCode") or item.get("country", "")

    # 팔로워 필드를 순서대로 시도해서 처음 양수인 값 사용 (0은 skip)
    _follower_fields = ["followersCount", "followedByCount", "followers",
                        "follower_count", "userInfo_followersCount",
                        "edge_followed_by", "userStats_followers"]
    followers = 0
    for f in _follower_fields:
        raw = item.get(f)
        # edge_followed_by는 {"count": N} 형태일 수 있음
        if isinstance(raw, dict):
            raw = raw.get("count")
        v = _parse_count(raw)
        if v is not None and v > 0:
            followers = v
            break

    following = _pick_int(item, "followsCount", "followingCount", "followeeCount", "following", "follows_count")

    # 디버그: 모든 키 저장
    _raw = {k: v for k, v in item.items() if k not in ("latestPosts", "biography", "profilePicUrl", "profilePicUrlHD") and v is not None}

    # relatedProfiles: 인스타그램이 제공하는 연관 계정 목록
    related_raw = item.get("relatedProfiles") or []
    related_usernames: list[str] = []
    for rp in related_raw:
        if isinstance(rp, dict):
            rn = rp.get("username") or rp.get("userName") or ""
        elif isinstance(rp, str):
            rn = rp
        else:
            rn = ""
        if rn:
            related_usernames.append(rn)

    return {
        "username":        uname,
        "full_name":       full_name,
        "followers":       followers,
        "following":       following,
        "posts_count":     int(item.get("postsCount") or item.get("media_count", 0)),
        "bio":             bio,
        "category":        _detect_category_from_bio(bio, full_name),
        "is_verified":     bool(item.get("verified") or item.get("isVerified") or item.get("is_verified", False)),
        "profile_url":     f"https://www.instagram.com/{uname}/",
        "country_code":    cc,
        "region":          _detect_region(bio, full_name, uname, cc),
        "city":            _detect_city(bio, full_name),
        "relatedProfiles": related_usernames,
        "_raw_followers":  _raw,
    }


# ── ① 키워드로 인스타그램 계정 직접 검색 ──────────────────────────
def search_by_keyword(
    keyword: str,
    max_results: int = 20,
    progress_callback=None,
    apify_token: str | None = None,
) -> tuple[list[dict], str | None]:
    """
    patient_discovery/instagram-search-users 로 키워드 → 계정 직접 검색.
    인스타그램 검색창에 타이핑하는 것과 동일한 방식.
    실패 시 해시태그 방식으로 자동 fallback.
    """
    client = _get_client(apify_token)
    if not client:
        return [], "Apify API 토큰이 없어요. 우측 상단 설정에서 토큰을 입력해주세요."

    kw = keyword.strip().lstrip("#")

    if progress_callback:
        progress_callback(f"'{kw}' 키워드로 인스타그램 계정 검색 중...")

    # ── Step 1: 멀티 키워드 + Google 검색 병행 ──────────────────────
    usernames: set[str] = set()
    keyword_followers: dict[str, int] = {}
    _last_err: str = ""

    # 방식 A — 관련 키워드 여러 개로 username/bio 검색
    # 카테고리 매핑이 있으면 사용, 없으면 자동 생성
    _predefined = _CATEGORY_KEYWORDS.get(kw, [])
    _auto = [f"{kw}인플루언서", f"{kw}크리에이터"] if not _predefined else []
    _search_terms = list(dict.fromkeys([kw] + _predefined + _auto))
    for _i, _term in enumerate(_search_terms[:4]):
        if progress_callback:
            progress_callback(f"'{_term}' 계정 검색 중... ({_i+1}/{min(len(_search_terms),4)})")
        try:
            run = client.actor(KEYWORD_ACTOR).call(
                run_input={"query": _term, "maxResults": max(30, max_results * 2)}
            )
            if not run:
                continue
            for item in client.dataset(run["defaultDatasetId"]).iterate_items():
                uname = item.get("username", "")
                if uname:
                    usernames.add(uname)
                    fc = _pick_int(item, "followersCount", "followers", "follower_count", "followedByCount")
                    if fc > 0:
                        keyword_followers[uname] = fc
        except Exception as e:
            _last_err = str(e)

    # 방식 B — Google 검색으로 Instagram 계정 발굴 (팔로워 많은 계정 적중률 높음)
    _google_queries = _CATEGORY_GOOGLE_QUERIES.get(kw, [
        f"site:instagram.com {kw} 인플루언서",
        f"instagram {kw} 크리에이터 팔로워",
    ])
    if progress_callback:
        progress_callback(f"Google에서 {kw} 인플루언서 발굴 중...")
    try:
        g_run = client.actor(SEARCH_ACTOR).call(run_input={
            "queries": "\n".join(_google_queries[:2]),
            "maxPagesPerQuery": 1,
            "resultsPerPage": 10,
        })
        if g_run:
            _ig_url_re = re.compile(r"instagram\.com/([a-zA-Z0-9_.]{2,30})/?")
            for item in client.dataset(g_run["defaultDatasetId"]).iterate_items():
                for result in (item.get("organicResults") or []):
                    _url = result.get("url") or ""
                    m = _ig_url_re.search(_url)
                    if m:
                        _u = m.group(1)
                        if _u not in ("p", "reel", "stories", "explore", "tv"):
                            usernames.add(_u)
    except Exception as e:
        _last_err = str(e)

    if not usernames:
        if "hard limit" in _last_err.lower() or "usage" in _last_err.lower():
            return [], "Apify 월간 사용량 한도를 초과했어요. Apify 대시보드에서 플랜을 확인해주세요."
        if _last_err:
            return [], f"검색 API 오류: {_last_err}"
        return [], "검색 결과가 없어요. 다른 키워드를 입력해보세요."

    # ── Step 2: 프로필 상세 수집 ────────────────────────────────────
    if progress_callback:
        progress_callback(f"후보 {len(usernames)}개 프로필 수집 중...")

    profiles, err = _fetch_profiles(list(usernames)[:100], client)
    if err:
        return [], err

    # 프로필 스크래퍼가 팔로워 0을 반환한 경우 검색 단계 값으로 보완
    for p in profiles:
        if p["followers"] == 0 and p["username"] in keyword_followers:
            p["followers"] = keyword_followers[p["username"]]

    profiles.sort(key=lambda x: x["followers"], reverse=True)
    return profiles[:max_results], None


# ── ① 정밀 팔로워 필터링 (instaprism/instagram-user-filter) ────────
def precise_filter_accounts(
    usernames: list[str],
    follower_min: int = 0,
    follower_max: int = 999_999_999,
    progress_callback=None,
    apify_token: str | None = None,
) -> tuple[list[dict], str | None]:
    """
    기존 검색 결과(username 목록)를 instaprism 필터 액터로 정밀 필터링.
    팔로워 수 범위에 정확히 맞는 계정만 반환, 프로필 정보 포함.
    비용: $7/1,000 계정 (≈ ₩10/계정)
    """
    client = _get_client(apify_token)
    if not client:
        return [], "Apify API 토큰이 없어요."
    if not usernames:
        return [], "필터링할 계정이 없어요."

    if progress_callback:
        progress_callback(f"{len(usernames)}개 계정 정밀 필터 중...")

    try:
        run = client.actor(USER_FILTER_ACTOR).call(run_input={
            "usernames":    usernames,
            "minFollowers": follower_min,
            "maxFollowers": follower_max if follower_max < 999_999_999 else None,
        })
        if not run:
            return [], "정밀 필터 실행 실패"

        results: list[dict] = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            uname = item.get("username") or item.get("userName", "")
            if not uname:
                continue
            followers = _pick_int(item, "followersCount", "followers", "followedByCount")
            following = _pick_int(item, "followingCount", "following", "friendsCount")
            bio = str(item.get("biography") or item.get("bio") or "")
            full_name = str(item.get("fullName") or item.get("full_name") or "")
            results.append({
                "username":    uname,
                "full_name":   full_name,
                "followers":   followers,
                "following":   following,
                "bio":         bio,
                "category":    _detect_category_from_bio(bio, full_name),
                "is_verified": bool(item.get("verified") or item.get("isVerified", False)),
                "profile_url": f"https://www.instagram.com/{uname}/",
                "region":      _detect_region(bio, full_name, uname, ""),
                "city":        _detect_city(bio, full_name),
                "relatedProfiles": [],
                "_raw_followers": followers,
            })

        results.sort(key=lambda x: x["followers"], reverse=True)
        return results, None
    except Exception as e:
        return [], f"정밀 필터 오류: {e}"


def estimated_precise_filter_cost(count: int) -> int:
    """계정 수 기준 정밀 필터 예상 비용 (원)"""
    return max(1, round(count * _PRECISE_FILTER_COST_PER_ACCOUNT))


# ── ② 경쟁사/브랜드 계정 게시물에서 협업 인플루언서 역추적 ─────────
def search_by_following(
    base_account: str,
    max_results: int = 30,
    progress_callback=None,
    apify_token: str | None = None,
) -> tuple[list[dict], str | None]:
    """
    경쟁사·브랜드 계정의 최근 게시물에서 태그·멘션된 계정 추출.
    → 이미 그 브랜드와 협업한 인플루언서 목록 완성.
    relatedProfiles(유사 계정)도 보완적으로 합산.
    """
    client = _get_client(apify_token)
    if not client:
        return [], "Apify API 토큰이 없어요. 우측 상단 설정에서 토큰을 입력해주세요."

    account = base_account.lstrip("@").strip()
    usernames: set[str] = set()

    # ── Step 1A: 게시물에서 태그·멘션 계정 추출 ──────────────────
    if progress_callback:
        progress_callback(f"@{account} 게시물에서 협업 계정 추출 중... (1/2)")

    try:
        post_run = client.actor(POST_ACTOR).call(
            run_input={
                "directUrls":   [f"https://www.instagram.com/{account}/"],
                "resultsType":  "posts",
                "resultsLimit": 30,
            }
        )
        if not post_run:
            raise ValueError("post_run is None")
        for item in client.dataset(post_run["defaultDatasetId"]).iterate_items():
            # 캡션에서 @멘션 추출
            caption = item.get("caption") or item.get("alt", "")
            for mention in re.findall(r"@([\w.]+)", caption):
                if mention.lower() != account.lower():
                    usernames.add(mention)
            # taggedUsers 필드
            for tu in item.get("taggedUsers") or []:
                uname = tu.get("username", "")
                if uname and uname.lower() != account.lower():
                    usernames.add(uname)
    except Exception as e:
        if "hard limit" in str(e).lower() or "usage" in str(e).lower():
            return [], "Apify 월간 사용량 한도를 초과했어요. Apify 대시보드에서 플랜을 확인해주세요."

    # ── Step 1B: relatedProfiles 보완 ────────────────────────────
    try:
        prof_run = client.actor(PROFILE_ACTOR).call(
            run_input={"usernames": [account]}
        )
        if not prof_run:
            raise ValueError("prof_run is None")
        for item in client.dataset(prof_run["defaultDatasetId"]).iterate_items():
            for rel in item.get("relatedProfiles") or []:
                uname = rel.get("username", "")
                if uname and uname.lower() != account.lower():
                    usernames.add(uname)
    except Exception as e:
        if "hard limit" in str(e).lower() or "usage" in str(e).lower():
            return [], "Apify 월간 사용량 한도를 초과했어요. Apify 대시보드에서 플랜을 확인해주세요."

    if not usernames:
        return [], f"@{account}에서 연관 계정을 찾지 못했어요. 계정명을 확인해주세요."

    # ── Step 2: 연관 계정 상세 프로필 수집 ───────────────────────
    if progress_callback:
        progress_callback(f"{len(usernames)}개 연관 계정 프로필 수집 중... (2/2)")

    profiles, err = _fetch_profiles(list(usernames)[:max_results], client)
    if err:
        return [], err

    profiles.sort(key=lambda x: x["followers"], reverse=True)
    return profiles, None


# ── 공통: 사용자명 목록 → 프로필 상세 ────────────────────────────
def _fetch_profiles(
    usernames: list[str],
    client: ApifyClient,
) -> tuple[list[dict], str | None]:
    try:
        run = client.actor(PROFILE_ACTOR).call(
            run_input={"usernames": usernames}
        )
    except Exception as e:
        msg = str(e)
        if "hard limit" in msg.lower() or "usage" in msg.lower():
            return [], "Apify 월간 사용량 한도를 초과했어요. Apify 대시보드에서 플랜을 확인해주세요."
        return [], f"프로필 수집 오류: {msg}"

    profiles = []
    if run:
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            p = _normalize_profile(item)
            if p["username"]:
                profiles.append(p)
    return profiles, None


# ── 유사 계정 탐색 헬퍼 ──────────────────────────────────────────
_GENERIC_HASHTAGS = frozenset({
    "인스타그램", "일상", "daily", "photo", "instagood", "instagram",
    "love", "follow", "like", "감성", "소통", "맞팔", "선팔",
    "beautiful", "picoftheday", "photooftheday", "selfie", "style",
    "korea", "한국", "서울", "seoul",
})


def _extract_top_hashtags(captions: list[str], n: int = 5) -> list[str]:
    counts: dict[str, int] = {}
    tag_re = re.compile(r"#([\w가-힣]+)")
    for cap in captions:
        for tag in tag_re.findall(cap.lower()):
            if tag not in _GENERIC_HASHTAGS and len(tag) >= 2:
                counts[tag] = counts.get(tag, 0) + 1
    sorted_tags = sorted(counts, key=lambda t: counts[t], reverse=True)
    return sorted_tags[:n]


def _similar_follower_range(followers: int) -> tuple[int, int]:
    lo = max(100, int(followers * 0.2))
    hi = int(followers * 5.0)
    return lo, hi


def _calc_similarity(base: dict, cand: dict) -> int:
    score = 0
    base_f = base.get("followers", 0) or 1
    cand_f = cand.get("followers", 0) or 1
    ratio = min(base_f, cand_f) / max(base_f, cand_f)
    score += int(ratio * 50)

    base_cat = base.get("카테고리", "")
    cand_cat = cand.get("카테고리", "")
    if base_cat and cand_cat and base_cat == cand_cat:
        score += 25

    base_bio = (base.get("bio", "") or "").lower()
    cand_bio = (cand.get("bio", "") or "").lower()
    base_words = set(re.findall(r"[\w가-힣]{2,}", base_bio))
    cand_words = set(re.findall(r"[\w가-힣]{2,}", cand_bio))
    if base_words and cand_words:
        overlap = len(base_words & cand_words) / len(base_words | cand_words)
        score += int(overlap * 25)

    return min(score, 100)


def _extract_bio_keywords(bio: str, full_name: str) -> list[str]:
    """바이오에서 의미있는 검색 키워드 2~3개 추출"""
    stopwords = {
        "and", "the", "for", "with", "from", "have", "this", "that",
        "일상", "소통", "맞팔", "선팔", "계정", "스타그램", "그램",
        "공식", "official", "page", "계", "님", "저는", "합니다",
    }
    text = f"{full_name} {bio}"
    tokens = re.findall(r"[가-힣a-zA-Z]{2,}", text)
    seen: set[str] = set()
    result: list[str] = []
    for tok in tokens:
        t = tok.lower()
        if t not in stopwords and t not in seen:
            seen.add(t)
            result.append(tok)
        if len(result) >= 3:
            break
    return result


def search_similar_creators(
    username: str,
    max_results: int = 20,
    progress_callback=None,
    apify_token: str | None = None,
) -> tuple[list[dict], str | None]:
    """
    계정 하나 입력 → 비슷한 계정 자동 발굴
    탐색 방식: relatedProfiles + 게시물 해시태그 + 바이오 키워드 + 카테고리 검색
    """
    client = _get_client(apify_token)
    if not client:
        return [], "Apify API 토큰이 없어요. 우측 상단 설정에서 토큰을 입력해주세요."

    # ── Step 1: 기준 계정 프로필 수집 ─────────────────────────────
    if progress_callback:
        progress_callback(f"앨리가 @{username} 계정을 분석하고 있어요 ✨")

    base_profiles, err = _fetch_profiles([username], client)
    if err:
        return [], err
    if not base_profiles:
        return [], f"@{username} 프로필을 찾지 못했어요. 공개 계정인지 확인해주세요."

    base = base_profiles[0]
    base_followers = base.get("followers", 0) or 0
    base_bio = base.get("bio", "") or ""
    base_full = base.get("full_name", "") or ""
    base_category = _detect_category_from_bio(base_bio, base_full)

    # 팔로워 범위를 좀 더 넉넉하게 (0.1x ~ 10x)
    lo_f = max(100, int(base_followers * 0.1)) if base_followers else 0
    hi_f = int(base_followers * 10) if base_followers else 999_999_999

    candidates: set[str] = set()

    # 소스 A: relatedProfiles (API가 제공하는 연관 계정)
    candidates.update(base.get("relatedProfiles", []))

    # ── Step 2: 게시물 해시태그 + 바이오 키워드 수집 ─────────────
    if progress_callback:
        progress_callback("앨리가 게시물과 바이오를 읽어보고 있어요 🔍")

    captions: list[str] = []
    try:
        post_run = client.actor(POST_ACTOR).call(
            run_input={
                "directUrls": [f"https://www.instagram.com/{username}/"],
                "resultsType": "posts",
                "resultsLimit": 15,
            }
        )
        if post_run:
            for item in client.dataset(post_run["defaultDatasetId"]).iterate_items():
                cap = item.get("caption") or item.get("text") or ""
                if cap:
                    captions.append(cap)
    except Exception:
        pass

    top_tags = _extract_top_hashtags(captions, n=4)
    bio_keywords = _extract_bio_keywords(base_bio, base_full)

    # 검색할 키워드 목록: 해시태그 + 바이오 키워드 + 카테고리
    search_keywords: list[str] = []
    search_keywords.extend(top_tags[:3])
    search_keywords.extend(bio_keywords[:2])
    if base_category:
        search_keywords.append(base_category)
    # 중복 제거, 최대 6개
    seen_kw: set[str] = set()
    unique_kws: list[str] = []
    for kw in search_keywords:
        if kw.lower() not in seen_kw:
            seen_kw.add(kw.lower())
            unique_kws.append(kw)
        if len(unique_kws) >= 6:
            break

    # ── Step 3: 키워드별 계정 탐색 ────────────────────────────────
    if progress_callback:
        kw_preview = ", ".join(unique_kws[:3])
        progress_callback(f"앨리가 '{kw_preview}' 키워드로 유사 계정을 찾고 있어요 🕵️")

    for kw in unique_kws:
        if len(candidates) >= 80:
            break
        try:
            kw_run = client.actor(KEYWORD_ACTOR).call(
                run_input={"query": kw, "maxResults": 30}
            )
            if not kw_run:
                continue
            for item in client.dataset(kw_run["defaultDatasetId"]).iterate_items():
                uname = (item.get("username") or item.get("userName") or "").strip()
                if uname and uname != username:
                    candidates.add(uname)
        except Exception:
            continue

    # ── Step 4: 해시태그 scraper로 보완 (계정이 부족하면) ─────────
    if len(candidates) < 15 and top_tags:
        if progress_callback:
            progress_callback("앨리가 해시태그로 추가 계정을 더 찾아보고 있어요 📎")
        for tag in top_tags[:2]:
            try:
                ht_run = client.actor(HASHTAG_ACTOR).call(
                    run_input={"hashtags": [tag], "resultsLimit": 30}
                )
                if not ht_run:
                    continue
                for item in client.dataset(ht_run["defaultDatasetId"]).iterate_items():
                    uname = (
                        item.get("ownerUsername")
                        or (item.get("owner") or {}).get("username", "")
                    )
                    if uname and uname != username:
                        candidates.add(uname)
                if len(candidates) >= 40:
                    break
            except Exception:
                continue

    candidates.discard(username)

    if not candidates:
        return [], (
            f"@{username}과 비슷한 계정을 찾지 못했어요.\n"
            "계정이 비공개이거나 게시물·바이오가 없으면 탐색이 어려울 수 있어요."
        )

    # ── Step 5: 후보 계정 상세 프로필 + 유사도 점수 ───────────────
    candidate_list = list(candidates)[:60]
    if progress_callback:
        progress_callback(f"앨리가 {len(candidate_list)}개 후보를 유사도 기준으로 분석하고 있어요 🤖")

    profiles, err = _fetch_profiles(candidate_list, client)
    if err:
        return [], err

    results = []
    for p in profiles:
        f = p.get("followers", 0) or 0
        if base_followers > 0 and not (lo_f <= f <= hi_f):
            continue
        p["유사도"] = _calc_similarity(base, p)
        results.append(p)

    # 유사도 낮아도 결과가 너무 없으면 범위 무시하고 포함
    if len(results) < 5:
        for p in profiles:
            if p not in results:
                p["유사도"] = _calc_similarity(base, p)
                results.append(p)

    results.sort(key=lambda x: x["유사도"], reverse=True)
    return results[:max_results], None


# ── 분석 헬퍼 함수들 ──────────────────────────────────────────────
def _tier_er_benchmark(followers: int) -> float:
    for min_f, er in _ER_BENCHMARKS:
        if followers >= min_f:
            return er
    return 5.2


def _tier_reach_benchmark(followers: int) -> float:
    for min_f, reach in _REELS_REACH_BENCHMARKS:
        if followers >= min_f:
            return reach
    return 70.0


def _calc_emv(avg_likes: float, avg_comments: float, avg_views: float) -> dict:
    usd = avg_likes * 0.014 + avg_comments * 0.12 + avg_views / 1000 * 7.0
    return {"emv_usd": round(usd, 2), "emv_krw": round(usd * 1_350)}


def _parse_ts(raw) -> datetime | None:
    try:
        if isinstance(raw, (int, float)):
            return datetime.fromtimestamp(raw, tz=timezone.utc)
        if isinstance(raw, str):
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        pass
    return None


def _analyze_comments(comments: list[str]) -> dict:
    if not comments:
        return {"purchase_intent_pct": 0.0, "low_quality_pct": 0.0, "total": 0}
    total = len(comments)
    purchase = sum(
        1 for c in comments if any(p in c.lower() for p in _PURCHASE_INTENT)
    )
    low_q = sum(
        1 for c in comments
        if len(c.strip()) <= 3
        or bool(_EMOJI_ONLY_RE.match(c.strip()))
        or any(p in c.lower() for p in _LOW_QUALITY)
    )
    return {
        "purchase_intent_pct": round(purchase / total * 100, 1),
        "low_quality_pct":     round(low_q / total * 100, 1),
        "total":               total,
    }


_GUGU_KEYWORDS = [
    "공동구매", "공구오픈", "공구 오픈", "공구링크", "공구 링크",
    "공구중", "공구 중", "공구해요", "공구합니다", "공구 진행", "공구",
    "단체구매", "그룹구매",
    "지금 오픈", "오픈중", "오픈 중", "판매중", "판매 중",
    "주문받아요", "주문 받아요", "주문하러", "구매하러",
    "마감임박", "마감 임박", "마감 d-", "선착순", "한정수량", "한정 수량",
    "할인코드", "쿠폰코드", "내 코드", "제 코드", "my code", "use code",
]
_GUGU_ACTIVE = [
    "지금 오픈", "오픈중", "오픈 중", "진행중", "진행 중",
    "주문받아요", "마감임박", "마감 임박", "선착순", "한정수량",
]


def _analyze_gugu_activity(caption_ts: list[tuple[str, object]]) -> dict:
    """캡션+타임스탬프 리스트에서 공동구매 활동 여부를 분석"""
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    total = len(caption_ts)
    gugu_posts: list[dict] = []

    for caption, ts in caption_ts:
        cap_low = caption.lower()
        if any(kw in cap_low for kw in _GUGU_KEYWORDS):
            is_active_signal = any(kw in cap_low for kw in _GUGU_ACTIVE)
            gugu_posts.append({"ts": ts, "active_signal": is_active_signal, "caption": caption[:100]})

    if not gugu_posts:
        return {
            "공구_여부": False, "공구_빈도": 0, "공구_게시물수": 0,
            "최근_공구": None, "현재_공구_활성": False, "공구_요약": "공구 활동 없음",
        }

    gugu_count = len(gugu_posts)
    freq_pct   = round(gugu_count / total * 100, 1) if total else 0

    # 최근 공구 날짜
    dated = [p for p in gugu_posts if p["ts"]]
    dated.sort(key=lambda x: x["ts"], reverse=True)
    latest = dated[0]["ts"] if dated else None
    latest_str = latest.strftime("%Y-%m-%d") if latest else "날짜 미상"

    # 현재 활성: 최근 30일 이내에 활성 시그널 있는 공구 포스트
    recent_active = any(
        p["active_signal"] and p["ts"] and (now - p["ts"]).days <= 30
        for p in gugu_posts
    )

    # 빈도 요약
    if freq_pct >= 30:
        freq_label = f"매우 활발 (전체 게시물의 {freq_pct:.0f}%)"
    elif freq_pct >= 10:
        freq_label = f"활발 (전체 게시물의 {freq_pct:.0f}%)"
    else:
        freq_label = f"간헐적 (전체 게시물의 {freq_pct:.0f}%)"

    summary = f"{'🟢 현재 진행 중' if recent_active else '⏸ 최근 활동 없음'} | 총 {gugu_count}건 | {freq_label} | 마지막: {latest_str}"

    return {
        "공구_여부": True,
        "공구_빈도": freq_pct,
        "공구_게시물수": gugu_count,
        "최근_공구": latest_str,
        "현재_공구_활성": recent_active,
        "공구_요약": summary,
    }


def _analyze_commerce_signals(bio: str, captions: list[str]) -> int:
    """바이오 + 캡션에서 상업 활동 시그널을 분석해 0-100 점수 반환"""
    score = 0
    bio_low = bio.lower()
    cap_text = " ".join(captions[:20]).lower()
    all_text = bio_low + " " + cap_text

    # 쇼핑 도메인/플랫폼 링크
    shop_hits = sum(1 for d in _SHOPPING_DOMAINS if d in all_text)
    score += min(shop_hits * 18, 36)

    # 구매 CTA 키워드
    cta_hits = sum(1 for kw in _SHOPPING_CTA_KW if kw in all_text)
    score += min(cta_hits * 6, 24)

    # 협찬/협업 시그널 (브랜드가 이미 선택한 계정)
    collab_hits = sum(1 for kw in _COLLAB_SIGNAL_KW if kw in all_text)
    score += min(collab_hits * 5, 20)

    # 할인코드 패턴 (대문자+숫자: CODE10, SPRING20 등)
    code_hits = len(re.findall(r'\b[A-Z]{2,8}\d{1,3}\b', bio + " " + " ".join(captions[:5])))
    score += min(code_hits * 15, 20)

    return min(score, 100)


_CONTENT_TYPE_KW = {
    "정보형": ["꿀팁", "루틴", "비교", "체크리스트", "후기", "팁", "방법", "추천", "리뷰", "정보", "before", "after", "알아야", "정리", "차이"],
    "감성형": ["일상", "감성", "에세이", "셀카", "브이로그", "daily", "vlog", "그냥", "요즘", "오늘의"],
    "공구형": ["공구", "공동구매", "오픈", "링크", "할인", "쿠폰", "구매"],
    "광고형": ["광고", "협찬", "유료광고", "#ad", "#sponsored", "제공"],
}
_SAVE_INDUCING_KW = [
    "루틴", "꿀팁", "비교", "before", "after", "체크리스트",
    "실패", "추천", "방법", "정리", "알아야", "저장", "북마크",
]


def _analyze_content_mix(caption_ts: list[tuple[str, object]]) -> dict:
    """캡션으로 콘텐츠 타입 분류 + 저장 유도형 비율 계산"""
    type_counts = {k: 0 for k in _CONTENT_TYPE_KW}
    save_inducing = 0
    total = len(caption_ts)
    if not total:
        return {"콘텐츠_타입": {}, "저장유도형_비율": 0.0, "주요_콘텐츠_타입": "정보 없음"}

    for caption, _ in caption_ts:
        cap_low = caption.lower()
        matched = []
        for ctype, kws in _CONTENT_TYPE_KW.items():
            if any(kw in cap_low for kw in kws):
                type_counts[ctype] += 1
                matched.append(ctype)
        if any(kw in cap_low for kw in _SAVE_INDUCING_KW):
            save_inducing += 1

    pct_map = {k: round(v / total * 100, 1) for k, v in type_counts.items()}
    dominant = max(type_counts.keys(), key=lambda k: type_counts[k])
    if type_counts[dominant] == 0:
        dominant = "미분류"

    return {
        "콘텐츠_타입": pct_map,
        "저장유도형_비율": round(save_inducing / total * 100, 1),
        "주요_콘텐츠_타입": dominant,
    }


def _analyze_view_stability(video_posts: list[dict], followers: int) -> dict:
    """조회수 안정성 + 팔로워 대비 조회수 효율"""
    views = [p["views"] for p in video_posts if p["views"] > 0]
    if not views:
        return {"조회수_안정성": 0, "안정형_비율": 0.0, "최소_조회수": 0, "팔로워_조회수_효율": 0.0}

    avg_v = sum(views) / len(views)
    stable = sum(1 for v in views if v >= avg_v * 0.3)
    stability_pct = round(stable / len(views) * 100, 1)

    # 안정성 점수: 80%+ stable→100, 60%→70, 40%→40, <40%→20
    if stability_pct >= 80:   stability_score = 100
    elif stability_pct >= 60: stability_score = 70
    elif stability_pct >= 40: stability_score = 40
    else:                     stability_score = 20

    follower_efficiency = round(avg_v / followers * 100, 1) if followers else 0.0

    return {
        "조회수_안정성": stability_score,
        "안정형_비율": stability_pct,
        "최소_조회수": min(views),
        "팔로워_조회수_효율": follower_efficiency,
    }


def _analyze_upload_pattern(caption_ts: list[tuple[str, object]]) -> dict:
    """업로드 패턴: 주간 업로드 빈도 + 마지막 업로드 이후 경과일"""
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    from datetime import datetime as _dt
    raw = [ts for _, ts in caption_ts if ts is not None]
    timestamps: list[_dt] = sorted(raw, key=lambda t: t, reverse=True)  # type: ignore[arg-type]

    if not timestamps:
        return {"주간_업로드수": 0.0, "마지막_업로드_경과일": None, "활성_상태": "정보 없음"}

    days_since_last = (now - timestamps[0]).days

    # 최근 90일 내 포스트 수로 주간 업로드 계산
    cutoff = now - timedelta(days=90)
    recent_posts = [t for t in timestamps if t >= cutoff]
    posts_per_week = round(len(recent_posts) / 13, 1)  # 90일 = 13주

    if days_since_last <= 7:
        active_status = "🟢 활성"
    elif days_since_last <= 30:
        active_status = "🟡 보통"
    else:
        active_status = "🔴 비활성"

    return {
        "주간_업로드수": posts_per_week,
        "마지막_업로드_경과일": days_since_last,
        "활성_상태": active_status,
    }


def _scrape_comments_deep(post_urls: list[str], limit_per_post: int, client) -> list[str]:
    """상위 게시물 URL 목록에서 댓글을 대량 수집 (deep comment 옵션용)"""
    if not post_urls:
        return []
    try:
        run = client.actor(POST_ACTOR).call(run_input={
            "directUrls":   post_urls,
            "resultsType":  "comments",
            "resultsLimit": limit_per_post,
        })
        if not run:
            return []
        comments: list[str] = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            text = item.get("text") or item.get("ownerUsername", "")
            if isinstance(text, str) and text.strip():
                comments.append(text.strip())
        return comments
    except Exception:
        return []


def _web_search_brand_signals(username: str, client) -> dict:
    """Google 검색으로 브랜드 협업/상업 활동 시그널 수집"""
    try:
        queries = "\n".join([
            f'"{username}" 인스타 협찬 브랜드 공구',
            f'instagram.com/{username} 후기 구매',
        ])
        run = client.actor(SEARCH_ACTOR).call(run_input={
            "queries": queries,
            "maxPagesPerQuery": 1,
            "resultsPerPage": 5,
        })
        if not run:
            return {"web_mentions": 0, "web_brand_signals": 0}

        brand_kw = ["협찬", "협업", "콜라보", "공구", "구매", "쇼핑", "브랜드", "리뷰", "후기", "brand", "collab", "shop"]
        brand_signals = 0
        mention_count = 0
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            for result in (item.get("organicResults") or []):
                text = ((result.get("title") or "") + " " + (result.get("snippet") or "")).lower()
                if any(kw in text for kw in brand_kw):
                    brand_signals += 1
                mention_count += 1

        return {"web_mentions": mention_count, "web_brand_signals": brand_signals}
    except Exception:
        return {"web_mentions": 0, "web_brand_signals": 0}


def _detect_brand_fit(captions: list[str], bio: str) -> str:
    text = " ".join(captions + [bio]).lower()
    scores = {cat: sum(1 for kw in kws if kw in text) for cat, kws in _BRAND_KEYWORDS.items()}
    best = max(scores.keys(), key=lambda k: scores[k])
    return best if scores[best] > 0 else "라이프스타일"


def _calc_scores(
    avg_views: int, view_variance: float, comment_rate: float,
    engagement_rate: float, ad_ratio: float, cq: dict,
    ghost_estimate: float = 0, trend: str = "", ad_er_penalty: float = 0,
    followers: int = 0, following: int = 0,
    commerce_score: int = 0, web_brand_signals: int = 0,
) -> dict:
    def _vs(v):
        if v >= 1_000_000: return 100
        if v >= 500_000:   return 85
        if v >= 100_000:   return 70
        if v >= 50_000:    return 55
        if v >= 10_000:    return 40
        return 20

    def _vr(r):
        if r <= 2:  return 90
        if r <= 3:  return 75
        if r <= 5:  return 60
        if r <= 10: return 40
        return 20

    def _cs(r):
        if r >= 0.5:  return 95
        if r >= 0.3:  return 80
        if r >= 0.1:  return 60
        if r >= 0.05: return 40
        return 20

    def _es(r):
        # views 기준 ER: 릴스 업계 평균 ~3-5%
        # followers 기준 ER(이미지): 업계 평균 ~3-5%
        if r >= 5:   return 95
        if r >= 3:   return 80
        if r >= 1.5: return 60
        if r >= 0.5: return 40
        return 20

    vs = _vs(avg_views)
    vr = _vr(view_variance) if view_variance else 90
    cs = _cs(comment_rate)
    es = _es(engagement_rate)
    quality_s       = max(0, 100 - cq["low_quality_pct"])
    purchase_intent = min(cq["purchase_intent_pct"] * 10, 100)

    # 유령 팔로워 패널티 (50% 이상이면 점수 할인)
    ghost_penalty = min(ghost_estimate / 100, 0.4)

    seeding  = min(int((vs * 0.3 + vr * 0.2 + cs * 0.3 + es * 0.2) * (1 - ghost_penalty * 0.5)), 100)
    fandom   = min(int(cs * 0.4 + quality_s * 0.4 + vr * 0.2), 100)

    # 구매전환: 댓글 구매의도 + 참여율 + 상업 활동 시그널(링크·코드·협찬) 반영
    purchase = min(int(
        purchase_intent * 0.35
        + cs * 0.20
        + max(0, 100 - ad_ratio * 1.5) * 0.15
        + commerce_score * 0.30        # 쇼핑링크·할인코드·협찬 시그널
    ), 100)

    # 공구 적합도: 팬덤 + 구매전환 + 상업 활동 복합
    gugu = min(int(
        (fandom * 0.40 + purchase * 0.40 + commerce_score * 0.20)
        * (1 - min(ad_ratio, 70) / 200)
    ), 100)

    # 웹 검색 브랜드 시그널 보정 (실제 외부 언급이 있으면 상업성 신뢰도 ↑)
    if web_brand_signals >= 2:
        purchase = min(purchase + web_brand_signals * 4, 100)
        gugu     = min(gugu     + web_brand_signals * 3, 100)
    if web_brand_signals >= 4:
        seeding  = min(seeding  + 5, 100)  # 외부 언급 많으면 도달력도 검증된 계정

    risk: list[str] = []
    if view_variance > 10:                      risk.append("조회수 편차 심함")
    if comment_rate < 0.05:                     risk.append("댓글률 매우 낮음")
    if cq["low_quality_pct"] > 70:              risk.append("저품질 댓글 많음")
    if ad_ratio > 70:                           risk.append("광고 비율 과다")
    if engagement_rate < 0.5:                   risk.append("참여율 낮음")
    if ghost_estimate > 50:                     risk.append(f"유령 팔로워 추정 {ghost_estimate:.0f}%")
    if "급락" in trend:                         risk.append("참여율 급락 추세")
    if ad_er_penalty > 30:                      risk.append(f"광고 반응 {ad_er_penalty:.0f}% 저하")
    if following > 5000 and followers < 50_000: risk.append("팔로잉 수 과다")

    risk_level = "🟢 낮음" if not risk else ("🟡 보통" if len(risk) <= 2 else "🔴 높음")

    return {
        "seeding": seeding, "fandom": fandom,
        "purchase": purchase, "gugu": gugu,
        "risk_level": risk_level, "risk_signals": risk,
    }


def _generate_report(
    avg_views: int, ad_ratio: float, scores: dict, brand_fit: str,
    view_variance: float, cq: dict, trend: str = "",
    ghost_estimate: float = 0, ad_er_penalty: float = 0, emv_krw: int = 0,
) -> str:
    parts = []

    if avg_views >= 100_000:
        parts.append(f"이 계정은 평균 {avg_views:,} 조회수를 기록하는 상위권 계정입니다.")
    elif avg_views >= 10_000:
        parts.append(f"평균 {avg_views:,} 조회수로 안정적인 도달력을 보유합니다.")
    else:
        parts.append("평균 조회수가 낮아 광고 도달력은 제한적입니다.")

    if trend:
        if "성장" in trend:
            parts.append("최근 게시물 참여율이 상승 중인 성장형 계정입니다.")
        elif "급락" in trend:
            parts.append("⚠️ 최근 게시물 참여율이 급격히 하락 중입니다. 팔로워 이탈 또는 광고 피로 가능성이 있습니다.")
        elif "하락" in trend:
            parts.append("최근 참여율이 소폭 하락 중으로, 추이 모니터링이 필요합니다.")

    if view_variance and view_variance <= 2:
        parts.append("조회수가 고르게 유지되는 안정형 계정입니다.")
    elif view_variance and view_variance > 10:
        parts.append("특정 영상에만 조회수가 집중되는 바이럴 원툴 패턴이 감지됩니다.")

    if ghost_estimate > 40:
        parts.append(f"팔로워 대비 참여율이 낮아 유령 팔로워가 약 {ghost_estimate:.0f}% 수준으로 추정됩니다.")

    if scores["fandom"] >= 70:
        parts.append("댓글 품질과 참여도가 우수하여 팬덤 충성도가 높습니다.")
    elif scores["fandom"] >= 50:
        parts.append("팬덤 충성도는 보통 수준입니다.")
    else:
        parts.append("댓글 참여가 낮아 팬덤 형성이 미흡합니다.")

    if cq["purchase_intent_pct"] >= 10:
        parts.append(f"구매 의도 댓글 비율이 {cq['purchase_intent_pct']}%로 높아 공구·시딩 효과가 기대됩니다.")

    parts.append(f"콘텐츠 분석 결과 {brand_fit} 카테고리 제품과 높은 적합도를 보입니다.")

    if ad_er_penalty > 30:
        parts.append(f"광고 게시물의 반응이 일반 콘텐츠 대비 {ad_er_penalty:.0f}% 낮아 광고 피로도가 감지됩니다.")
    elif ad_er_penalty < 10 and ad_ratio > 0:
        parts.append("광고 콘텐츠에도 일반 게시물과 유사한 반응을 보여 팔로워 신뢰도가 높습니다.")

    if ad_ratio > 50:
        parts.append(f"최근 광고 비율이 {ad_ratio:.0f}%로 높아 피로도 관리가 필요합니다.")
    elif ad_ratio <= 30 and ad_ratio >= 0:
        parts.append(f"광고 비율({ad_ratio:.0f}%)이 적절하여 콘텐츠 신뢰도가 유지됩니다.")

    if emv_krw > 0:
        parts.append(f"게시물 1개당 예상 미디어 가치(EMV)는 약 {emv_krw:,}원입니다.")

    if scores["risk_level"].startswith("🔴"):
        parts.append(f"⚠️ 위험 신호 감지({', '.join(scores['risk_signals'])}). 계약 전 추가 검증을 권장합니다.")

    return " ".join(parts)


# ── 계정별 릴스·게시물 상세 분석 ──────────────────────────────────
def analyze_account(
    username: str,
    posts_limit: int = 50,
    progress_callback=None,
    bio: str = "",
    followers: int = 0,
    following: int = 0,
    apify_token: str | None = None,
    web_search: bool = False,
    deep_comments: bool = False,
    deep_comments_limit: int = 500,
) -> tuple[dict, str | None]:
    client = _get_client(apify_token)
    if not client:
        return {}, "Apify API 토큰이 없어요. 우측 상단 설정에서 토큰을 입력해주세요."

    if progress_callback:
        progress_callback(f"@{username} 게시물 수집 중...")

    try:
        run = client.actor(POST_ACTOR).call(
            run_input={
                "directUrls":   [f"https://www.instagram.com/{username}/"],
                "resultsType":  "posts",
                "resultsLimit": posts_limit,
            }
        )
    except Exception as e:
        return {}, f"게시물 수집 오류: {e}"

    if not run:
        return {}, f"@{username} 게시물 데이터를 가져오지 못했어요."

    posts_data: list[dict] = []
    captions: list[str] = []
    caption_ts: list[tuple[str, object]] = []   # (caption, datetime|None)
    all_comments: list[str] = []
    post_urls_by_views: list[tuple[int, str]] = []  # (views, url) for deep comment sorting

    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        likes = int(item.get("likesCount") or item.get("likes", 0) or 0)
        cmts  = int(item.get("commentsCount") or item.get("comments", 0) or 0)
        views = int(
            item.get("videoViewCount") or item.get("videoPlayCount")
            or item.get("playCount") or item.get("viewCount") or 0
        )
        is_video = item.get("type") in ("Video", "Reel") or views > 0
        caption  = str(item.get("caption") or "")
        cap_low  = caption.lower()
        is_ad    = any(kw in cap_low for kw in _AD_KEYWORDS)
        ts       = _parse_ts(item.get("timestamp") or item.get("takenAt") or item.get("taken_at_timestamp"))

        captions.append(caption)
        caption_ts.append((caption, ts))
        for c in (item.get("latestComments") or []):
            text = c.get("text", "") if isinstance(c, dict) else str(c)
            if text:
                all_comments.append(text)

        # post URL 수집 (deep_comments용)
        _url = item.get("url") or item.get("shortCode") and f"https://www.instagram.com/p/{item['shortCode']}/"
        if _url:
            post_urls_by_views.append((views, str(_url)))

        posts_data.append({
            "likes": likes, "cmts": cmts, "views": views,
            "is_video": is_video, "is_ad": is_ad, "ts": ts,
        })

    if not posts_data:
        return {}, f"@{username} 게시물 데이터를 가져오지 못했어요."

    def _avg(lst: list) -> int:   return round(sum(lst) / len(lst)) if lst else 0
    def _pct(a: float, b: float) -> float: return round(a / b * 100, 2) if b else 0.0

    total_posts  = len(posts_data)

    # 릴스/비디오 포스트만 따로 분리 (일관된 분모 사용을 위해)
    video_posts = [p for p in posts_data if p["is_video"] and p["views"] > 0]
    reels_views = [p["views"] for p in video_posts]

    avg_views    = _avg(reels_views)
    max_views    = max(reels_views) if reels_views else 0
    view_variance = round(max_views / avg_views, 1) if avg_views and max_views else 0.0

    # 전체 포스트 기준 (팔로워 ER에 사용)
    avg_likes    = _avg([p["likes"] for p in posts_data])
    avg_comments = _avg([p["cmts"]  for p in posts_data])

    # 데이터 품질 체크: 좋아요/댓글이 0이어도 캡션이 있으면 공구 분석은 진행
    _engagement_ok = not (total_posts >= 5 and avg_likes == 0 and avg_comments == 0)
    if not _engagement_ok:
        # 캡션이 있으면 공구 분석만 반환
        _non_empty = [c for c in captions if c.strip()]
        if _non_empty:
            _gugu     = _analyze_gugu_activity(caption_ts)
            _commerce = _analyze_commerce_signals(bio, captions)
            _cmix     = _analyze_content_mix(caption_ts)
            _upat     = _analyze_upload_pattern(caption_ts)
            return {
                "계정명": username, "분석_상태": "캡션 전용 (참여 데이터 수집 실패)",
                "공구_여부": _gugu["공구_여부"],
                "공구_요약": _gugu["공구_요약"],
                "공구_게시물수": _gugu["공구_게시물수"],
                "공구_빈도(%)": _gugu["공구_빈도"],
                "현재_공구_활성": _gugu["현재_공구_활성"],
                "최근_공구": _gugu["최근_공구"],
                "상업활동 지수": _commerce,
                "콘텐츠_타입": _cmix["콘텐츠_타입"],
                "주요_콘텐츠_타입": _cmix["주요_콘텐츠_타입"],
                "저장유도형_비율": _cmix["저장유도형_비율"],
                "주간_업로드수": _upat["주간_업로드수"],
                "마지막_업로드_경과일": _upat["마지막_업로드_경과일"],
                "활성_상태": _upat["활성_상태"],
            }, None
        return {}, (
            f"@{username} 게시물 지표(좋아요·댓글·캡션) 수집 실패 — "
            "Instagram 데이터 제한 또는 비공개 계정일 수 있어요."
        )

    # 릴스 전용 좋아요/댓글 (조회수 기준 ER 계산에 사용)
    reels_avg_likes = _avg([p["likes"] for p in video_posts]) if video_posts else 0
    reels_avg_cmts  = _avg([p["cmts"]  for p in video_posts]) if video_posts else 0

    # comment_rate / engage_rate: 릴스 포스트끼리 일관된 분모 사용
    # 릴스 없는 계정은 팔로워 기준으로 fallback
    if video_posts and avg_views > 0:
        comment_rate = _pct(reels_avg_cmts,  avg_views)
        engage_rate  = _pct(reels_avg_likes + reels_avg_cmts, avg_views)
    else:
        comment_rate = _pct(avg_comments, max(followers, 1))
        engage_rate  = _pct(avg_likes + avg_comments, max(followers, 1))

    ad_ratio = _pct(sum(1 for p in posts_data if p["is_ad"]), total_posts)

    # ── 참여 추세: 최근 5개 vs 이전 10개 ────────────────────────────
    trend = ""
    if len(posts_data) >= 15:
        def _post_er(p: dict) -> float:
            denom = p["views"] if p["views"] else max(followers, 1)
            return (p["likes"] + p["cmts"]) / denom * 100
        recent_er  = sum(_post_er(p) for p in posts_data[:5])  / 5
        older_er   = sum(_post_er(p) for p in posts_data[5:15]) / 10
        if older_er > 0:
            ratio = (recent_er - older_er) / older_er
            if   ratio >  0.15: trend = "📈 성장형"
            elif ratio < -0.40: trend = "📉 급락형"
            elif ratio < -0.25: trend = "📉 하락형"
            else:               trend = "➡️ 안정형"

    # ── 광고 vs 일반 콘텐츠 ER 비교 ─────────────────────────────────
    ad_posts      = [p for p in posts_data if p["is_ad"]]
    organic_posts = [p for p in posts_data if not p["is_ad"]]

    def _avg_er(post_list: list) -> float:
        """포스트별 ER 평균. 릴스면 조회수, 이미지면 팔로워 기준."""
        if not post_list:
            return 0.0
        def _denom(p):
            return p["views"] if p["is_video"] and p["views"] > 0 else max(followers, 1)
        return round(
            sum((p["likes"] + p["cmts"]) / _denom(p) * 100 for p in post_list)
            / len(post_list), 2
        )

    ad_er      = _avg_er(ad_posts)
    organic_er = _avg_er(organic_posts)
    ad_er_penalty = round((1 - ad_er / organic_er) * 100, 1) if organic_er else 0.0

    # ── 팔로워 퀄리티 추정 ──────────────────────────────────────────
    expected_er    = _tier_er_benchmark(followers) if followers else 0.0
    actual_er_base = _pct(avg_likes + avg_comments, followers) if followers else 0.0
    ghost_estimate = max(0.0, round((1 - actual_er_base / expected_er) * 100, 1)) if expected_er else 0.0

    reels_reach_rate    = _pct(avg_views, followers) if followers and avg_views else 0.0
    expected_reach_rate = _tier_reach_benchmark(followers) if followers else 0.0

    comment_like_ratio  = _pct(avg_comments, avg_likes) if avg_likes else 0.0
    ff_ratio            = round(followers / max(following, 1), 1) if following else 0.0

    # ── 포스팅 주기 ─────────────────────────────────────────────────
    timestamps = sorted([p["ts"] for p in posts_data if p["ts"]], reverse=True)
    avg_interval_days: float | None = None
    if len(timestamps) >= 2:
        gaps = [(timestamps[i] - timestamps[i + 1]).days for i in range(min(len(timestamps) - 1, 19))]
        avg_interval_days = round(sum(gaps) / len(gaps), 1)

    # ── EMV ─────────────────────────────────────────────────────────
    emv = _calc_emv(avg_likes, avg_comments, avg_views)

    # ── 댓글 심층 수집 (옵션) ───────────────────────────────────────
    deep_comment_count = 0
    if deep_comments and post_urls_by_views:
        if progress_callback:
            progress_callback(f"@{username} 댓글 심층 수집 중 (최대 {deep_comments_limit}개)...")
        top_urls = [u for _, u in sorted(post_urls_by_views, reverse=True)[:10]]
        limit_per = max(50, deep_comments_limit // max(len(top_urls), 1))
        deep = _scrape_comments_deep(top_urls, limit_per, client)
        if deep:
            all_comments = deep
            deep_comment_count = len(deep)

    # ── 최종 점수 / 리포트 ──────────────────────────────────────────
    cq             = _analyze_comments(all_comments)
    brand_fit      = _detect_brand_fit(captions, bio)
    commerce_score = _analyze_commerce_signals(bio, captions)
    gugu_activity  = _analyze_gugu_activity(caption_ts)
    content_mix    = _analyze_content_mix(caption_ts)
    view_stability = _analyze_view_stability(video_posts, followers)
    upload_pattern = _analyze_upload_pattern(caption_ts)

    web_signals: dict = {}
    if web_search:
        if progress_callback:
            progress_callback(f"@{username} 웹 검색으로 브랜드 언급 확인 중...")
        web_signals = _web_search_brand_signals(username, client)

    scores = _calc_scores(
        avg_views, view_variance, comment_rate, engage_rate, ad_ratio, cq,
        ghost_estimate, trend, ad_er_penalty, followers, following,
        commerce_score=commerce_score,
        web_brand_signals=web_signals.get("web_brand_signals", 0),
    )
    report = _generate_report(
        avg_views, ad_ratio, scores, brand_fit, view_variance, cq,
        trend, ghost_estimate, ad_er_penalty, emv["emv_krw"],
    )

    return {
        # 기본
        "계정명":           username,
        "분석 게시물 수":   total_posts,
        "릴스/영상 수":     len(reels_views),
        "평균 조회수":      avg_views,
        "최고 조회수":      max_views,
        "조회수 편차":      view_variance,
        "10만+ 릴스":      sum(1 for v in reels_views if v >= 100_000),
        "50만+ 릴스":      sum(1 for v in reels_views if v >= 500_000),
        "100만+ 릴스":     sum(1 for v in reels_views if v >= 1_000_000),
        "평균 좋아요":      avg_likes,
        "평균 댓글":        avg_comments,
        # 분석 지표
        "댓글률(%)":        comment_rate,
        "참여율(%)":        engage_rate,
        "광고 비율(%)":     ad_ratio,
        # 추세
        "참여 추세":        trend,
        # 팔로워 퀄리티
        "기대 참여율(%)":   expected_er,
        "실제 참여율(%)":   actual_er_base,
        "유령 팔로워 추정(%)": ghost_estimate,
        "릴스 도달률(%)":   reels_reach_rate,
        "기대 도달률(%)":   expected_reach_rate,
        "댓글/좋아요 비율(%)": comment_like_ratio,
        "팔로워/팔로잉":    ff_ratio,
        # 광고 vs 일반
        "광고 콘텐츠 ER(%)":  ad_er,
        "일반 콘텐츠 ER(%)":  organic_er,
        "광고 반응 저하(%)":  ad_er_penalty,
        # 포스팅 주기
        "평균 포스팅 주기(일)": avg_interval_days,
        # EMV
        "게시물당 EMV(원)": emv["emv_krw"],
        # 댓글 품질
        "구매의도 댓글(%)": cq["purchase_intent_pct"],
        "저품질 댓글(%)":   cq["low_quality_pct"],
        "분석 댓글 수":     cq["total"],
        "심층댓글_수집수":  deep_comment_count,
        # 점수
        "시딩 점수":        scores["seeding"],
        "공구 적합도":      scores["gugu"],
        "구매전환 점수":    scores["purchase"],
        "팬덤 점수":        scores["fandom"],
        # 상업 활동
        "상업활동 지수":    commerce_score,
        "웹 브랜드 언급":   web_signals.get("web_brand_signals", 0),
        # 공구 활동
        "공구_여부":        gugu_activity["공구_여부"],
        "공구_요약":        gugu_activity["공구_요약"],
        "공구_게시물수":    gugu_activity["공구_게시물수"],
        "공구_빈도(%)":     gugu_activity["공구_빈도"],
        "현재_공구_활성":   gugu_activity["현재_공구_활성"],
        "최근_공구":        gugu_activity["최근_공구"],
        # 콘텐츠 믹스
        "콘텐츠_타입":          content_mix["콘텐츠_타입"],
        "주요_콘텐츠_타입":     content_mix["주요_콘텐츠_타입"],
        "저장유도형_비율":       content_mix["저장유도형_비율"],
        # 조회수 안정성
        "조회수_안정성":         view_stability["조회수_안정성"],
        "안정형_비율":           view_stability["안정형_비율"],
        "최소_조회수":           view_stability["최소_조회수"],
        "팔로워_조회수_효율":    view_stability["팔로워_조회수_효율"],
        # 업로드 패턴
        "주간_업로드수":         upload_pattern["주간_업로드수"],
        "마지막_업로드_경과일":  upload_pattern["마지막_업로드_경과일"],
        "활성_상태":             upload_pattern["활성_상태"],
        # 위험
        "위험도":           scores["risk_level"],
        "위험 신호":        scores["risk_signals"],
        # 추천
        "추천 카테고리":    brand_fit,
        "AI 리포트":        report,
    }, None


def analyze_accounts(
    usernames: list[str],
    posts_limit: int = 50,
    progress_callback=None,
    profile_map: dict[str, dict] | None = None,
    apify_token: str | None = None,
    web_search: bool = False,
    deep_comments: bool = False,
) -> tuple[list[dict], list[str]]:
    results, errors = [], []
    for i, username in enumerate(usernames):
        if progress_callback:
            progress_callback(i, len(usernames), username)
        profile  = (profile_map or {}).get(username, {})
        data, err = analyze_account(
            username, posts_limit,
            bio=profile.get("bio", ""),
            followers=profile.get("followers", 0),
            following=profile.get("following", 0),
            apify_token=apify_token,
            web_search=web_search,
            deep_comments=deep_comments,
        )
        if err:
            errors.append(f"@{username}: {err}")
        else:
            results.append(data)
    return results, errors
