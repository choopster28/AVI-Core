from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class FantasyProsClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        api_key_header: str = "x-api-key",
        timeout_seconds: int = 60,
    ) -> None:
        if not api_key:
            raise RuntimeError("FANTASYPROS_API_KEY is not set.")

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

        retry = Retry(
            total=4,
            connect=4,
            read=4,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def get_json(
        self,
        path: str,
        params: dict[str, str | int | float] | None = None,
    ) -> Any:
        if not path:
            raise ValueError("FantasyPros endpoint path cannot be blank.")

        url = path if path.startswith("http") else f"{self.base_url}/{path.lstrip('/')}"
        response = self.session.get(
            url,
            params=params,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()
