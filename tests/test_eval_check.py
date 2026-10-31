import pytest

from eval.check import SCRIPTED, compare_heldout, run_scripted

OK = {"failures": [], "wrong_mappings": [], "confirmed": 0}


def test_known_gap_is_not_a_regression():
    r = {"h": {**OK, "failures": ["gap"]}}
    assert compare_heldout(r, {"h": ["gap"]}) == ([], [])


def test_new_failure_is_a_regression():
    assert compare_heldout({"h": {**OK, "failures": ["new"]}}, {})[0] == ["h: new"]


def test_safety_breach_fails_even_if_listed_as_known():
    r = {"h": {**OK, "failures": ["wrong"], "wrong_mappings": ["c"], "confirmed": 1}}
    regressions, _ = compare_heldout(r, {"h": ["wrong"]})
    assert len(regressions) == 2


def test_closed_gap_is_reported():
    assert compare_heldout({"h": OK}, {"h": ["gap"]}) == ([], ["h: gap"])


@pytest.mark.parametrize("name", SCRIPTED)
def test_scripted_scenarios_match_the_frozen_outcomes(name, tmp_path):
    actual, confirmed = run_scripted(name, tmp_path)
    assert actual == SCRIPTED[name] and not confirmed
