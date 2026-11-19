"""
providers.py — Registri tunggal semua provider OTP.

Cara menambah provider baru
───────────────────────────
1. Buat fungsi send_xxx(phone, session) yang mengembalikan requests.Response.
2. Buat fungsi check_xxx(response) -> bool  (opsional; kalau tidak ada, pakai
   pengecekan generik: HTTP 2xx + success_on).
3. Daftarkan dengan Provider(...) di bagian bawah file.

Tidak perlu menyentuh file lain.

Format nomor tersedia di utils.py:
  fmt_08    →  08xxxxxxxxxx
  fmt_plus  →  +628xxxxxxxxxx
  fmt_62    →  628xxxxxxxxxx
  fmt_nocode →  8xxxxxxxxxx

Placeholder untuk provider bertipe 'json':
  {number}  — nomor setelah diformat
  {raw}     — nomor strip 0 (tanpa kode negara)
  {rand}    — UUID v4 random
  {ip}      — IP publik mesin ini
  {email}   — email random
  {name}    — nama Indonesia random
  {pw}      — password random
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import quote

import requests
from requests.sessions import Session

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from useragents import get_random_ua
from utils import fmt_08, fmt_plus, fmt_62, fmt_nocode


# ─────────────────────────────────────────────────────────────
# Dataclass Provider
# ─────────────────────────────────────────────────────────────

@dataclass
class Provider:
    """Satu provider OTP.

    Untuk provider JSON sederhana, isi url + payload + (opsional) headers/referer.
    Untuk provider yang butuh enkripsi/logika khusus, isi send_fn (dan check_fn).
    Dua-duanya tidak perlu diisi sekaligus.
    """
    name       : str

    # ── Mode JSON (tidak butuh send_fn) ──────────────────────
    url        : str                        = ""
    payload    : str                        = ""   # template string dengan {placeholder}
    headers    : dict                       = field(default_factory=dict)
    referer    : str                        = ""

    # ── Format nomor ─────────────────────────────────────────
    number_fmt : Callable[[str], str]       = fmt_08

    # ── Deteksi sukses ───────────────────────────────────────
    success_on : list[str]                  = field(default_factory=list)

    # ── Mode custom (isi kalau butuh enkripsi/logic khusus) ──
    send_fn    : Callable | None            = None   # (phone, session) -> Response
    check_fn   : Callable | None            = None   # (response) -> bool

    # ── Kontrol ──────────────────────────────────────────────
    timeout    : int                        = 15
    enabled    : bool                       = True


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


def _send_indosaku(phone: str, session: Session) -> requests.Response:
    h = dict(_IS_HEADERS)
    h["b9uMD"]      = os.urandom(8).hex()
    h["User-Agent"] = get_random_ua()
    session.headers.update(h)
    payload = {
        "cVWzn1Oq"  : 1,
        "e8dv2iH"   : "INSA4",
        "yidTRs"    : phone.lstrip("0"),
        "mKm0HT8WuK": "1",
        "fnKDg"     : "Google",
    }
    return session.post(_IS_BASE + _IS_PATH, data=_is_encrypt(payload), timeout=30)


def _check_indosaku(response: requests.Response) -> bool:
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


def _send_rupiahcepat(phone: str, session: Session) -> requests.Response:
    h = dict(_RC_HEADERS)
    h["User-Agent"] = get_random_ua()
    session.headers.update(h)
    uid  = _rc_uuid()
    data = {"mobile": phone, "sms_type": "8", "otp_channel": "2"}
    return session.post(_RC_BASE + _RC_PATH, data="data=" + _rc_encrypt(data, uid), timeout=30)


def _check_rupiahcepat(response: requests.Response) -> bool:
    try:
        return response.json().get("code") == 0
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════
# 3. CAIRIN — multipart/form-data
# ═══════════════════════════════════════════════════════════════

_CAIRIN_FILE = "6f8c3b90c845f09ff1bfe714a30aede8"
_CAIRIN_IMEI = "352365091234567"


def _send_cairin(phone: str, session: Session) -> requests.Response:
    session.headers.update({"User-Agent": get_random_ua()})
    return session.post(
        "https://app.cairin.id/v1/app/sms/sendCaptcha",
        data={
            "haveImageCode": "0",
            "fileName"     : _CAIRIN_FILE,
            "phone"        : "0" + phone.lstrip("0"),
            "imageCode"    : "",
            "userImei"     : _CAIRIN_IMEI,
            "verifySend"   : "1",
            "type"         : "registry",
        },
        timeout=30,
    )


def _check_cairin(response: requests.Response) -> bool:
    try:
        return response.json().get("code") == "0"
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════
# DAFTAR PROVIDER
# ═══════════════════════════════════════════════════════════════
# Untuk menambah provider baru: tambah satu blok Provider(...) di sini.
# Lihat docstring di atas untuk panduan lengkap.

PROVIDERS: list[Provider] = [

    # ── 1. Indosaku — AES-128-ECB, SMS/WA ────────────────────
    Provider(
        name       = "Indosaku",
        number_fmt = fmt_08,
        send_fn    = _send_indosaku,
        check_fn   = _check_indosaku,
    ),

    # ── 2. RupiahCepat — AES-128-CBC + MD5, WA ───────────────
    Provider(
        name       = "RupiahCepat",
        number_fmt = fmt_08,
        send_fn    = _send_rupiahcepat,
        check_fn   = _check_rupiahcepat,
    ),

    # ── 3. Cairin — multipart/form-data, SMS ─────────────────
    Provider(
        name       = "Cairin",
        number_fmt = fmt_08,
        send_fn    = _send_cairin,
        check_fn   = _check_cairin,
    ),

    # ── 4. DuniaGames — JSON, nonaktif (endpoint 401/CF) ─────
    Provider(
        name       = "DuniaGames",
        url        = "https://api.duniagames.co.id/api/user/api/v2/user/send-otp",
        payload    = '{"phoneNumber":"{number}","userName":"{raw}"}',
        headers    = {
            "Content-Type": "application/json",
            "Origin"       : "https://duniagames.co.id",
            "x-device"     : "{rand}",
        },
        referer    = "https://duniagames.co.id/newregister/phone/email-register",
        number_fmt = fmt_plus,
        success_on = ['"code":0'],
        timeout    = 20,
        enabled    = False,
    ),

    # ════════════════════════════════════════════════════════════
    # Tambahkan provider baru di bawah baris ini.
    #
    # Contoh provider JSON sederhana:
    # Provider(
    #     name       = "NamaProvider",
    #     url        = "https://api.namaprovider.com/v1/otp/send",
    #     payload    = '{"phone":"{number}","type":"register"}',
    #     headers    = {"Content-Type": "application/json", "Origin": "https://namaprovider.com"},
    #     number_fmt = fmt_08,
    #     success_on = ['"status":"ok"'],
    # ),
    #
    # Contoh provider dengan logika custom:
    # Provider(
    #     name     = "NamaProvider",
    #     send_fn  = _send_namaprovider,   # definisikan fungsinya di atas
    #     check_fn = _check_namaprovider,
    # ),
    # ════════════════════════════════════════════════════════════
]
