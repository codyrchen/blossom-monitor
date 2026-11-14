# Blossom site monitor

Read-only script that checks the Get Started dropdowns, every sitemap page, and the location page text on joinblossomhealth.com, and exits 1 if anything is wrong.

Nov 14, 2026 run (5 failures, 7 warnings):

- Connecticut, Orlando and Tampa pages say care is only available "when you're physically located in New York"
- Pittsburgh page says its providers are in Philadelphia
- In PA, Capital Blue Cross and Highmark both send "Highmark of Pennsylvania"
- DE, ME, MO, NH, NV, WI and WV have insurer lists but no /locations page (warnings)
- State dropdown (51) and the 580 sitemap pages passed

| Check | Fails when |
|---|---|
| State dropdown | a state has the wrong USPS code, two states share a code, or a state is listed twice. Missing states warn. |
| Insurance dropdown | an insurer is listed twice or has an empty value |
| State insurer lists | two insurers in one state send the same value. A state with a list but no /locations page warns. |
| Sitemap | a page doesn't return 200. No canonical link warns. |
| Licensing text | a location page names a different state than the provider's license |
| City text | a city page names a place other than its city or state. Cities missing from `CITY_STATE` warn. |
| Booking (`--booking`) | a served state doesn't reach scheduling, or an unserved state shows times |

```bash
pip install -r requirements.txt
python -m pytest -q
python monitor.py --json results.json
```

`--booking` needs Playwright and starts an intake session per state, so only run it with Blossom's ok. The GitHub Action is manual only for now.
