import pytest

import project
from project import get_winner, summarize_rivalry, validate_score


PLAYERS = ("Alex", "Sam")


@pytest.mark.parametrize("goals,pens", [
    ((-1, 0), None), ((1,), None), ((2, 1), (5, 4)), ((2, 2), (4, 4)),
])
def test_validate_score(goals, pens):
    with pytest.raises(ValueError):
        validate_score(goals, pens)


@pytest.mark.parametrize("goals,pens,winner", [
    ((2, 1), None, "Alex"), ((0, 3), None, "Sam"), ((0, 0), None, None),
    ((2, 2), (5, 4), "Alex"), ((1, 1), (3, 4), "Sam"),
])
def test_get_winner(goals, pens, winner):
    assert get_winner(PLAYERS, goals, pens) == winner


def test_summarize_rivalry():
    matches = [((2, 2), (5, 4)), ((1, 3), None), ((0, 0), None)]
    assert summarize_rivalry(PLAYERS, matches) == {
        "Alex": dict(wins=1, draws=1, losses=1, goals=3),
        "Sam": dict(wins=1, draws=1, losses=1, goals=5),
    }


def test_reopen_rivalry(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(project, "DATABASE", tmp_path / "matches.sqlite3")
    answers = iter(["Alex", "Sam", "1", "2-1", "1", "2-2", "5-4", "4"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    project.main()
    answers = iter(["2", "3", "4"])
    project.main()
    output = capsys.readouterr().out
    assert output.index("Alex 2-2 Sam (5-4 on pens)") < output.index("Alex 2-1 Sam")
    assert "Alex: 2 W, 0 D, 0 L, 4 goals" in output


@pytest.mark.parametrize("edit,expected_first,expected_stats", [
    (["1", "1-3", "y"], "Alex 1-3 Sam", "Alex: 0 W, 1 D, 1 L, 1 goals"),
    (["1", "1-3", ""], "Alex 2-2 Sam (5-4 on pens)", "Alex: 1 W, 1 D, 0 L, 2 goals"),
    (["99"], "Alex 2-2 Sam (5-4 on pens)", "Alex: 1 W, 1 D, 0 L, 2 goals"),
])
def test_correct_match(tmp_path, monkeypatch, capsys, edit, expected_first, expected_stats):
    monkeypatch.setattr(project, "DATABASE", tmp_path / "matches.sqlite3")
    answers = iter(["Alex", "Sam", "1", "2-2", "5-4", "1", "0-0", "", "5", *edit, "4"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    project.main()
    messages = capsys.readouterr().out
    if edit == ["99"]:
        assert "Match ID not found" in messages
    else:
        assert "Current #1: Alex 2-2 Sam (5-4 on pens)" in messages
        assert "Proposed #1: Alex 1-3 Sam" in messages

    answers = iter(["2", "3", "4"])
    project.main()
    output = capsys.readouterr().out
    assert f"#2: Alex 0-0 Sam\n#1: {expected_first}\n" in output
    assert expected_stats in output
