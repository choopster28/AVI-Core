from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class SleeperClient:
    BASE_URL = "https://api.sleeper.app/v1"

    def __init__(self, timeout_seconds: int = 45) -> None:
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

        retry_strategy = Retry(
            total=4,
            connect=4,
            read=4,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy
        )

        self.session.mount("https://", adapter)

    def get_json(self, endpoint: str) -> Any:
        url = f"{self.BASE_URL}{endpoint}"

        response = self.session.get(
            url,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()

        return response.json()

    def get_league(
        self,
        league_id: str,
    ) -> dict[str, Any]:
        return self.get_json(
            f"/league/{league_id}"
        )

    def get_users(
        self,
        league_id: str,
    ) -> list[dict[str, Any]]:
        return self.get_json(
            f"/league/{league_id}/users"
        )

    def get_rosters(
        self,
        league_id: str,
    ) -> list[dict[str, Any]]:
        return self.get_json(
            f"/league/{league_id}/rosters"
        )

    def get_traded_picks(
        self,
        league_id: str,
    ) -> list[dict[str, Any]]:
        return self.get_json(
            f"/league/{league_id}/traded_picks"
        )

    def get_drafts(
        self,
        league_id: str,
    ) -> list[dict[str, Any]]:
        return self.get_json(
            f"/league/{league_id}/drafts"
        )

    def get_transactions(
        self,
        league_id: str,
        week: int,
    ) -> list[dict[str, Any]]:
        return self.get_json(
            f"/league/{league_id}/transactions/{week}"
        )

    def get_nfl_players(
        self,
    ) -> dict[str, dict[str, Any]]:
        return self.get_json(
            "/players/nfl"
        )