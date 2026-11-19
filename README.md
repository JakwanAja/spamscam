# SpamScam

Tool OTP bombing untuk nomor HP Indonesia. Tiap siklus mengirim request ke semua provider secara paralel, lalu menunggu cooldown 62 detik sebelum siklus berikutnya.

## Provider aktif

| # | Provider | Metode | Channel |
|---|---|---|---|
| 1 | Indosaku | AES-128-ECB | SMS / WA |
| 2 | RupiahCepat | AES-128-CBC + MD5 signature | WA |
| 3 | Cairin | multipart/form-data | SMS |

> DuniaGames dinonaktifkan sementara — endpoint mengembalikan 401/Cloudflare.

## Instalasi

```
pip install -r requirements.txt
```

## Cara pakai

```
python main.py
```

Masukkan nomor target (format `08xxxxxxxxxx`) dan jumlah siklus.

## Output label

| Label | Warna | Artinya |
|---|---|---|
| `OK` | Hijau | OTP berhasil dikirim |
| `LIMIT` | Kuning | Provider mendeteksi rate limit (HTTP 429) |
| `Gagal` | Merah | Error jaringan atau response tidak valid |

## Struktur proyek

```
spamscam/
├── main.py          — Entry point & CLI
├── engine.py        — Dispatcher paralel (ThreadPoolExecutor)
├── providers.py     — Semua provider: definisi + logika request dalam satu file
├── utils.py         — Format nomor, placeholder resolver, get_public_ip
├── useragents.py    — Pool 20 User-Agent untuk rotasi per request
└── requirements.txt
```

## Cara menambah provider baru

Buka `providers.py`, tambahkan satu blok `Provider(...)` di bagian bawah daftar `PROVIDERS`.

**Provider JSON sederhana** (tidak butuh enkripsi):
```python
Provider(
    name       = "NamaProvider",
    url        = "https://api.namaprovider.com/v1/otp/send",
    payload    = '{"phone":"{number}","type":"register"}',
    headers    = {"Content-Type": "application/json"},
    number_fmt = fmt_08,
    success_on = ['"status":"ok"'],
),
```

**Provider dengan logika khusus** (enkripsi, signature, dsb):
```python
def _send_namaprovider(phone, session): ...
def _check_namaprovider(response): ...

Provider(
    name     = "NamaProvider",
    send_fn  = _send_namaprovider,
    check_fn = _check_namaprovider,
),
```

Tidak perlu menyentuh file lain.

## Dependensi

```
requests
pycryptodome
rich
```
