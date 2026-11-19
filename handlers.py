"""
handlers.py — Custom handler untuk provider yang butuh logic khusus.

Setiap handler bertanda tangan:
    handler_xxx(phone: str, session: requests.Session) -> requests.Response

check_xxx(response) -> bool  — opsional, override generic success checker.

Registry di bawah memetakan post_type → (handler_fn, check_fn | None).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from urllib.parse import quote

import requests
from requests.sessions import Session

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


# ═══════════════════════════════════════════════════════════════
# 1. INDOSAKU — AES-128-ECB
# ═══════════════════════════════════════════════════════════════

_IS_BASE    = "https://app.indosaku.id"
_IS_PATH    = "/jdn49uXCY9hp/mvNa/f8t_UdUf"
_IS_KEY     = b"b0b53117-94ab-424f-91c4-10a78f42"
_IS_HEADERS = {
    "bZ6LZqlrL6vMGIwhALp": "IND",
    "rGjS96"              : "112",
    "lAsnNVkU0U9C"        : "android",
    "g9Z76E9boK"          : "Google",
    "x6FDnYreNpNWph"      : "",
    "Content-Type"        : "application/json; charset=UTF-8",
    "User-Agent"          : "okhttp/4.12.0",
}


def _is_encrypt(payload: dict) -> str:
    raw    = json.dumps(payload, separators=(",", ":")).encode()
    cipher = AES.new(_IS_KEY, AES.MODE_ECB)
    return base64.b64encode(cipher.encrypt(pad(raw, 16))).decode()


def _is_decrypt(text: str) -> dict:
    blob = text.strip()
    if blob.startswith("{"):
        return json.loads(blob)
    cipher = AES.new(_IS_KEY, AES.MODE_ECB)
    raw    = cipher.decrypt(base64.b64decode(blob.replace('"', "")))
    return json.loads(unpad(raw, 16).decode())


def handler_indosaku(phone: str, session: Session) -> requests.Response:
    h = dict(_IS_HEADERS)
    h["b9uMD"] = os.urandom(8).hex()
    session.headers.update(h)
    payload = {
        "cVWzn1Oq"  : 1,
        "e8dv2iH"   : "INSA4",
        "yidTRs"    : phone.lstrip("0"),
        "mKm0HT8WuK": "1",
        "fnKDg"     : "Google",
    }
    return session.post(_IS_BASE + _IS_PATH, data=_is_encrypt(payload), timeout=30)


def check_indosaku(response: requests.Response) -> bool:
    try:
        body = _is_decrypt(response.text)
        data = body.get("data") or {}
        return body.get("code") == 200 and data.get("tsFzo") == 1
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════
# 2. RUPIAHCEPAT — AES-128-CBC + MD5 signature
# ═══════════════════════════════════════════════════════════════

_RC_BASE    = "https://apiservice.rupiahcepatweb.com"
_RC_PATH    = "/api/v2/request_auth_code"
_RC_KEY     = "889511be9163d0d23997851e61033282"
_RC_IV      = "ec1d0eafaa9bbc096dfe255c86db9905"
_RC_SALT    = "&97dab6b088ad"
_RC_HEADERS = {
    "Accept"            : "application/json, text/plain, */*",
    "Content-Type"      : "application/x-www-form-urlencoded",
    "Origin"            : "https://h5.rupiahcepat.co.id",
    "Referer"           : "https://h5.rupiahcepat.co.id/",
    "User-Agent"        : "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "x-app-version-code": "999",
    "x-platform"        : "h5-whatsapp",
}


def _rc_uuid() -> str:
    stamp = str(int(time.time() * 1000))
    tail  = "".join("0123456789abcdef"[int.from_bytes(os.urandom(1), "big") % 16] for _ in range(12))
    return stamp + tail


def _rc_base_params(uid: str) -> dict:
    now = str(int(time.time() * 1000))
    return {
        "access_token": "", "city": "", "app_free_memory": "",
        "longitude": "0", "total_boot_time_wake": "", "ui_version": "",
        "noise": "", "battery_max": "", "app_avaliable_memory": "",
        "app_version": "9.9.9", "app_version_code": "999", "version_code": "999",
        "platform": "h5", "app_max_memory": "", "brand": "",
        "manufacturer": "", "mem": "", "tz": "", "total_boot_time": "",
        "lat": "0", "latitude": "0", "is_sim": "0", "is_simulator": "0",
        "lon": "0", "is_tt": "0", "time_zone": "", "cpu_num": "",
        "product": "", "device": "", "is_google_service": "0",
        "battery_level": "0.7", "uuid": uid, "request_time": now,
        "uptime": now, "rcid": uid, "net": "other", "model": "",
        "width": "412", "network": "other", "height": "915", "os": "other",
    }


def _rc_encrypt(data: dict, uid: str) -> str:
    merged = _rc_base_params(uid)
    merged.update({k: ("" if v is None else v) for k, v in data.items()})
    signed = sorted(merged)[:20]
    raw    = "&".join(f"{k}={merged[k]}" for k in signed)
    merged["signature"] = hashlib.md5((raw + _RC_SALT).encode()).hexdigest()
    cipher = AES.new(bytes.fromhex(_RC_KEY), AES.MODE_CBC, bytes.fromhex(_RC_IV))
    body   = json.dumps(merged, separators=(",", ":")).encode()
    return quote(base64.b64encode(cipher.encrypt(pad(body, 16))).decode(), safe="")


def handler_rupiahcepat(phone: str, session: Session) -> requests.Response:
    session.headers.update(_RC_HEADERS)
    uid  = _rc_uuid()
    data = {"mobile": phone, "sms_type": "8", "otp_channel": "2"}
    return session.post(_RC_BASE + _RC_PATH, data="data=" + _rc_encrypt(data, uid), timeout=30)


def check_rupiahcepat(response: requests.Response) -> bool:
    try:
        return response.json().get("code") == 0
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════
# 3. CAIRIN — multipart/form-data
# ═══════════════════════════════════════════════════════════════

_CAIRIN_UA   = (
    "Mozilla/5.0 (Linux; Android 9; vivo 1902 Build/PPR1.180610.011; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/74.0.3729.136 Mobile Safari/537.36"
)
_CAIRIN_FILE = "6f8c3b90c845f09ff1bfe714a30aede8"
_CAIRIN_IMEI = "352365091234567"


def handler_cairin(phone: str, session: Session) -> requests.Response:
    session.headers.update({"User-Agent": _CAIRIN_UA})
    return session.post(
        "https://app.cairin.id/v1/app/sms/sendCaptcha",
        data={
            "haveImageCode": "0",
            "fileName"      : _CAIRIN_FILE,
            "phone"         : "0" + phone.lstrip("0"),
            "imageCode"     : "",
            "userImei"      : _CAIRIN_IMEI,
            "verifySend"    : "1",
            "type"          : "registry",
        },
        timeout=30,
    )


def check_cairin(response: requests.Response) -> bool:
    try:
        return response.json().get("code") == "0"
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════
# Registry
# ═══════════════════════════════════════════════════════════════

REGISTRY: dict[str, tuple] = {
    "indosaku"   : (handler_indosaku,    check_indosaku),
    "rupiahcepat": (handler_rupiahcepat, check_rupiahcepat),
    "cairin"     : (handler_cairin,      check_cairin),
}
