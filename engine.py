"""
engine.py — Concurrent dispatcher.
Menjalankan semua provider secara paralel dan melaporkan hasil real-time.
"""
from __future__ import annotations

import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Iterator

import requests
from requests.sessions import Session

from providers import Provider, PROVIDERS
from useragents import get_random_ua
from utils import resolve_payload


# ─────────────────────────────────────────────────────────────
# Rate limit keywords
# ─────────────────────────────────────────────────────────────

_RATE_LIMIT_KEYWORDS = [
    "rate limit", "too many", "try again", "exceeded",
    "banned", "blocked", "terlalu banyak", "coba lagi",
]


# ─────────────────────────────────────────────────────────────
# Result
# ─────────────────────────────────────────────────────────────

@dataclass
class Result:
    name    : str
    ok      : bool
    status  : int  = 0
    detail  : str  = ""
    limited : bool = False


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _is_rate_limited(status: int, text: str) -> bool:
    if status == 429:
        return True
    text_lower = text.lower()
    return any(kw in text_lower for kw in _RATE_LIMIT_KEYWORDS)


def _check_success_on(text: str, success_on: list[str]) -> bool:
    if not success_on:
        return False
    text_lower = text.lower()
    return any(re.search(p.lower(), text_lower) for p in success_on)


# ─────────────────────────────────────────────────────────────
# Dispatch satu provider
# ─────────────────────────────────────────────────────────────

def _send_one(phone: str, provider: Provider,
              stop_flag: threading.Event) -> Result:
    if stop_flag.is_set():
        return Result(name=provider.name, ok=False, detail="Dibatalkan")

    name = provider.name
    try:
        phone_fmt = provider.number_fmt(phone)
        phone_raw = phone.lstrip("0")

        # ── Mode custom (send_fn didefinisikan) ───────────────
        if provider.send_fn is not None:
            s = Session()
            s.headers.update({"User-Agent": get_random_ua()})
            response = provider.send_fn(phone_fmt, s)

            if _is_rate_limited(response.status_code, response.text):
                return Result(name=name, ok=False, status=response.status_code,
                              detail="Rate limited", limited=True)

            if provider.check_fn is not None:
                ok = provider.check_fn(response)
            else:
                ok = (200 <= response.status_code < 300 and
                      _check_success_on(response.text, provider.success_on))

            return Result(name=name, ok=ok, status=response.status_code,
                          detail=response.text[:80])

        # ── Mode JSON generik ─────────────────────────────────
        headers = dict(provider.headers)
        for k, v in headers.items():
            if isinstance(v, str) and "{" in v:
                headers[k] = resolve_payload(v, phone_fmt, phone_raw)

        headers.setdefault("User-Agent", get_random_ua())
        headers.setdefault("Accept", "application/json, text/plain, */*")
        if provider.referer:
            headers.setdefault("Referer", provider.referer)

        raw_payload  = resolve_payload(provider.payload, phone_fmt, phone_raw)
        content_type = headers.get("Content-Type", "application/json")

        s = Session()
        s.headers.update(headers)

        if content_type.startswith("application/json"):
            response = s.post(provider.url, json=json.loads(raw_payload),
                              timeout=provider.timeout)
        else:
            response = s.post(provider.url, data=raw_payload.encode(),
                              timeout=provider.timeout)

        status = response.status_code
        body   = response.text

        if _is_rate_limited(status, body):
            return Result(name=name, ok=False, status=status,
                          detail="Rate limited", limited=True)

        if 200 <= status < 300:
            ok = _check_success_on(body, provider.success_on) if provider.success_on else True
        else:
            ok = False

        return Result(name=name, ok=ok, status=status, detail=body[:80])

    except requests.exceptions.ConnectionError:
        return Result(name=name, ok=False, status=0, detail="Connection error")
    except requests.exceptions.Timeout:
        return Result(name=name, ok=False, status=0, detail="Timeout")
    except Exception as e:
        return Result(name=name, ok=False, status=0, detail=str(e)[:80])


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def send_all(phone: str,
             providers: list[Provider] | None = None,
             max_workers: int = 12,
             stop_flag: threading.Event | None = None) -> Iterator[Result]:
    """
    Kirim OTP ke semua provider secara paralel.
    Yield Result satu per satu sesuai urutan selesai.
    """
    if providers is None:
        providers = PROVIDERS
    if stop_flag is None:
        stop_flag = threading.Event()

    active = [p for p in providers if p.enabled]

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_send_one, phone, p, stop_flag): p
            for p in active
        }
        for future in as_completed(futures):
            if stop_flag.is_set():
                for f in futures:
                    f.cancel()
                break
            try:
                yield future.result()
            except Exception as e:
                name = futures[future].name
                yield Result(name=name, ok=False, detail=str(e)[:80])
