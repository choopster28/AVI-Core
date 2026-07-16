from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class FantasyProsClient:
    """Client for the FantasyPros Public API v2."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        api_key_header: str = "x-api-key",
        timeout_seconds: int = 60,
    ) -> None:
        if not api_key:
            raise RuntimeError(
                "FANTASYPROS_API_KEY is not set."
            )

        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

        self.session.headers.update(
            {
                api_key_header: api_key,
                "Accept": "application/json",
                "User-Agent": "AVI-Core/0.2.0",
            }
        )

        retry_strategy = Retry(
            total=4,
            connect=4,
            read=4,
            backoff_factor=1,
            status_forcelist=[
                429,
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

    def get_json(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = (
            f"{self.base_url}/"
            f"{endpoint.lstrip('/')}"
        )

        response = self.session.get(
            url,
            params=params,
            timeout=self.timeout_seconds,
        )

        response.raise_for_status()
        return response.json()

    def get_players(
        self,
    ) -> dict[str, Any]:
        """
        Download the NFL player directory.

        FantasyPros only accepts one external ID provider per request,
        so AVI requests NFL IDs here.
        """
        return self.get_json(
            "nfl/players",
            params={
                "ecr": "included",
                "show": "pos_rank",
                "external_ids": "nfl",
            },
        )

    def get_projections(
        self,
        season: int,
        position: str,
        week: int = 0,
        ros: bool = False,
    ) -> dict[str, Any]:
        """
        Download projections for one position.

        week=0 requests preseason/full-season projections.
        """
        return self.get_json(
            f"nfl/{season}/projections",
            params={
                "position": position,
                "week": week,
                "ros": str(ros).lower(),
            },
        )

    def get_consensus_rankings(
        self,
        season: int,
        position: str,
        ranking_type: str,
        scoring: str,
        week: int = 0,
        include_idp: bool = False,
    ) -> dict[str, Any]:
        """
        Download consensus rankings for one position.

        Examples of ranking_type:
        - DYNASTY
        - DRAFT
        - PRESEASON
        - ROS
        """
        params: dict[str, Any] = {
            "position": position,
            "type": ranking_type,
            "scoring": scoring,
            "week": week,
        }

        if include_idp:
            params["include_idp"] = "true"

        return self.get_json(
            f"nfl/{season}/consensus-rankings",
            params=params,
        )

    def get_player_points(
        self,
        season: int,
        position: str,
        scoring: str,
        start_week: int = 1,
        end_week: int = 18,
    ) -> dict[str, Any]:
        """
        Download actual NFL fantasy points.

        AVI stores these immediately, but they do not affect C-AVI
        until verified regular-season games have been played.
        """
        return self.get_json(
            f"nfl/{season}/player-points",
            params={
                "position": position,
                "scoring": scoring,
                "start": start_week,
                "end": end_week,
                "min": "false",
            },
        )

    def get_injuries(
        self,
        season: int,
        week: int = 0,
    ) -> dict[str, Any]:
        return self.get_json(
            "nfl/injuries",
            params={
                "year": season,
                "week": week,
                "include_probabilities": "true",
            },
        )

    def get_news(
        self,
        limit: int = 500,
    ) -> dict[str, Any]:
        return self.get_json(
            "nfl/news",
            params={
                "limit": limit,
                "order_by": "updated",
            },
        )