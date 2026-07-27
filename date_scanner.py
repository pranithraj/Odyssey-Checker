#!/usr/bin/env python3
"""
Scans a range of dates on the Celebration Cinema Grand Rapids North Fandango
page and reports which ones have The Odyssey in IMAX 70MM. Sends one ntfy.sh
push per run listing any *newly found* available dates (so you don't get
re-notified about a date you already know about).

Reuses fetch_rendered_text / tickets_appear_available / url_for_date from
checker.py — same detection logic, just applied across many dates instead
of one.

Usage:
    python date_scanner.py                         # default: next 21 days from today
    python date_scanner.py --start 2026-08-01 --end 2026-09-15
    python date_scanner.py --delay 5               # slower, more polite pacing
"""

import argparse
import json
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from checker import fetch_rendered_text, tickets_appear_available, url_for_date

# Separate topic from the single-date checker, so alerts don't mix.
# Pick your own unique string — same caveat as checker.py: ntfy topics are
# public by default, so don't use anything guessable.
NTFY_TOPIC = "pranith-odyssey-imax70-dates-ghr-4mq9"

STATE_FILE = Path(__file__).parent / "scanner_state.json"


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"known_available_dates": []}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state))


def notify(new_dates: list[str]) -> None:
    lines = "\n".join(new_dates)
    message = f"New IMAX 70MM Odyssey dates open at Celebration Cinema GR North:\n{lines}"
    req = urllib.request.Request(
        url=f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={
            "Title": "New Odyssey IMAX 70MM dates available!",
            "Priority": "urgent",
            "Tags": "tickets,movie_camera,calendar",
        },
        method="POST",
    )
    urllib.request.urlopen(req, timeout=15)


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def scan(start: date, end: date, delay_seconds: float) -> list[str]:
    """Returns list of date strings (YYYY-MM-DD) where tickets are available."""
    import time

    available = []
    for d in daterange(start, end):
        date_str = d.isoformat()
        url = url_for_date(date_str)
        try:
            text = fetch_rendered_text(url)
        except Exception as e:
            print(f"{date_str}: fetch failed ({e}), skipping")
            continue

        if tickets_appear_available(text):
            print(f"{date_str}: AVAILABLE")
            available.append(date_str)
        else:
            print(f"{date_str}: not yet")

        time.sleep(delay_seconds)

    return available


def main():
    parser = argparse.ArgumentParser()
    today = date.today()
    parser.add_argument("--start", default=today.isoformat(),
                         help="Start date YYYY-MM-DD (default: today)")
    parser.add_argument("--end", default=(today + timedelta(days=21)).isoformat(),
                         help="End date YYYY-MM-DD (default: 21 days from today)")
    parser.add_argument("--delay", type=float, default=3.0,
                         help="Seconds to wait between date checks (default: 3)")
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)

    print(f"Scanning {start} to {end} ({(end - start).days + 1} dates)...\n")
    available_now = scan(start, end, args.delay)

    state = load_state()
    known = set(state.get("known_available_dates", []))
    newly_found = sorted(set(available_now) - known)

    if newly_found:
        print(f"\nNew dates found: {newly_found}")
        notify(newly_found)
        state["known_available_dates"] = sorted(known | set(available_now))
        save_state(state)
    else:
        print("\nNo new dates since last run.")
        # Still refresh state in case some previously-available dates
        # dropped off (e.g. sold out and removed from the listing).
        if set(available_now) != known:
            state["known_available_dates"] = available_now
            save_state(state)


if __name__ == "__main__":
    main()
