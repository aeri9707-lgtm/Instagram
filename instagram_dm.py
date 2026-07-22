import time
import random
from pathlib import Path
from typing import Any

try:
    from instagrapi import Client
    from instagrapi.exceptions import BadPassword, TwoFactorRequired, ChallengeRequired
    _INSTAGRAPI_AVAILABLE = True
except ImportError:
    Client = None  # type: ignore[assignment]
    _INSTAGRAPI_AVAILABLE = False

    class BadPassword(Exception):
        pass

    class TwoFactorRequired(Exception):
        pass

    class ChallengeRequired(Exception):
        pass

_client: Any = None
SESSION_FILE = Path(".ig_session.json")


def login(username: str, password: str) -> tuple[bool, str]:
    global _client
    if not _INSTAGRAPI_AVAILABLE or Client is None:
        return False, "공개 테스트에서는 Instagram 로그인이 비활성화되어 있어요."
    try:
        cl = Client()
        cl.delay_range = [2, 5]
        cl.login(username, password)
        _client = cl
        _save_session()
        return True, "✅ 로그인 성공"
    except BadPassword:
        return False, "비밀번호가 틀렸어요."
    except TwoFactorRequired:
        return False, "2단계 인증 계정이에요. 인스타그램 앱에서 인증 후 다시 시도해주세요."
    except ChallengeRequired:
        return False, "Instagram 보안 확인이 필요해요. 인스타그램 앱에서 로그인 확인 후 다시 시도해주세요."
    except Exception as e:
        return False, f"로그인 실패: {str(e)[:100]}"


def load_session() -> tuple[bool, str]:
    """저장된 세션 복원. 반환: (성공 여부, username)"""
    global _client
    if not _INSTAGRAPI_AVAILABLE or Client is None:
        return False, ""
    if not SESSION_FILE.exists():
        return False, ""
    try:
        cl = Client()
        cl.delay_range = [2, 5]
        cl.load_settings(SESSION_FILE)
        user_info = cl.account_info()
        _client = cl
        return True, user_info.username
    except Exception:
        SESSION_FILE.unlink(missing_ok=True)
        return False, ""


def logout() -> None:
    global _client
    _client = None
    SESSION_FILE.unlink(missing_ok=True)


def _save_session() -> None:
    if _client:
        try:
            _client.dump_settings(SESSION_FILE)
        except Exception:
            pass


def is_logged_in() -> bool:
    return _client is not None


def get_follower_counts(usernames: list[str]) -> dict[str, int]:
    """팔로워 0인 계정을 instagrapi로 보완"""
    if not _client:
        return {}
    results = {}
    for username in usernames:
        try:
            user = _client.user_info_by_username(username)
            if user.follower_count:
                results[username] = user.follower_count
            time.sleep(0.8)
        except Exception:
            pass
    return results


def check_follow_status(usernames: list[str]) -> dict[str, str]:
    """
    반환: {username: "맞팔" | "팔로워" | "팔로잉" | "없음" | "확인불가"}
    팔로워  = 상대가 나를 팔로우
    팔로잉  = 내가 상대를 팔로우
    맞팔   = 서로 팔로우
    없음   = 아무 관계 없음
    """
    if not _client:
        return {}

    user_ids: dict[str, str] = {}
    results: dict[str, str] = {}

    for username in usernames:
        try:
            uid = _client.user_id_from_username(username)
            user_ids[username] = uid
            time.sleep(0.5)
        except Exception:
            results[username] = "확인불가"

    for uname, uid in user_ids.items():
        try:
            fs = _client.user_friendship_v1(uid)
            if fs.following and fs.followed_by:
                results[uname] = "🤝 맞팔"
            elif fs.followed_by:
                results[uname] = "👤 팔로워"
            elif fs.following:
                results[uname] = "➡️ 팔로잉"
            else:
                results[uname] = "➖ 없음"
            time.sleep(0.5)
        except Exception:
            results[uname] = "확인불가"

    return results


def follow_users(
    usernames: list[str],
    progress_callback=None,
) -> list[dict]:
    if not _client:
        return [{"username": u, "status": "❌ 실패", "message": "로그인 필요"} for u in usernames]

    results = []
    for i, username in enumerate(usernames):
        if progress_callback:
            progress_callback(i, len(usernames), username)
        try:
            uid = _client.user_id_from_username(username)
            _client.user_follow(uid)
            results.append({"username": username, "status": "✅ 팔로우 완료", "message": ""})
        except Exception as e:
            results.append({"username": username, "status": "❌ 실패", "message": str(e)[:80]})

        if i < len(usernames) - 1:
            time.sleep(random.uniform(3, 7))

    return results


def get_inbox(limit: int = 20) -> tuple[list[dict], str | None]:
    if not _client:
        return [], "로그인이 필요해요."
    try:
        threads = _client.direct_threads(amount=limit)
        result = []
        for t in threads:
            users = [u.username for u in t.users if u.username]
            last_msg = ""
            last_time = None
            if t.messages:
                m = t.messages[0]
                last_msg = m.text or "[미디어]"
                last_time = m.timestamp
            result.append({
                "thread_id": t.id,
                "상대방": ", ".join(users),
                "마지막 메시지": last_msg,
                "시간": last_time,
                "읽지 않음": not t.read_state,
            })
        return result, None
    except Exception as e:
        return [], f"받은 DM 불러오기 실패: {str(e)[:100]}"


def get_thread(thread_id: str) -> tuple[list[dict], str | None]:
    if not _client:
        return [], "로그인이 필요해요."
    try:
        thread = _client.direct_thread(int(thread_id))
        messages = []
        for m in reversed(thread.messages):
            sender = "나" if str(m.user_id) == str(_client.user_id) else "상대방"
            messages.append({
                "보낸이": sender,
                "내용": m.text or "[미디어]",
                "시간": m.timestamp,
            })
        return messages, None
    except Exception as e:
        return [], f"대화 불러오기 실패: {str(e)[:100]}"


def reply_to_thread(thread_id: str, text: str) -> tuple[bool, str]:
    if not _client:
        return False, "로그인이 필요해요."
    try:
        _client.direct_send(text, thread_ids=[int(thread_id)])
        return True, "✅ 발송 완료"
    except Exception as e:
        return False, f"발송 실패: {str(e)[:100]}"


def send_dms(
    targets: list[dict],
    progress_callback=None,
) -> list[dict]:
    """
    targets: [{"username": str, "dm_text": str}, ...]
    반환: [{"username": str, "status": "성공" | "실패", "message": str}, ...]
    """
    if not _client:
        return [{"username": t["username"], "status": "실패", "message": "로그인 필요"} for t in targets]

    results = []
    for i, target in enumerate(targets):
        username = target["username"]
        text = target["dm_text"]

        if progress_callback:
            progress_callback(i, len(targets), username)

        try:
            user_id = _client.user_id_from_username(username)
            _client.direct_send(text, user_ids=[int(user_id)])
            results.append({"username": username, "status": "✅ 성공", "message": "발송 완료"})
        except Exception as e:
            results.append({"username": username, "status": "❌ 실패", "message": str(e)[:80]})

        if i < len(targets) - 1:
            delay = random.uniform(5, 12)
            time.sleep(delay)

    return results
