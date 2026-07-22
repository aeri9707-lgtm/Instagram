"""자연어 → 검색 파라미터 파서 (외부 API 불필요)"""
import re

# 카테고리 키워드 → 검색 키워드 매핑
_CATEGORY_MAP: list[tuple[list[str], str]] = [
    (["뷰티", "화장", "스킨케어", "메이크업", "beauty", "코스메틱"], "뷰티"),
    (["패션", "코디", "ootd", "옷", "스타일", "fashion"], "패션"),
    (["육아", "아기", "아이", "엄마", "맘", "baby", "mom"], "육아"),
    (["다이어트", "헬스", "운동", "피트니스", "gym", "fitness", "workout"], "헬스"),
    (["요리", "음식", "맛집", "먹방", "레시피", "food", "cooking"], "요리"),
    (["여행", "travel", "트립", "trip"], "여행"),
    (["인테리어", "홈", "home", "interior", "집꾸미기"], "인테리어"),
    (["게임", "gaming", "스트리머"], "게임"),
    (["반려동물", "강아지", "고양이", "펫", "pet", "dog", "cat"], "반려동물"),
    (["자동차", "카", "car", "드라이브"], "자동차"),
    (["경제", "재테크", "주식", "투자", "finance"], "재테크"),
    (["교육", "공부", "학습", "study", "education"], "교육"),
    (["음악", "music", "뮤지션", "가수"], "음악"),
    (["사진", "photo", "포토그래피", "photography"], "사진"),
]

# 팔로워 티어 키워드 → (min, max)
_TIER_MAP: list[tuple[list[str], tuple[int, int]]] = [
    (["나노", "nano"], (1_000, 9_999)),
    (["마이크로", "micro"], (10_000, 99_999)),
    (["미드티어", "mid", "중간"], (100_000, 499_999)),
    (["매크로", "macro"], (500_000, 999_999)),
    (["메가", "mega", "탑", "top"], (1_000_000, 999_999_999)),
]

# 팔로워 직접 수치 패턴: "10만 이상", "5만~20만", "1만명"
_NUM_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*([만천억])?\s*(?:명|팔로워|followers?)?\s*"
    r"(?:(이상|이하|~|-)\s*(\d+(?:\.\d+)?)\s*([만천억])?)?"
)


def _to_int(num_str: str, unit: str | None) -> int:
    n = float(num_str)
    u = (unit or "").strip()
    if u == "억":
        return int(n * 100_000_000)
    if u == "만":
        return int(n * 10_000)
    if u == "천":
        return int(n * 1_000)
    return int(n)


def _detect_follower_range(text: str) -> tuple[int, int] | None:
    """자연어에서 팔로워 범위 추출. 반환: (min, max) or None"""
    # 티어명 우선
    for keywords, tier_range in _TIER_MAP:
        if any(kw in text for kw in keywords):
            return tier_range

    # 숫자 직접 기재
    m = _NUM_PATTERN.search(text)
    if m:
        lo_n, lo_u, op, hi_n, hi_u = m.groups()
        if lo_n:
            lo = _to_int(lo_n, lo_u)
            if op in ("~", "-") and hi_n:
                # "1~5만"처럼 단위가 한쪽에만 있으면 양쪽에 같은 단위를 적용.
                shared_lo_unit = lo_u or hi_u
                shared_hi_unit = hi_u or lo_u
                lo = _to_int(lo_n, shared_lo_unit)
                hi = _to_int(hi_n, shared_hi_unit)
                return (lo, hi)
            elif op == "이상":
                return (lo, 999_999_999)
            elif op == "이하":
                return (0, lo)
            else:
                return (max(0, lo - lo // 2), lo * 2)
    return None


def _detect_region(text: str) -> str:
    if any(w in text for w in ["한국", "국내", "korea", "코리아", "한국인"]):
        return "한국"
    if any(w in text for w in ["해외", "글로벌", "global", "영어권", "overseas"]):
        return "해외"
    return "전체"


def parse_nl_query(text: str) -> dict:
    """
    반환:
      keyword       str   — Apify 검색 키워드
      follower_min  int
      follower_max  int
      region        str   — "전체" | "한국" | "해외"
      detected_tags list[str]  — 파싱된 태그 (UI 표시용)
    """
    t = text.lower()
    tags: list[str] = []

    # 입력을 공백 기준으로 토큰화 (한글/영문 단어 단위)
    _tokens = set(re.findall(r"[가-힣a-zA-Z]+", t))

    # 카테고리 — 문장에 먼저 등장한 긍정 카테고리를 선택한다.
    # "육아 제외"처럼 뒤에 부정 표현이 붙은 카테고리는 검색 주제로 사용하지 않는다.
    category_matches: list[tuple[int, str]] = []
    negators = ("제외", "빼고", "빼줘", "말고", "아닌", "없이")
    for kws, label in _CATEGORY_MAP:
        for kw in kws:
            pattern = rf"(?<![가-힣a-zA-Z]){re.escape(kw)}(?![가-힣a-zA-Z])"
            for match in re.finditer(pattern, t):
                following = t[match.end():match.end() + 18]
                if any(negator in following for negator in negators):
                    continue
                category_matches.append((match.start(), label))
    keyword = min(category_matches, default=(0, ""), key=lambda item: item[0])[1]
    if keyword:
        tags.append(f"카테고리: {keyword}")

    # 팔로워 범위
    f_range = _detect_follower_range(t)
    if f_range:
        lo, hi = f_range
        lo_str = f"{lo // 10_000}만" if lo >= 10_000 else str(lo)
        hi_str = f"{hi // 10_000}만" if hi < 999_999_999 else "∞"
        tags.append(f"팔로워: {lo_str}~{hi_str}")
    else:
        lo, hi = 0, 999_999_999

    # 지역
    region = _detect_region(t)
    if region != "전체":
        tags.append(f"지역: {region}")

    # 나이대 (태그 표시용만 — 검색 키워드에 합산)
    for age in ["10대", "20대", "30대", "40대", "50대"]:
        if age in t:
            tags.append(f"연령대: {age}")
            break

    # 성별 힌트
    gender = "전체"
    if any(w in t for w in ["여성", "여자", "girl", "female", "woman"]):
        gender = "여성"
        tags.append("성별: 여성")
    elif any(w in t for w in ["남성", "남자", "boy", "male", "man"]):
        gender = "남성"
        tags.append("성별: 남성")

    if not keyword:
        # 카테고리 미감지 → 원문에서 의미 있는 명사를 최대 2개 조합해 키워드로 사용
        stopwords = {"찾아", "줘", "검색", "인플루언서", "블로거", "유튜버",
                     "계정", "추천", "해줘", "알려", "보여", "나노", "마이크로",
                     "마이크", "매크로", "메가", "이상", "이하", "팔로워", "명",
                     "한국", "국내", "해외", "글로벌"}
        tokens = [t for t in re.findall(r"[가-힣a-zA-Z]{2,}", text) if t not in stopwords]
        # 첫 두 단어를 공백으로 합쳐 검색 (예: "강아지 간식", "건강식품 비건")
        keyword = " ".join(tokens[:2]) if tokens else "인플루언서"

    return {
        "keyword": keyword,
        "follower_min": lo,
        "follower_max": hi,
        "region": region,
        "gender": gender,
        "detected_tags": tags,
    }
