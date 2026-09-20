"""HTTP client for the quick draft recommendation endpoint."""

import re

import requests

HERO_CODE = re.compile(r"^c\d{4}$")


class Recommender:
    def __init__(self, base_url="http://127.0.0.1:8799", session=None):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()

    def recommend(self, enemy_codes, top=10, timeout=2, season=None):
        codes = list(enemy_codes)
        if any(not isinstance(code, str) or not HERO_CODE.fullmatch(code) for code in codes):
            raise ValueError("enemy_codes must contain c followed by four digits")
        payload = {"enemy_picks": codes, "top": max(0, min(int(top), 100))}
        if season is not None:
            payload["season"] = season
        response = self.session.post(
            f"{self.base_url}/api/draft/quick", json=payload, timeout=timeout
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or not isinstance(data.get("recommendations"), list):
            raise ValueError("invalid recommendation response")
        return data
