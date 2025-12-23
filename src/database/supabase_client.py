from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional
from urllib.parse import urlencode

import requests


class SupabaseError(RuntimeError):
    pass


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


@dataclass(frozen=True)
class SupabaseConfig:
    url: str
    service_role_key: str

    @staticmethod
    def from_env() -> "SupabaseConfig":
        url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
        key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
        if not url:
            raise SupabaseError("SUPABASE_URL is required")
        if not key:
            raise SupabaseError("SUPABASE_SERVICE_ROLE_KEY is required")
        return SupabaseConfig(url=url, service_role_key=key)


class SupabaseClient:
    """
    Minimal Supabase REST (PostgREST) wrapper for the hrb server.
    """

    def __init__(
        self,
        cfg: SupabaseConfig,
        *,
        session: Optional[requests.Session] = None,
        max_retries: int = 6,
        sleep_fn: Callable[[float], None] = _sleep,
    ) -> None:
        self._cfg = cfg
        self._session = session or requests.Session()
        self._max_retries = max_retries
        self._sleep = sleep_fn

    def _headers(self, *, prefer: Optional[str] = None, content_type_json: bool = False) -> dict[str, str]:
        h = {
            "apikey": self._cfg.service_role_key,
            "Authorization": f"Bearer {self._cfg.service_role_key}",
        }
        if prefer:
            h["Prefer"] = prefer
        if content_type_json:
            h["Content-Type"] = "application/json"
        return h

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        json_body: Any = None,
        range_from: Optional[int] = None,
        range_to: Optional[int] = None,
        timeout_seconds: int = 30,
    ) -> requests.Response:
        url = f"{self._cfg.url}{path}"
        if params:
            url = f"{url}?{urlencode({k: v for k, v in params.items() if v is not None}, doseq=True)}"

        merged_headers = dict(headers or {})
        if range_from is not None and range_to is not None:
            merged_headers["Range-Unit"] = "items"
            merged_headers["Range"] = f"{range_from}-{range_to}"

        body = None
        if json_body is not None:
            body = json.dumps(json_body, default=str)

        last_err: Optional[Exception] = None
        backoff = 0.6
        for attempt in range(self._max_retries + 1):
            try:
                resp = self._session.request(
                    method=method,
                    url=url,
                    headers=merged_headers,
                    data=body,
                    timeout=timeout_seconds,
                )
            except Exception as e:
                last_err = e
                if attempt >= self._max_retries:
                    raise SupabaseError(f"Supabase request failed: {method} {url} err={e}") from e
                self._sleep(backoff)
                backoff = min(backoff * 1.8, 10.0)
                continue

            if resp.status_code in (429, 500, 502, 503, 504):
                if attempt >= self._max_retries:
                    return resp
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

            return resp

        raise SupabaseError(f"Supabase request failed after retries: {method} {url} err={last_err}")

    def upsert(
        self,
        table: str,
        rows: list[dict[str, Any]],
        *,
        on_conflict: Optional[str] = None,
    ) -> int:
        if not rows:
            return 0
        params: dict[str, Any] = {}
        if on_conflict:
            params["on_conflict"] = on_conflict
        resp = self._request(
            "POST",
            f"/rest/v1/{table}",
            params=params,
            headers=self._headers(prefer="resolution=merge-duplicates,return=minimal", content_type_json=True),
            json_body=rows,
        )
        if not (200 <= resp.status_code < 300):
            raise SupabaseError(f"Upsert failed table={table} status={resp.status_code} body={resp.text[:500]}")
        return len(rows)

    def select(
        self,
        table: str,
        *,
        select: str = "*",
        filters: Optional[dict[str, Any]] = None,
        order: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"select": select}
        if filters:
            params.update(filters)
        if order:
            params["order"] = order

        range_from = None
        range_to = None
        if limit is not None:
            if limit <= 0:
                return []
            range_from = offset
            range_to = offset + limit - 1

        resp = self._request(
            "GET",
            f"/rest/v1/{table}",
            params=params,
            headers=self._headers(),
            range_from=range_from,
            range_to=range_to,
        )
        if not (200 <= resp.status_code < 300):
            raise SupabaseError(f"Select failed table={table} status={resp.status_code} body={resp.text[:500]}")
        data = resp.json()
        if not isinstance(data, list):
            raise SupabaseError(f"Unexpected select response type table={table} type={type(data)}")
        return data

    def count(self, table: str, *, filters: Optional[dict[str, Any]] = None) -> int:
        params: dict[str, Any] = {"select": "id"}
        if filters:
            params.update(filters)
        resp = self._request(
            "HEAD",
            f"/rest/v1/{table}",
            params=params,
            headers=self._headers(prefer="count=exact"),
        )
        if not (200 <= resp.status_code < 300):
            raise SupabaseError(f"Count failed table={table} status={resp.status_code} body={resp.text[:500]}")
        cr = resp.headers.get("Content-Range") or ""
        if "/" in cr:
            total = cr.split("/", 1)[1].strip()
            return int(total)
        raise SupabaseError(f"Could not parse Content-Range for count table={table} content_range={cr!r}")


