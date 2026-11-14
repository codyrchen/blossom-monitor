"""Offline tests: the monitor must flag the Nov 2026 Mississippi bug and pass the fixed list."""
from monitor import USPS, Report, check_insurance_options, check_state_options, parse_option_lists


def bundle(pairs, insurance=("Aetna", "Cigna")):
    states = ",".join(f"{{label:`{l}`,value:`{c}`}}" for l, c in pairs)
    ins = ",".join(f"{{label:`{x}`,value:`{x}`}}" for x in insurance)
    # mirrors the shape of the live Framer module
    return f"concernOptions:[{{label:``,value:``}}],insuranceOptions:[{ins}],stateOptions:[{states}],x:1"


FIXED = [(name, code) for name, code in USPS.items()]
# The list as shipped before the fix: Mississippi -> MI, Arkansas missing
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


def test_duplicate_insurance():
    rep = Report()
    check_insurance_options([("Aetna", "Aetna"), ("Aetna", "Aetna")], rep)
    assert rep.failures
