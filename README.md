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
├── handlers.py      — Handler custom (enkripsi AES, form-data)
├── targets.py       — Daftar provider & konfigurasi endpoint
├── utils.py         — Format nomor, placeholder resolver, get_public_ip
├── useragents.py    — Pool 20 User-Agent untuk rotasi per request
└── requirements.txt
```

## Dependensi

```
requests
pycryptodome
rich
```
