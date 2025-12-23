from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Optional

import requests


class BallDontLieError(RuntimeError):
    pass


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


@dataclass
class RateLimiter:
    """
    Simple client-side limiter.

    BALLDONTLIE ALL-STAR is 60 req/min. We default slightly under that.
    """

    min_interval_seconds: float
    _sleep: Callable[[float], None] = _sleep
    _last_ts: float = 0.0

    def wait(self) -> None:
        now = time.time()
        if self._last_ts <= 0:
            self._last_ts = now
            return
        elapsed = now - self._last_ts
        remaining = self.min_interval_seconds - elapsed
        if remaining > 0:
            self._sleep(remaining)
        self._last_ts = time.time()


class BallDontLieNFLClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.balldontlie.io/nfl/v1",
        session: Optional[requests.Session] = None,
        timeout_seconds: int = 30,
        max_retries: int = 6,
        per_page: int = 100,
        rate_limiter: Optional[RateLimiter] = None,
        sleep_fn: Callable[[float], None] = _sleep,
    ) -> None:
        self._api_key = api_key.strip()
        if not self._api_key:
            raise BallDontLieError("BALLDONTLIE api_key is required")
        self._base_url = base_url.rstrip("/")
        self._session = session or requests.Session()
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._per_page = per_page
        self._sleep = sleep_fn
        self._rl = rate_limiter or RateLimiter(min_interval_seconds=60.0 / 55.0, _sleep=sleep_fn)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": self._api_key}

    def _request(self, method: str, path: str, *, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        last_err: Optional[Exception] = None
        last_retry_status: Optional[int] = None
        last_retry_body: Optional[str] = None
        backoff = 0.6
        for attempt in range(self._max_retries + 1):
            self._rl.wait()
            try:
                resp = self._session.request(
                    method=method,
                    url=url,
                    headers=self._headers(),
                    params=params,
                    timeout=self._timeout,
                )
            except Exception as e:
                last_err = e
                if attempt >= self._max_retries:
                    raise BallDontLieError(f"Request failed: {method} {url} err={e}") from e
                self._sleep(backoff)
                backoff = min(backoff * 1.8, 10.0)
                continue

            if resp.status_code in (429, 500, 502, 503, 504):
                last_retry_status = resp.status_code
                try:
                    last_retry_body = resp.text
                except Exception:
                    last_retry_body = None
                if attempt >= self._max_retries:
                    raise BallDontLieError(
                        f"HTTP {resp.status_code} after retries for {method} {url}: {(resp.text or '')[:500]}"
                    )
                retry_after = resp.headers.get("Retry-After")
                if retry_after:
                    try:
                        self._sleep(float(retry_after))
                    except Exception:
                        self._sleep(backoff)
                else:
                    self._sleep(backoff)
                backoff = min(backoff * 1.8, 10.0)
                continue

            if not resp.ok:
                raise BallDontLieError(f"HTTP {resp.status_code} for {method} {url}: {resp.text[:500]}")

            try:
                payload = resp.json()
            except Exception as e:
                raise BallDontLieError(f"JSON decode failed for {method} {url}: {e}") from e

            if not isinstance(payload, dict):
                raise BallDontLieError(f"Unexpected response type for {method} {url}: {type(payload)}")
            return payload

        if last_err is not None:
            raise BallDontLieError(f"Request failed after retries: {method} {url} err={last_err}")
        if last_retry_status is not None:
            raise BallDontLieError(
                f"HTTP {last_retry_status} after retries for {method} {url}: {(last_retry_body or '')[:500]}"
            )
        raise BallDontLieError(f"Request failed after retries: {method} {url}")

    def paginate(self, path: str, *, params: Optional[dict[str, Any]] = None) -> Iterator[dict[str, Any]]:
        cursor: Optional[int] = None
        while True:
            p = dict(params or {})
            p.setdefault("per_page", self._per_page)
            if cursor is not None:
                p["cursor"] = cursor
            payload = self._request("GET", path, params=p)
            data = payload.get("data")
            if not isinstance(data, list):
                raise BallDontLieError(f"Expected list 'data' for {path}, got {type(data)}")
            for row in data:
                if isinstance(row, dict):
                    yield row

            meta = payload.get("meta") or {}
            next_cursor = meta.get("next_cursor") if isinstance(meta, dict) else None
            if next_cursor in (None, "", 0):
                break
            try:
                cursor = int(next_cursor)
            except Exception:
                raise BallDontLieError(f"Invalid next_cursor for {path}: {next_cursor!r}")

    def list_teams(self) -> list[dict[str, Any]]:
        payload = self._request("GET", "/teams")
        data = payload.get("data")
        if not isinstance(data, list):
            raise BallDontLieError(f"Expected list teams data, got {type(data)}")
        return [r for r in data if isinstance(r, dict)]

    def iter_players(self, *, search: Optional[str] = None, team_ids: Optional[list[int]] = None) -> Iterator[dict[str, Any]]:
        params: dict[str, Any] = {}
        if search:
            params["search"] = search
        if team_ids:
            params["team_ids[]"] = team_ids
        yield from self.paginate("/players", params=params)

    def iter_games(self, *, seasons: list[int], weeks: Optional[list[int]] = None) -> Iterator[dict[str, Any]]:
        params: dict[str, Any] = {"seasons[]": [int(s) for s in seasons]}
        if weeks:
            params["weeks[]"] = [int(w) for w in weeks]
        yield from self.paginate("/games", params=params)

    def iter_player_game_stats(self, *, seasons: list[int]) -> Iterator[dict[str, Any]]:
        # Endpoint: /stats supports seasons[] filter and cursor pagination
        params: dict[str, Any] = {"seasons[]": [int(s) for s in seasons]}
        yield from self.paginate("/stats", params=params)

    def iter_player_season_stats(self, *, season: int, postseason: bool = False) -> Iterator[dict[str, Any]]:
        # API expects lowercase booleans, not Python's True/False stringification.
        params: dict[str, Any] = {"season": int(season), "postseason": "true" if postseason else "false"}
        yield from self.paginate("/season_stats", params=params)

    def iter_advanced_receiving(self, *, season: int, week: int = 0, postseason: bool = False) -> Iterator[dict[str, Any]]:
        # This endpoint expects postseason as 0/1 (not true/false).
        params: dict[str, Any] = {"season": int(season), "week": int(week), "postseason": "1" if postseason else "0"}
        yield from self.paginate("/advanced_stats/receiving", params=params)

    def iter_advanced_rushing(self, *, season: int, week: int = 0, postseason: bool = False) -> Iterator[dict[str, Any]]:
        params: dict[str, Any] = {"season": int(season), "week": int(week), "postseason": "1" if postseason else "0"}
        yield from self.paginate("/advanced_stats/rushing", params=params)

    def iter_advanced_passing(self, *, season: int, week: int = 0, postseason: bool = False) -> Iterator[dict[str, Any]]:
        params: dict[str, Any] = {"season": int(season), "week": int(week), "postseason": "1" if postseason else "0"}
        yield from self.paginate("/advanced_stats/passing", params=params)


