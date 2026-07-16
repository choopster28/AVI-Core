from __future__ import annotations

import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class FantasyProsClient:
    """FantasyPros Public API v2 client with rate-limit protection."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        api_key_header: str,
        timeout_seconds: int = 60,
        minimum_request_interval: float = 2.0,
        maximum_attempts: int = 6,
        max_requests_per_run: int = 20,
    ) -> None:
        if not api_key:
            raise RuntimeError(
                "FANTASYPROS_API_KEY is not set."
            )

        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.minimum_request_interval = minimum_request_interval
        self.maximum_attempts = maximum_attempts
        self.max_requests_per_run = max_requests_per_run
        self.requests_used = 0
        self.last_request_time = 0.0

        self.session = requests.Session()

        self.session.headers.update(
            {
                api_key_header: api_key,
                "Accept": "application/json",
                "User-Agent": "AVI-Core/1.0.0",
            }
        )

        # Retry temporary server/network errors here.
        # HTTP 429 is handled explicitly in get().
        retry_strategy = Retry(
            total=4,
            connect=4,
            read=4,
            backoff_factor=1,
            status_forcelist=[
                500,
                502,
                503,
                504,
            ],
            allowed_methods=["GET"],
        )

        self.session.mount(
            "https://",
            HTTPAdapter(
                max_retries=retry_strategy
            ),
        )

    def _wait_before_request(self) -> None:
        elapsed = time.monotonic() - self.last_request_time

        remaining = (
            self.minimum_request_interval - elapsed
        )

        if remaining > 0:
            time.sleep(remaining)

    @staticmethod
    def _retry_after_seconds(
        response: requests.Response,
        attempt: int,
    ) -> float:
        retry_after = response.headers.get(
            "Retry-After",
            "",
        ).strip()

        if retry_after.isdigit():
            return max(float(retry_after), 1.0)

        # Fallback exponential wait:
        # 5, 10, 20, 40, 60 seconds.
        return min(
            5.0 * (2 ** attempt),
            60.0,
        )

    def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = (
            f"{self.base_url}/"
            f"{path.lstrip('/')}"
        )

        for attempt in range(
            self.maximum_attempts
        ):
            self._wait_before_request()

            if self.requests_used >= self.max_requests_per_run:
                raise RuntimeError(
                    "FantasyPros request budget exhausted: "
                    f"{self.requests_used}/"
                    f"{self.max_requests_per_run} requests used."
                )

            self.requests_used += 1

            print(
                "FantasyPros request budget: "
                f"{self.requests_used}/"
                f"{self.max_requests_per_run}"
            )

            response = self.session.get(
                url,
                params=params,
                timeout=self.timeout_seconds,
            )

            self.last_request_time = time.monotonic()

            if response.status_code == 429:
                wait_seconds = (
                    self._retry_after_seconds(
                        response,
                        attempt,
                    )
                )

                if attempt == self.maximum_attempts - 1:
                    response.raise_for_status()

                print(
                    "FantasyPros rate limit reached. "
                    f"Waiting {wait_seconds:.0f} seconds..."
                )

                time.sleep(wait_seconds)
                continue

            response.raise_for_status()
            return response.json()

        raise RuntimeError(
            "FantasyPros request failed after "
            f"{self.maximum_attempts} attempts."
        )

    def players(self) -> Any:
        return self.get(
            "nfl/players",
            {
                "ecr": "included",
                "show": "pos_rank",
                "external_ids": "nfl",
            },
        )

    def projections(
        self,
        season: int,
        position: str,
    ) -> Any:
        return self.get(
            f"nfl/{season}/projections",
            {
                "position": position,
                "week": 0,
            },
        )

    def consensus_rankings(
        self,
        season: int,
        position: str,
        ranking_type: str,
        scoring: str,
        include_idp: bool,
    ) -> Any:
        params: dict[str, Any] = {
            "position": position,
            "type": ranking_type,
            "scoring": scoring,
            "week": 0,
        }

        if include_idp:
            params["include_idp"] = "true"

        return self.get(
            f"nfl/{season}/consensus-rankings",
            params,
        )

    def player_points(
        self,
        season: int,
        position: str,
        scoring: str,
    ) -> Any:
        return self.get(
            f"nfl/{season}/player-points",
            {
                "position": position,
                "scoring": scoring,
                "start": 1,
                "end": 18,
                "min": "false",
            },
        )

    def injuries(
        self,
        season: int,
    ) -> Any:
        return self.get(
            "nfl/injuries",
            {
                "year": season,
                "week": 0,
                "include_probabilities": "true",
            },
        )

    def news(self) -> Any:
        return self.get(
            "nfl/news",
            {
                "limit": 500,
                "order_by": "updated",
            },
        )