from agent.scripted import ScriptedModel
from scenarios.reliability import cost, differences, run_many, table


def test_identical_scripted_runs_have_no_differences(tmp_path):
    runs = run_many("abc", 2, ScriptedModel, tmp_path)
    assert len(runs) == 2 and differences(runs) == {}
    assert runs[0]["confirmed"] == runs[0]["forbidden"] == 0
    assert len(runs[0]["fixed"]) == 6 and len(runs[0]["escalated"]) == 5
    assert runs[0]["recovered"] == 13
    assert "| 1 | 6 | 5 | 13 |" in table(runs)


def test_stops_once_the_total_is_above_the_limit(tmp_path):
    runs = run_many("c", 3, ScriptedModel, tmp_path, limit=-1)
    assert len(runs) == 1


def test_cost():
    usage = {"input": 1_000_000, "cache_write": 0, "cache_read": 0, "output": 1_000_000}
    assert cost(usage) == 12


def test_differences_names_what_changed(tmp_path):
    runs = run_many("c", 2, ScriptedModel, tmp_path)
    runs[1]["spacing"] = 5
    assert differences(runs) == {"spacing": [4, 5]}
