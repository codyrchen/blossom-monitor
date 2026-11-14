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
| Booking flow (`--booking`, optional) | a served state doesn't open on scheduling, or a state Blossom doesn't serve shows appointment times |

It reads the live dropdown lists straight from the JavaScript the Get Started page ships with,
so it tests exactly what patients see, not a copy of the config.

## Run it

```bash
pip install -r requirements.txt
python -m pytest -q        # offline tests, including a replay of the Mississippi bug
python monitor.py          # live checks, about a minute
```

`monitor.py` exits with code 1 on any failure, so it can run on a schedule (see
`.github/workflows/monitor.yml`, daily) or before each site publish.

The `--booking` check opens Blossom's intake flow once per state, which starts a session in
the intake tool each time, so it's off by default and meant to run only with Blossom's okay.

## Results on Nov 14, 2026

- State dropdown: 51 options, all correct (the Mississippi fix is live, Arkansas restored)
- Insurance dropdown: 9 options, no duplicates
- Sitemap: 580 pages listed; the ~120 main pages crawled by hand all return 200 with canonical links
- Licensing text: **fails today** on 3 pages that tell patients the wrong state: Connecticut, Orlando and Tampa say care is only available "when you're physically located in New York"
- Replaying the old list in the tests flags Mississippi → MI, the duplicate MI code, and the missing Arkansas
