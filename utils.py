"""utils.py — Format nomor, random generator, helper."""
from __future__ import annotations

import random
import string
import uuid

import requests


# ─────────────────────────────────────────────────────────────
# Format nomor HP Indonesia
# Input selalu dinormalisasi ke bentuk "083114592321" dulu
# di engine sebelum dikirim ke formatter.
# ─────────────────────────────────────────────────────────────

def normalize(phone: str) -> str:
    """Normalisasi nomor HP ke format '08xxxxxxxx'."""
    p = phone.strip().replace(" ", "").replace("-", "")
    if p.startswith("+62"):
        p = "0" + p[3:]
    elif p.startswith("62"):
        p = "0" + p[2:]
    return p


def fmt_08(phone: str) -> str:
    """08xxxxxxxxxx  (format standar Indonesia)"""
    p = normalize(phone)
    if not p.startswith("0"):
        p = "0" + p
    return p


def fmt_nocode(phone: str) -> str:
    """8xxxxxxxxxx  (strip leading 0, tanpa kode negara)"""
    p = normalize(phone)
    return p.lstrip("0")


def fmt_plus(phone: str) -> str:
    """+628xxxxxxxxxx"""
    p = normalize(phone)
    return "+62" + p.lstrip("0")


def fmt_62(phone: str) -> str:
    """628xxxxxxxxxx  (kode negara tanpa +)"""
    p = normalize(phone)
    return "62" + p.lstrip("0")


def fmt_phone_only(phone: str) -> str:
    """Alias fmt_nocode — 8xxxxxxxxxx"""
    return fmt_nocode(phone)


# ─────────────────────────────────────────────────────────────
# Random generators untuk placeholder di payload
# ─────────────────────────────────────────────────────────────

_FIRST_NAMES = ["Budi", "Andi", "Sari", "Dian", "Eka", "Reza", "Nina", "Hana", "Fajar", "Lina"]
_LAST_NAMES  = ["Santoso", "Wijaya", "Kusuma", "Pratama", "Putri", "Sari", "Nugroho", "Rahayu"]


def random_name() -> str:
    return f"{random.choice(_FIRST_NAMES)} {random.choice(_LAST_NAMES)}"


def random_email(phone: str = "") -> str:
    suffix = phone.lstrip("0")[-6:] if phone else str(random.randint(100000, 999999))
    domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com"]
    return f"user{suffix}@{random.choice(domains)}"


def random_pw() -> str:
    chars = string.ascii_letters + string.digits
    base  = "".join(random.choices(chars, k=8))
    return f"P{base}1!"


def random_ip() -> str:
    """IP Indonesia umum (Telkom, Indosat, XL range)."""
    ranges = [
        (180, 240, 1, 254),   # Telkom
        (114, 122, 1, 254),   # Indosat
        (36,  73, 1, 254),    # XL
    ]
    r = random.choice(ranges)
    return f"{r[0]}.{r[1]}.{random.randint(r[2], r[3])}.{random.randint(1, 254)}"


def random_uuid() -> str:
    return str(uuid.uuid4())


def random_uuid_hex() -> str:
    return uuid.uuid4().hex


# ─────────────────────────────────────────────────────────────
# Public IP — cache sekali per sesi
# ─────────────────────────────────────────────────────────────

_cached_public_ip: str | None = None

def get_public_ip() -> str:
    """
    Kembalikan IP publik nyata mesin ini.
    Di-cache setelah pertama kali dipanggil agar tidak fetch ulang tiap request.
    Fallback ke IP random Indonesia jika fetch gagal.
    """
    global _cached_public_ip
    if _cached_public_ip is not None:
        return _cached_public_ip
    try:
        resp = requests.get("https://api.ipify.org", timeout=5)
        _cached_public_ip = resp.text.strip()
    except Exception:
        _cached_public_ip = random_ip()
    return _cached_public_ip


# ─────────────────────────────────────────────────────────────
# Resolve placeholder dalam payload string
# ─────────────────────────────────────────────────────────────

def resolve_payload(template: str, phone_formatted: str, phone_raw: str) -> str:
    """
    Ganti semua placeholder di template string.
    phone_formatted = setelah diformat oleh number_fmt target
    phone_raw       = nomor asli tanpa kode negara (strip 0)
    """
    return (
        template
        .replace("{number}", phone_formatted)
        .replace("{raw}",    phone_raw)
        .replace("{rand}",   random_uuid())
        .replace("{ip}",     get_public_ip())
        .replace("{email}",  random_email(phone_raw))
        .replace("{name}",   random_name())
        .replace("{pw}",     random_pw())
    )
