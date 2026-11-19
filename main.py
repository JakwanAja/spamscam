"""
main.py — Entry point tools OTP spam.
Jalankan: python main.py
"""
from __future__ import annotations

import math
import re
import shutil
import threading
import time

from rich.console import Console
from rich.text import Text
from rich.theme import Theme

from engine import Result, send_all
from providers import PROVIDERS
from utils import normalize, get_public_ip

# ─────────────────────────────────────────────────────────────
COOLDOWN_SECONDS = 62

THEME = Theme({
    "accent"  : "cyan",
    "muted"   : "dim",
    "success" : "bold green",
    "warning" : "yellow",
    "error"   : "bold red",
    "info"    : "bold white",
})

console = Console(theme=THEME, highlight=False, color_system="standard")

# ─────────────────────────────────────────────────────────────
# Banner
# ─────────────────────────────────────────────────────────────

BANNER = r"""
███████╗██████╗  █████╗ ███╗   ███╗███████╗ ██████╗ █████╗ ███╗   ███╗
██╔════╝██╔══██╗██╔══██╗████╗ ████║██╔════╝██╔════╝██╔══██╗████╗ ████║
███████╗██████╔╝███████║██╔████╔██║███████╗██║     ███████║██╔████╔██║
╚════██║██╔═══╝ ██╔══██║██║╚██╔╝██║╚════██║██║     ██╔══██║██║╚██╔╝██║
███████║██║     ██║  ██║██║ ╚═╝ ██║███████║╚██████╗██║  ██║██║ ╚═╝ ██║
╚══════╝╚═╝     ╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝     ╚═╝"""


def print_banner() -> None:
    console.print(BANNER, style="bold white")
    console.print()
    console.print("SPAMSCAM v2  /  OTP SPAM TOOL", style="bold")
    console.print(
        f"Data-driven · Paralel · {sum(1 for p in PROVIDERS if p.enabled)} provider aktif",
        style="muted",
    )
    console.print()


# ─────────────────────────────────────────────────────────────
# Input
# ─────────────────────────────────────────────────────────────

def read_input() -> tuple[str, int] | None:
    raw_phone = input("  Nomor HP     : ").strip()
    no_hp = normalize(raw_phone)

    if not re.fullmatch(r"08\d{8,14}", no_hp):
        console.print(
            "\n  [!] Nomor HP tidak valid. Contoh: 08978397772\n",
            style="error",
        )
        return None

    raw_count = input("  Jumlah siklus: ").strip()
    try:
        count = int(raw_count) if raw_count else 1
    except ValueError:
        console.print("\n  [!] Jumlah harus berupa angka.\n", style="error")
        return None

    if count < 1:
        console.print("\n  [!] Jumlah minimal 1.\n", style="error")
        return None

    return no_hp, count


# ─────────────────────────────────────────────────────────────
# Countdown
# ─────────────────────────────────────────────────────────────

def countdown(seconds: float, stop_flag: threading.Event) -> None:
    end = time.monotonic() + seconds
    while True:
        if stop_flag.is_set():
            break
        remaining = end - time.monotonic()
        if remaining <= 0:
            break
        mins, secs = divmod(math.ceil(remaining), 60)
        print(f"\r  Cooldown: {mins:02d}:{secs:02d} ...", end="", flush=True)
        time.sleep(min(0.5, remaining))
    print("\r" + " " * 30 + "\r", end="", flush=True)


# ─────────────────────────────────────────────────────────────
# Satu siklus — jalankan semua provider paralel, tampil real-time
# ─────────────────────────────────────────────────────────────

def run_cycle(phone: str, cycle: int, total: int,
              stop_flag: threading.Event) -> tuple[int, int, int]:
    """
    Jalankan satu siklus.
    Return (ok_count, limited_count, total_count).
    """
    width   = min(50, shutil.get_terminal_size((88, 24)).columns - 2)
    divider = "─" * width

    console.print()
    console.print(f"  {divider}", style="muted")
    header = Text()
    header.append(f"  Siklus {cycle}/{total}", style="bold accent")
    header.append(f"  ·  Target: {phone}", style="muted")
    console.print(header)
    console.print(f"  {divider}", style="muted")

    results: list[Result] = []
    col_w = 22

    for result in send_all(phone, PROVIDERS, stop_flag=stop_flag):
        results.append(result)
        label = f"  {result.name}"
        if result.ok:
            console.print(f"{label:{col_w + 2}} [[success]OK[/success]]")
        elif result.limited:
            console.print(f"{label:{col_w + 2}} [[warning]LIMIT[/warning]]")
        else:
            console.print(f"{label:{col_w + 2}} [[error]Gagal[/error]]")

        if stop_flag.is_set():
            break

    ok_count      = sum(1 for r in results if r.ok)
    limited_count = sum(1 for r in results if r.limited)
    fail_count    = len(results) - ok_count - limited_count

    console.print(f"  {divider}", style="muted")
    summary = Text("  Hasil: ")
    summary.append(f"{ok_count} OK", style="bold green")
    summary.append(" / ")
    summary.append(f"{limited_count} Limit", style="yellow")
    summary.append(" / ")
    summary.append(f"{fail_count} Gagal", style="bold red")
    summary.append(f"  dari {len(results)} provider")
    console.print(summary)

    return ok_count, limited_count, len(results)


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def main() -> None:
    print_banner()

    data = read_input()
    if data is None:
        return

    phone, total_cycles = data

    # Fetch IP publik sekali di awal, cache untuk seluruh sesi
    console.print("  Mendapatkan IP publik...", style="muted", end="\r")
    get_public_ip()
    console.print(" " * 35, end="\r")

    stop_flag = threading.Event()

    try:
        total_ok      = 0
        total_limited = 0
        total_sent    = 0

        for i in range(1, total_cycles + 1):
            if stop_flag.is_set():
                break

            ok, limited, sent = run_cycle(phone, i, total_cycles, stop_flag)
            total_ok      += ok
            total_limited += limited
            total_sent    += sent

            if i < total_cycles and not stop_flag.is_set():
                console.print(
                    f"\n  Cooldown {COOLDOWN_SECONDS}s sebelum siklus berikutnya...",
                    style="muted",
                )
                countdown(COOLDOWN_SECONDS, stop_flag)

    except KeyboardInterrupt:
        stop_flag.set()
        console.print("\n\n  [!] Dibatalkan.\n", style="warning")
        return

    if stop_flag.is_set() and total_sent == 0:
        return

    summary = Text("\n  Selesai. Total: ")
    summary.append(f"{total_ok} OK", style="bold green")
    summary.append(" / ")
    summary.append(f"{total_limited} Limit", style="yellow")
    summary.append(f"  dari {total_sent} request.\n")
    console.print(summary)


if __name__ == "__main__":
    main()
