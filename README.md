# Blossom site monitor

**The problem it guards against.** In November 2026, choosing **Mississippi** on Blossom's
Get Started page sent patients into **Michigan's** booking flow — the dropdown mapped
`Mississippi` to `MI`. A patient could have booked a provider not licensed in their state.

**What this does.** In about a minute it checks the state and insurance dropdowns, every page
in the sitemap, and the licensing and city text on each location page, and it exits non-zero
(fails loudly) the moment any of it is wrong. Nothing to install beyond Python; it's read-only
and never touches the booking system unless you explicitly opt in.

**Run on Nov 14, 2026, it flagged 4 pages that give patients the wrong location:**

- **Connecticut, Orlando, and Tampa** tell patients their provider "can only provide care when
  you're physically located in **New York**" — the same licensing risk as the Mississippi bug.
- **Pittsburgh** says its providers are in **Philadelphia**.

(Re-run before relying on these — Blossom fixed the Mississippi bug within hours of it being
reported, so the live site may already differ.)

## What it checks

| Check | Fails when |
|---|---|
| State dropdown | any state maps to the wrong USPS code, two states share a code, or a state is listed twice. Missing states are warnings. |
| Insurance dropdown | an insurer is listed twice or has an empty value |
| Sitemap | any page in `sitemap.xml` doesn't return 200. Pages without a canonical link are warnings. |
| Licensing text | a location page tells patients their provider (licensed in one state) can see them only in a different state |
| City text | a city page says its providers are in a different city (e.g. the Pittsburgh page naming Philadelphia) |
| Booking flow (`--booking`, optional) | a served state doesn't open on scheduling, or a state Blossom doesn't serve shows appointment times |

It reads the live dropdown lists straight from the JavaScript the Get Started page ships with,
so it tests exactly what patients see, not a copy of the config.

## Run it

```bash
pip install -r requirements.txt
python -m pytest -q        # offline tests, including a replay of the Mississippi bug
python monitor.py          # live checks, about a minute
```

`monitor.py` exits with code 1 on any failure, so it can gate a site publish or run on a
schedule. The included GitHub Action (`.github/workflows/monitor.yml`) is manual-only
(`workflow_dispatch`); flip on the daily `schedule` once Blossom wants it running automatically.

The `--booking` check opens Blossom's intake flow once per state, which starts a session in
the intake tool each time, so it's off by default and meant to run only with Blossom's okay.

The offline tests replay the November 2026 state list, so they fail on the original
Mississippi → MI mapping, the duplicate MI code, the missing Arkansas, a location page that
names the wrong state, and a city page (Pittsburgh) that names the wrong city.
