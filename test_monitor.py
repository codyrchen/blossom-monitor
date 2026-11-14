"""Offline tests, including a replay of the Nov 2026 Mississippi bug."""
from monitor import USPS, Report, check_insurance_options, check_state_options, parse_option_lists


def bundle(pairs, insurance=("Aetna", "Cigna")):
    states = ",".join(f"{{label:`{l}`,value:`{c}`}}" for l, c in pairs)
    ins = ",".join(f"{{label:`{x}`,value:`{x}`}}" for x in insurance)
    # same shape as the live Framer module
    return f"concernOptions:[{{label:``,value:``}}],insuranceOptions:[{ins}],stateOptions:[{states}],x:1"


FIXED = [(name, code) for name, code in USPS.items()]
# list as shipped before the fix: Mississippi -> MI, Arkansas missing
BUGGY = [(n, "MI" if n == "Mississippi" else c) for n, c in FIXED if n != "Arkansas"]


def run(pairs):
    rep = Report()
    lists = parse_option_lists(bundle(pairs))
    check_state_options(lists["stateOptions"], rep)
    return rep


def test_parses_live_shape():
    lists = parse_option_lists(bundle(FIXED))
    assert len(lists["stateOptions"]) == 51
    assert lists["insuranceOptions"] == [("Aetna", "Aetna"), ("Cigna", "Cigna")]


def test_flags_original_bug():
    rep = run(BUGGY)
    assert any("Mississippi to 'MI'" in f for f in rep.failures)
    assert any("MI is used by more than one option" in f for f in rep.failures)
    assert any("Arkansas" in w for w in rep.warnings)


def test_fixed_list_passes():
    rep = run(FIXED)
    assert rep.failures == [] and rep.warnings == []


def test_flags_wrong_state_licensing_faq():
    from monitor import check_location_text
    bad = "<p>Due to medical licensing requirements, your Connecticut-licensed provider can only provide care when you&#x27;re physically located in New York.</p>"
    good = "<p>Due to medical licensing requirements, your Texas-licensed provider can only provide care when you're physically located in Texas.</p>"
    rep = Report()
    check_location_text("/locations/connecticut", bad, rep)
    check_location_text("/locations/texas", good, rep)
    assert len(rep.failures) == 1 and "New York" in rep.failures[0]


def test_city_check_flags_only_the_real_bug():
    from monitor import check_city_text
    tpl = "Blossom connects you with licensed psychiatric providers in {} who offer care."
    cases = {
        "pittsburgh": "Philadelphia",   # the bug
        "philadelphia": "Philadelphia",
        "orlando": "Florida",
        "tampa": "Florida",
        "boston": "Massachusetts",
        "new-york-city": "New York",
        "los-angeles": "LA",
        "san-francisco": "SF",
    }
    rep = Report()
    for slug, named in cases.items():
        check_city_text(f"/locations/{slug}", tpl.format(named), rep)
    assert len(rep.failures) == 1 and "Pittsburgh" in rep.failures[0]


def test_city_check_ignores_state_pages():
    from monitor import check_city_text
    rep = Report()
    check_city_text("/locations/texas", "providers in Dallas who offer care", rep)
    assert rep.failures == []


def test_duplicate_insurance():
    rep = Report()
    check_insurance_options([("Aetna", "Aetna"), ("Aetna", "Aetna")], rep)
    assert rep.failures


def test_city_check_edge_cases():
    from monitor import check_city_text
    rep = Report()
    check_city_text("/locations/tampa", "providers in St. Petersburg who offer care", rep)
    check_city_text("/locations/pittsburgh", "providers in the Philadelphia area", rep)
    assert len(rep.failures) == 2
    assert "St Petersburg" in rep.failures[0] and "Philadelphia" in rep.failures[1]


def test_city_check_covers_unlisted_cities():
    from monitor import check_city_text
    rep = Report()
    check_city_text("/locations/st-louis", "providers in St. Louis who offer care", rep)
    assert rep.failures == [] and len(rep.warnings) == 1
    check_city_text("/locations/st-louis", "providers in Chicago who offer care", rep)
    assert len(rep.failures) == 1 and "Chicago" in rep.failures[0]
    rep = Report()
    check_city_text("/locations/washington-dc", "providers in Washington D.C. who", rep)
    assert rep.failures == [] and rep.warnings == []


def test_unreachable_site_reports_failure_instead_of_crashing(monkeypatch, capsys):
    import sys
    import requests
    import monitor

    def down(url, **kw):
        raise requests.ConnectionError("site down")

    monkeypatch.setattr(monitor, "get", down)
    monkeypatch.setattr(sys, "argv", ["monitor.py"])
    assert monitor.main() == 1
    out = capsys.readouterr().out
    assert "Could not load" in out and "2 failures" in out


# trimmed copy of the live per-state map
STATE_MAP = (
    "stateOptions:[],ys={CA:[{label:`Anthem`,value:`Anthem`}],"
    "PA:[{label:`Capital Blue Cross (Blue Cross Blue Shield)`,value:`Highmark of Pennsylvania`},"
    "{label:`Highmark (Blue Cross Blue Shield)`,value:`Highmark of Pennsylvania`},"
    "{label:`Independence Blue Cross (Blue Cross Blue Shield)`,value:`Independence Blue Cross`}],"
    "NV:[{label:`Anthem`,value:`Anthem`}]},bs=1"
)


def test_state_insurers_flags_shared_value():
    from monitor import check_state_insurers, parse_state_insurers
    by_state = parse_state_insurers(STATE_MAP)
    assert set(by_state) == {"CA", "PA", "NV"}
    rep = Report()
    check_state_insurers(by_state, {"CA", "PA", "NV"}, rep)
    assert len(rep.failures) == 1
    assert "PA" in rep.failures[0] and "Capital Blue Cross" in rep.failures[0]
    assert "Highmark of Pennsylvania" in rep.failures[0]


def test_state_insurers_warns_without_location_page():
    from monitor import check_state_insurers, parse_state_insurers
    rep = Report()
    check_state_insurers(parse_state_insurers(STATE_MAP), {"CA", "PA"}, rep)
    assert rep.warnings == ["NV has its own insurer list but no /locations page"]
