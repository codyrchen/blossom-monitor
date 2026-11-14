"""Blossom Health site monitor.

Catches the class of bug that sent Mississippi patients to Michigan: it reads the
live state and insurance lists the booking widget ships with and checks them, then
checks that every page in the sitemap loads and points to a canonical URL.

Usage:
    python monitor.py                 # core checks (fast, read-only, ~1 min)
    python monitor.py --booking       # also open the booking flow per state (needs Playwright)
    python monitor.py --json out.json # write results for CI

Exit code is 1 when any check fails, so it can gate deploys or run on a schedule.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import requests

SITE = "https://www.joinblossomhealth.com"
VISIT = "https://visit.joinblossomhealth.com"
UA = {"User-Agent": "blossom-site-monitor/1.0"}

USPS = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA",
    "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
    "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH",
    "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
    "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA",
    "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN",
    "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "Washington D.C.": "DC", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}


@dataclass
class Report:
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    def fail(self, msg: str) -> None:
        self.failures.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def note(self, msg: str) -> None:
        self.info.append(msg)


def get(url: str, **kw) -> requests.Response:
    for attempt in range(3):
        try:
            return requests.get(url, headers=UA, timeout=20, **kw)
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


# ---------------------------------------------------------------- widget options

OPTION_LIST = re.compile(r"(stateOptions|insuranceOptions):\[(.*?)\]", re.S)
OPTION = re.compile(r"label:[`\"']([^`\"']*)[`\"'],value:[`\"']([^`\"']*)[`\"']")


def parse_option_lists(js: str) -> dict[str, list[tuple[str, str]]]:
    """Return every non-empty stateOptions / insuranceOptions list found in a JS bundle."""
    found: dict[str, list[tuple[str, str]]] = {}
    for name, body in OPTION_LIST.findall(js):
        pairs = OPTION.findall(body)
        if pairs and name not in found:
            found[name] = pairs
    return found


def check_state_options(pairs: list[tuple[str, str]], rep: Report) -> None:
    labels = [label for label, _ in pairs]
    codes = [code for _, code in pairs]
    for label, code in pairs:
        expected = USPS.get(label)
        if expected is None:
            rep.warn(f"State dropdown has an unknown label: {label!r} -> {code}")
        elif code != expected:
            rep.fail(f"State dropdown maps {label} to {code!r}; should be {expected!r}")
    for code in sorted({c for c in codes if codes.count(c) > 1}):
        names = [label for label, c in pairs if c == code]
        rep.fail(f"State code {code} is used by more than one option: {', '.join(names)}")
    for label in sorted({x for x in labels if labels.count(x) > 1}):
        rep.fail(f"State {label} appears more than once in the dropdown")
    missing = [s for s in USPS if s not in labels]
    if missing:
        rep.warn(f"Missing from state dropdown: {', '.join(missing)}")
    rep.note(f"State dropdown: {len(pairs)} options checked")


def check_insurance_options(pairs: list[tuple[str, str]], rep: Report) -> None:
    values = [v for _, v in pairs]
    for v in sorted({x for x in values if values.count(x) > 1}):
        rep.fail(f"Insurance option {v!r} appears more than once")
    for label, value in pairs:
        if not value.strip():
            rep.fail(f"Insurance option {label!r} has an empty value")
    rep.note(f"Insurance dropdown: {', '.join(v for _, v in pairs)}")


def check_widget(rep: Report) -> None:
    html = get(f"{SITE}/start").text
    modules = sorted(set(re.findall(r"https://framerusercontent\.com/[^\"'\s)]+\.mjs", html)))
    lists: dict[str, list[tuple[str, str]]] = {}
    for url in modules:
        try:
            js = get(url).text
        except requests.RequestException as e:
            rep.warn(f"Could not load {url}: {e}")
            continue
        for name, pairs in parse_option_lists(js).items():
            lists.setdefault(name, pairs)
    if "stateOptions" not in lists:
        rep.fail("Could not find the booking widget's state list on /start (site structure changed?)")
    else:
        check_state_options(lists["stateOptions"], rep)
    if "insuranceOptions" in lists:
        check_insurance_options(lists["insuranceOptions"], rep)


# ---------------------------------------------------------------- pages

LICENSE_FAQ = re.compile(
    r"your ([A-Z][A-Za-z ]+?)-licensed provider can only provide care when you(?:'|&#x27;|’)re "
    r"physically located in ([A-Z][A-Za-z ]+?)\."
)


def check_page(url: str) -> tuple[str, int, str | None, str]:
    try:
        r = get(url)
    except requests.RequestException as e:
        return url, 0, str(e), ""
    canon = re.search(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', r.text)
    return url, r.status_code, canon.group(1) if canon else None, r.text


def check_location_text(url: str, html: str, rep: Report) -> None:
    """Location pages must tell patients the right state for licensing."""
    for licensed, located in set(LICENSE_FAQ.findall(html)):
        if licensed != located:
            rep.fail(f"{url} says your {licensed}-licensed provider can see you only in {located}")


def check_sitemap(rep: Report, workers: int = 8) -> list[str]:
    xml = get(f"{SITE}/sitemap.xml").text
    urls = re.findall(r"<loc>([^<]+)</loc>", xml)
    if not urls:
        rep.fail("sitemap.xml has no URLs")
        return []
    with ThreadPoolExecutor(workers) as pool:
        results = list(pool.map(check_page, urls))
    for url, status, canon, html in results:
        if status != 200:
            rep.fail(f"{url} returned {status or canon}")
            continue
        if canon is None:
            rep.warn(f"{url} has no canonical link")
        if "/locations/" in url:
            check_location_text(url, html, rep)
    rep.note(f"Sitemap: {len(urls)} pages checked")
    return urls


def served_states(urls: list[str]) -> set[str]:
    """States with a /locations/<state> page, i.e. where the site says Blossom practices."""
    slugs = {u.rstrip("/").rsplit("/locations/", 1)[-1] for u in urls if "/locations/" in u}
    return {code for name, code in USPS.items() if name.lower().replace(" ", "-") in slugs}


# ---------------------------------------------------------------- booking flow (optional)

def check_booking(served: set[str], rep: Report, insurance: str = "Aetna") -> None:
    """Open the booking flow for every state and record which step it lands on.

    Each page load starts a session in Blossom's intake tool, so run this sparingly
    (e.g. weekly, or before releases) and with Blossom's go-ahead.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=UA["User-Agent"])
        for name, code in USPS.items():
            page.goto(f"{VISIT}/?state={code}&insurance_plan={insurance}")
            try:
                page.wait_for_function("location.hash.length > 1", timeout=15000)
            except Exception:
                rep.fail(f"Booking flow for {name} never reached a step")
                continue
            step = page.evaluate("location.hash.slice(1)")
            if code in served and step != "time_slot_selection":
                rep.fail(f"{name} is a served state but booking opened on '{step}', not scheduling")
            elif code not in served and step == "time_slot_selection":
                rep.fail(f"{name} is not a served state but booking shows appointment times")
            elif code not in served:
                rep.note(f"{name}: not served; booking goes to '{step}'")
            time.sleep(1)
        browser.close()


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--booking", action="store_true", help="also test the booking flow per state")
    ap.add_argument("--json", help="write results to this file")
    args = ap.parse_args()

    rep = Report()
    check_widget(rep)
    urls = check_sitemap(rep)
    served = served_states(urls)
    rep.note(f"Served states (from /locations pages): {len(served)}: {', '.join(sorted(served))}")
    if args.booking:
        check_booking(served, rep)

    for label, items in (("FAIL", rep.failures), ("WARN", rep.warnings), ("INFO", rep.info)):
        for msg in items:
            print(f"[{label}] {msg}")
    print(f"\n{len(rep.failures)} failures, {len(rep.warnings)} warnings")
    if args.json:
        with open(args.json, "w") as f:
            json.dump(rep.__dict__, f, indent=2)
    return 1 if rep.failures else 0


if __name__ == "__main__":
    sys.exit(main())
