import unittest
from unittest.mock import patch

import apify_helper
from apify_helper import _detect_region_details, _normalize_profile, _quality_score
from ui_components import profile_card


class _FakeDataset:
    def __init__(self, items):
        self.items = items

    def iterate_items(self):
        return iter(self.items)


class _FakeRun:
    def __init__(self, run_id):
        self.run_id = run_id

    def wait_for_finish(self, **_kwargs):
        return {"id": self.run_id, "status": "SUCCEEDED", "defaultDatasetId": self.run_id}

    def get(self):
        return self.wait_for_finish()


class _FakeActor:
    def __init__(self, client, actor_id):
        self.client = client
        self.actor_id = actor_id

    def start(self, run_input):
        run_id = f"run-{len(self.client.started)}"
        self.client.started.append((self.actor_id, run_input))
        start = 0 if len(self.client.started) == 1 else 18
        self.client.datasets[run_id] = [
            {"username": f"mom_{i}", "followersCount": 10_000 + i}
            for i in range(start, start + 18)
        ]
        return {"id": run_id}

    def call(self, run_input, **_kwargs):
        run_id = "profiles"
        self.client.profile_usernames = list(run_input["usernames"])
        self.client.datasets[run_id] = [
            {
                "username": username,
                "fullName": f"육아맘 {username}",
                "biography": "신생아 육아와 아기용품 리뷰",
                "followersCount": 20_000,
                "postsCount": 100,
                "countryCode": "KR",
            }
            for username in run_input["usernames"]
        ]
        return {"id": run_id, "status": "SUCCEEDED", "defaultDatasetId": run_id}


class _FakeClient:
    def __init__(self):
        self.started = []
        self.datasets = {}
        self.profile_usernames = []

    def actor(self, actor_id):
        return _FakeActor(self, actor_id)

    def run(self, run_id):
        return _FakeRun(run_id)

    def dataset(self, dataset_id):
        return _FakeDataset(self.datasets[dataset_id])


class SearchQualityTests(unittest.TestCase):
    def test_korean_region_evidence_has_confidence(self):
        self.assertEqual(
            _detect_region_details("서울 육아 콘텐츠", "김하늘", "sky_mom", ""),
            ("한국", 90, "한국 도시 서울"),
        )
        self.assertEqual(
            _detect_region_details("Beauty creator", "Jane", "jane", "US")[:2],
            ("해외", 100),
        )

    def test_relevant_public_profile_outranks_irrelevant_profile(self):
        relevant = _normalize_profile({
            "username": "seoul_mom",
            "fullName": "서울 육아맘",
            "biography": "신생아 육아와 아기용품 리뷰, 협업 문의 hello@example.com",
            "followersCount": 32_000,
            "postsCount": 240,
            "countryCode": "KR",
            "businessEmail": "hello@example.com",
        })
        irrelevant = _normalize_profile({
            "username": "daily_store",
            "fullName": "온라인 스토어",
            "biography": "패션 상품 판매",
            "followersCount": 250_000,
            "postsCount": 400,
            "countryCode": "KR",
        })
        relevant_score, reasons = _quality_score(
            relevant, "신생아 육아 감성 엄마", "한국", 10_000, 100_000, source_hits=2,
        )
        irrelevant_score, _ = _quality_score(
            irrelevant, "신생아 육아 감성 엄마", "한국", 10_000, 100_000, source_hits=1,
        )
        self.assertGreater(relevant_score, irrelevant_score)
        self.assertTrue(any("검색어 일치" in reason for reason in reasons))

    def test_private_account_is_penalized(self):
        public = _normalize_profile({
            "username": "beauty_creator",
            "fullName": "뷰티 크리에이터",
            "biography": "스킨케어 메이크업 리뷰",
            "followersCount": 20_000,
            "postsCount": 100,
            "countryCode": "KR",
        })
        private = dict(public, is_private=True)
        public_score, _ = _quality_score(public, "뷰티 스킨케어", "한국")
        private_score, _ = _quality_score(private, "뷰티 스킨케어", "한국")
        self.assertEqual(public_score - private_score, 20)

    def test_follower_fit_is_not_a_popularity_bonus(self):
        in_range = _normalize_profile({
            "username": "creator_a", "fullName": "육아맘", "biography": "육아 아기",
            "followersCount": 50_000, "postsCount": 100, "countryCode": "KR",
        })
        too_large = dict(in_range, username="creator_b", followers=500_000)
        in_score, _ = _quality_score(in_range, "육아", "한국", 10_000, 100_000)
        out_score, _ = _quality_score(too_large, "육아", "한국", 10_000, 100_000)
        self.assertEqual(in_score - out_score, 15)

    def test_fast_path_returns_exact_requested_count_without_fallback(self):
        client = _FakeClient()
        with patch.object(apify_helper, "_get_client", return_value=client):
            results, error = apify_helper.search_by_keyword(
                "육아", max_results=20, apify_token="test", region="한국",
                quality_query="신생아 육아 엄마",
            )
        self.assertIsNone(error)
        self.assertEqual(len(results), 20)
        self.assertEqual(len(client.started), 2)
        self.assertLessEqual(len(client.profile_usernames), 36)
        self.assertTrue(all(p["region"] == "한국" for p in results))
        self.assertTrue(all("recommendation_score" in p for p in results))

    def test_profile_card_shows_score_and_formats_followers_once(self):
        card = profile_card({
            "username": "mom_creator", "full_name": "육아맘", "followers": 32_000,
            "recommendation_score": 87,
            "recommendation_reasons": ["검색어 일치: 육아", "국가 코드 KR"],
        })
        self.assertIn("3.2만", card)
        self.assertNotIn("만만", card)
        self.assertIn("추천 87점", card)


if __name__ == "__main__":
    unittest.main()
