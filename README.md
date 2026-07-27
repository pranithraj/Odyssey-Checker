# Odyssey IMAX 70MM ticket watcher

Watches the Celebration Cinema Grand Rapids North Fandango page for
*The Odyssey* IMAX 70MM showtimes on Aug 21, 2026, and pushes a phone
notification the moment tickets go on sale. Also includes a date-range
scanner for checking multiple dates at once.

## 1. Get notifications on your phone

Install the **ntfy** app (iOS/Android, free) and subscribe to the topic
`pranith-odyssey-imax70-ghr-8f2k` — or better, open `checker.py` and change
`NTFY_TOPIC` to your own random string first (topics are public by
default, so a unique name keeps strangers from guessing it and spamming
you). Subscribe to whatever you set it to.

## 2. Calibrate once (important)

Fandango's page layout might not match what's hardcoded in the script,
and it can change over time. Before relying on this, run it once locally:

```bash
pip install playwright
playwright install chromium
python checker.py --calibrate
```

This saves the rendered page text to `calibration_dump.txt`. Confirm:
- whether "The Odyssey (2026)" appears before or after the
  "NEW & COMING SOON" marker (before = scheduled, after = not yet)
- when scheduled, that "IMAX 70MM" and a time like "7:00p" appear within
  ~1500 characters after the title

If the wording or layout has changed, adjust `MOVIE_TITLE`,
`COMING_SOON_MARKER`, `FORMAT_MARKER`, or `TIME_PATTERN` at the top of
`checker.py`.

## 3. Test the happy path (recommended before trusting it)

Confirm it correctly detects an *available* movie too, not just the
"not available yet" case. If IMAX 70MM showtimes are already posted for
an earlier date (e.g. Aug 20), test against that:

```bash
python checker.py --date 2026-08-20
```

State is tracked **per URL**, so this won't interfere with the real Aug 21
check — testing against Aug 20 and having it fire won't mark Aug 21 as
already notified. If it correctly prints "Tickets appear to be available"
and you get the ntfy push, the whole pipeline (fetch → detect → notify) is
proven end to end.

You can also point it at a completely different URL to sanity-check parsing
in general:
```bash
python checker.py --url "https://www.fandango.com/.../theater-page?date=2026-08-20&a=11533"
```

## 4. Run it (single-date checker)

**Locally, one-off:**
```bash
python checker.py
```

**On a schedule (recommended): GitHub Actions**
1. Push this folder to a new GitHub repo (public or private — private is
   fine, Actions still runs on the free tier for personal repos).
2. That's it — `.github/workflows/check-tickets.yml` runs the check every
   30 minutes automatically. Check the "Actions" tab to see run history.
3. To change frequency, edit the `cron` line in that file.
4. To test it immediately without waiting, go to Actions → "Check Odyssey
   IMAX 70MM tickets" → "Run workflow".

**Locally on a schedule instead (if you'd rather not use GitHub):**
```bash
# crontab -e, then add:
*/30 * * * * cd /path/to/odyssey-ticket-agent && python3 checker.py >> log.txt 2>&1
```

## 5. Bonus: scan a whole date range instead of just Aug 21

`date_scanner.py` reuses the same detection logic but checks a range of
dates and tells you which ones have The Odyssey in IMAX 70MM — useful if
you're flexible on the date, or want a heads-up as soon as *any* new dates
open up, not just Aug 21.

```bash
python date_scanner.py                                   # next 21 days from today
python date_scanner.py --start 2026-08-01 --end 2026-09-15
```

It uses a **separate ntfy topic** (`pranith-odyssey-imax70-dates-ghr-4mq9`
by default — change it in `date_scanner.py`, same guidance as above) so
these alerts don't mix with the single-date Aug 21 checker. Subscribe to
it separately in the ntfy app.

It only notifies about *newly found* dates — re-running it after nothing's
changed stays quiet. State is tracked in `scanner_state.json`.

Since this makes one page load per date in the range (21 dates ≈ a minute
or two with the default 3-second delay between checks), it runs on its own,
less frequent schedule — `.github/workflows/scan-dates.yml` runs it once a
day rather than every 30 minutes. Adjust the cron line or `--delay` if you
want it faster/slower.

## 6. Resetting

**Single-date checker:** once tickets are found for a given URL, it won't
re-notify for that same URL. State lives in `state.json` (a list of
already-notified URLs) — delete it, or remove the specific URL entry, to
reset.

**Date scanner:** tracks which dates it has already found in
`scanner_state.json`. Delete it to be re-notified about dates you already
know about.

## Notes

- Fandango disallows automated access per their robots.txt. These scripts
  poll at a low frequency for personal, non-commercial use — this isn't a
  scraper serving other people. Keep the interval reasonable (15+ min for
  the single-date checker, once a day for the range scanner) and don't
  publish/share a running instance widely.
- If Fandango changes their page layout, `--calibrate` again and adjust
  the regex patterns at the top of `checker.py` (both scripts use them).
- Want it to also text/email you instead of (or in addition to) ntfy?
  Swap the `notify()` function for `smtplib` (email) or Twilio (SMS) —
  happy to add that if you'd rather have it.

