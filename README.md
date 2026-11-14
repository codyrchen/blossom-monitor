# Blossom site monitor

A small, read-only check that would have caught the November 2026 bug where choosing
**Mississippi** on Blossom's Get Started page sent patients into the **Michigan** booking flow
(the dropdown mapped `Mississippi` to `MI`, and Arkansas was missing).

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

## What a run covers

- **State dropdown:** all options on `/start`, each checked against its USPS code (51 as of writing)
- **Insurance dropdown:** the `/start` insurer options, checked for duplicates and empty values
- **Sitemap:** every URL in `sitemap.xml` (~580) fetched and checked for a 200 and a canonical link
- **Licensing + city text:** every `/locations/*` page checked that it names the right state and city

Run `python monitor.py` and paste the summary line it prints (`N failures, N warnings`) here once
you've seen it, rather than quoting a count you haven't run.

The offline tests replay the November 2026 state list, so they fail loudly on the original
Mississippi → MI mapping, the duplicate MI code, and the missing Arkansas, and on a location
page that names the wrong state.
