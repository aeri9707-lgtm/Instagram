"""캠페인 북마크: JSON 파일 기반 저장/불러오기/삭제"""
import json
from datetime import datetime
from pathlib import Path

CAMPAIGNS_FILE = Path("campaigns.json")


def _load_all() -> dict:
    if not CAMPAIGNS_FILE.exists():
        return {}
    try:
        return json.loads(CAMPAIGNS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_all(data: dict) -> None:
    CAMPAIGNS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def save_campaign(name: str, profiles: list[dict], label: str = "") -> None:
    """현재 검색 결과를 캠페인으로 저장 (같은 이름이면 덮어쓰기)"""
    data = _load_all()
    data[name] = {
        "label": label or name,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "count": len(profiles),
        "profiles": profiles,
    }
    _save_all(data)


def list_campaigns() -> list[dict]:
    """저장된 캠페인 목록 반환 [{name, label, saved_at, count}, ...]"""
    data = _load_all()
    return [
        {
            "name": k,
            "label": v.get("label", k),
            "saved_at": v.get("saved_at", ""),
            "count": v.get("count", 0),
        }
        for k, v in data.items()
    ]


def load_campaign(name: str) -> list[dict]:
    """캠페인 프로필 목록 반환"""
    data = _load_all()
    return data.get(name, {}).get("profiles", [])


def delete_campaign(name: str) -> None:
    data = _load_all()
    data.pop(name, None)
    _save_all(data)


def campaign_exists(name: str) -> bool:
    return name in _load_all()
