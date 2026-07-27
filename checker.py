#!/usr/bin/env python3
"""
Checks a Fandango theater page for IMAX 70MM showtimes on a specific date,
and sends an ntfy.sh push notification the first time tickets appear.

Usage:
    python checker.py --calibrate          # dump rendered text for inspection
    python checker.py                      # normal run: checks the Aug 21 URL
    python checker.py --date 2026-08-20    # test against a different date
                                            # (state is tracked per-URL, so
                                            # this won't affect the Aug 21 check)
    python checker.py --url "<full url>"   # test against any arbitrary URL
"""

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

# ---- Config ---------------------------------------------------------------

DEFAULT_URL = (
    "https://www.fandango.com/celebration-cinema-grand-rapids-north-aaqou/"
    "theater-page?format=IMAX%2070MM&date=2026-08-21&a=11533"
)
# Note: confirmed via calibration that the format= query param does NOT
# reliably filter the page server-side, so detection filters for "IMAX 70MM"
# in the rendered text instead. Keeping the param in the URL is harmless.

BASE_THEATER_URL = (
    "https://www.fandango.com/celebration-cinema-grand-rapids-north-aaqou/"
    "theater-page?format=IMAX%2070MM&a=11533"
)


def url_for_date(date_str: str) -> str:
    """Build the theater-page URL for an arbitrary date, e.g. '2026-08-20'."""
    return f"{BASE_THEATER_URL}&date={date_str}"

# ntfy.sh topic — pick your own unique, hard-to-guess name.
# Anyone who knows the topic name can read your notifications, since ntfy
# topics are public by default unless self-hosted / auth'd.
NTFY_TOPIC = "pranith-odyssey-imax70-ghr-8f2k"

STATE_FILE = Path(__file__).parent / "state.json"

# Based on a real calibration dump (2026-07-26): Fandango does NOT show a
# "check back soon" message. A movie with no showtimes yet simply appears
# ONLY under the "NEW & COMING SOON" grid (just "Title (Year)", no times,
# no format). Once scheduled, it appears earlier in the page as its own
# section with format headers (e.g. "IMAX 70MM") and times.
#
# Also: the "format=" URL query param does NOT reliably filter results
# (confirmed — a Standard-format movie showed up despite format=IMAX 70MM),
# so filtering by format has to happen in the text, not the URL.
MOVIE_TITLE = r"the odyssey\s*\(2026\)"
COMING_SOON_MARKER = "NEW & COMING SOON"
# Real text is "IMAX® 70MM" (registered trademark symbol in between) — allow
# any short run of non-alphanumeric chars there, not just whitespace.
FORMAT_MARKER = r"imax\W{0,3}70\s*mm"

# Real showtimes render like "7:00p" / "9:35p" (single-letter am/pm, no "m").
TIME_PATTERN = r"\b\d{1,2}:\d{2}\s?[ap]m?\b"


# ---- Core logic -------------------------------------------------------------

def fetch_rendered_text(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        )
        # networkidle often never fires on sites with persistent background
        # connections (analytics, ads, polling) — wait for DOM instead, then
        # give the async showtime widget time to render.
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(5000)
        text = page.inner_text("body")
        browser.close()
        return text


def tickets_appear_available(text: str) -> bool:
    lowered = text.lower()

    # Only the portion of the page before "NEW & COMING SOON" contains
    # movies that actually have showtimes scheduled. If the title only
    # shows up in/after that section, nothing's been posted yet.
    coming_soon_idx = lowered.find(COMING_SOON_MARKER.lower())
    scheduled_section = lowered[:coming_soon_idx] if coming_soon_idx != -1 else lowered

    match = re.search(MOVIE_TITLE, scheduled_section)
    if not match:
        return False

    # Look at the text right after the title for an IMAX 70MM format header
    # followed by an actual showtime — that's the real "on sale" signal.
    window = scheduled_section[match.end(): match.end() + 1500]
    has_format = re.search(FORMAT_MARKER, window) is not None
    has_time = re.search(TIME_PATTERN, window) is not None

    return has_format and has_time


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"notified_urls": []}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state))


def already_notified(state: dict, url: str) -> bool:
    return url in state.get("notified_urls", [])


def mark_notified(state: dict, url: str) -> None:
    state.setdefault("notified_urls", []).append(url)


def notify(message: str) -> None:
    req = urllib.request.Request(
        url=f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={
            "Title": "Odyssey IMAX 70MM tickets are up!",
            "Priority": "urgent",
            "Tags": "tickets,movie_camera",
        },
        method="POST",
    )
    urllib.request.urlopen(req, timeout=15)


# ---- Entry points -----------------------------------------------------------

def calibrate(url: str):
    print(f"Fetching rendered page text from:\n{url}\n")
    text = fetch_rendered_text(url)
    dump_path = Path(__file__).parent / "calibration_dump.txt"
    dump_path.write_text(text)
    print(f"Saved rendered text to {dump_path}")
    print("\nCheck two things in that file:")
    print("1. Does 'The Odyssey (2026)' still only appear after the")
    print("   'NEW & COMING SOON' marker (not yet scheduled)? Once it's")
    print("   scheduled it should appear earlier, as its own section.")
    print("2. When it IS scheduled, confirm 'IMAX 70MM' and a time like")
    print("   '7:00p' appear within ~1500 chars after the title — if the")
    print("   layout differs, adjust FORMAT_MARKER / TIME_PATTERN.")


def run_check(url: str, quiet_if_notified: bool = True):
    state = load_state()
    if already_notified(state, url):
        if quiet_if_notified:
            print(f"Already notified for this URL previously — nothing to do.\n{url}")
        return

    text = fetch_rendered_text(url)
    if tickets_appear_available(text):
        print("Tickets appear to be available — sending notification.")
        notify(f"Showtimes are up for The Odyssey (IMAX 70MM):\n{url}")
        mark_notified(state, url)
        save_state(state)
    else:
        print("Not available yet.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibrate", action="store_true",
                         help="Dump rendered page text for manual inspection")
    parser.add_argument("--date", default=None,
                         help="Test against a different date, e.g. 2026-08-20 "
                              "(builds the URL automatically; tracked "
                              "separately from the default Aug 21 URL)")
    parser.add_argument("--url", default=None,
                         help="Test against a fully custom URL, overrides --date")
    args = parser.parse_args()

    if args.url:
        target_url = args.url
    elif args.date:
        target_url = url_for_date(args.date)
    else:
        target_url = DEFAULT_URL

    if args.calibrate:
        calibrate(target_url)
    else:
        run_check(target_url)
