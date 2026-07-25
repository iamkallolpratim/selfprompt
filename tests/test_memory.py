from selfprompt.core.events import Action, ActionType, Critique, Observation, Turn
from selfprompt.memory.file_backend import FileMemory


def _turn(index, issues=None):
    return Turn(
        index=index,
        observation=Observation(summary=f"obs {index}"),
        critique=Critique(progress_made=not issues, confidence=0.7, issues=issues or []),
        action=Action(type=ActionType.MESSAGE, detail=f"action {index}"),
        result=f"result {index}",
    )


def test_record_and_load_turns(tmp_path):
    mem = FileMemory(tmp_path)
    mem.record_turn("goal-a", _turn(0))
    mem.record_turn("goal-a", _turn(1))

    turns = mem.load_turns("goal-a")
    assert len(turns) == 2
    assert turns[0].observation.summary == "obs 0"
    assert turns[1].result == "result 1"


def test_lessons_extracted_from_issues(tmp_path):
    mem = FileMemory(tmp_path)
    mem.record_turn("goal-b", _turn(0, issues=["something broke"]))

    lessons_file = tmp_path / "goal-b" / "lessons.md"
    assert lessons_file.exists()
    assert "something broke" in lessons_file.read_text()


def test_load_context_includes_progress_and_lessons(tmp_path):
    mem = FileMemory(tmp_path)
    mem.record_turn("goal-c", _turn(0, issues=["oops"]))

    context = mem.load_context("goal-c")
    assert "oops" in context
    assert "obs 0" in context


def test_load_context_truncates_to_max_chars(tmp_path):
    mem = FileMemory(tmp_path)
    for i in range(50):
        mem.record_turn("goal-d", _turn(i))

    context = mem.load_context("goal-d", max_chars=200)
    assert len(context) <= 200


def test_load_turns_empty_for_unknown_goal(tmp_path):
    mem = FileMemory(tmp_path)
    assert mem.load_turns("nonexistent") == []
