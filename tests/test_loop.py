import pytest

from selfprompt.core.events import ActionType
from selfprompt.core.llm import MockProvider, NullProvider
from selfprompt.core.loop import GoalLoop
from selfprompt.core.state import Budget, StopCondition
from selfprompt.memory.file_backend import FileMemory
from selfprompt.tools.base import ToolResult
from selfprompt.tools.registry import ToolRegistry


def test_loop_finishes_on_finish_action(make_decision):
    llm = MockProvider([make_decision(action_type="finish")])
    loop = GoalLoop("do the thing", llm=llm, budget=Budget(max_turns=5))
    result = loop.run()
    assert result.finished
    assert result.turn_count == 1
    assert result.turns[0].action.type is ActionType.FINISH


def test_loop_aborts_on_abort_action(make_decision):
    llm = MockProvider([make_decision(action_type="abort")])
    loop = GoalLoop("impossible thing", llm=llm, budget=Budget(max_turns=5))
    result = loop.run()
    assert not result.finished
    assert "aborted" in result.stop_reason


def test_loop_respects_max_turns(make_decision):
    llm = MockProvider([make_decision(action_type="message")])
    loop = GoalLoop("never finishes", llm=llm, budget=Budget(max_turns=3))
    result = loop.run()
    assert not result.finished
    assert result.turn_count == 3
    assert "max_turns" in result.stop_reason


def test_loop_stops_on_cost_budget(make_decision):
    llm = MockProvider(lambda prompt, system: make_decision(action_type="message"))
    loop = GoalLoop("burn money", llm=llm, budget=Budget(max_turns=100, max_cost_usd=0.0))
    result = loop.run()
    assert not result.finished
    # cost budget of 0.0 should stop before any turn accrues cost above it once tokens exist
    assert result.turn_count <= 1


def test_loop_stop_condition_short_circuits(make_decision):
    calls = {"n": 0}

    def responses(prompt, system):
        calls["n"] += 1
        return make_decision(action_type="message")

    llm = MockProvider(responses)
    turns_seen = []

    def goal_done(turns):
        turns_seen.append(len(turns))
        return len(turns) >= 2

    loop = GoalLoop(
        "goal",
        llm=llm,
        budget=Budget(max_turns=10),
        stop_conditions=[StopCondition("two_turns", goal_done)],
    )
    result = loop.run()
    assert result.finished
    assert result.turn_count == 2
    assert "stop condition met" in result.stop_reason


def test_loop_executes_tool_call():
    class EchoTool:
        name = "echo"
        description = "echoes args"
        dangerous = False

        def run(self, **kwargs):
            return ToolResult(ok=True, output=f"echoed: {kwargs.get('text')}")

    decision_1 = (
        '{"observation": "calling echo", "critique": {"progress_made": true, "confidence": 0.5, "issues": []}, '
        '"action": {"type": "tool_call", "detail": "echo it", "tool_name": "echo", "tool_args": {"text": "hi"}}}'
    )
    decision_2 = (
        '{"observation": "done", "critique": {"progress_made": true, "confidence": 0.9, "issues": []}, '
        '"action": {"type": "finish", "detail": "done"}}'
    )
    llm = MockProvider([decision_1, decision_2])
    tools = ToolRegistry([EchoTool()])
    loop = GoalLoop("echo hi", llm=llm, tools=tools, budget=Budget(max_turns=5))
    result = loop.run()
    assert result.finished
    assert result.turns[0].result == "echoed: hi"


def test_loop_handles_malformed_llm_response():
    llm = MockProvider(["this is not json at all"])
    loop = GoalLoop("goal", llm=llm, budget=Budget(max_turns=1))
    result = loop.run()
    assert not result.finished
    assert result.turns[0].critique.progress_made is False
    assert result.turns[0].action.type is ActionType.MESSAGE


def test_next_step_returns_prompt_when_not_done(tmp_path):
    loop = GoalLoop(
        "goal", llm=NullProvider(), memory=FileMemory(tmp_path), goal_id="host-driven"
    )
    step = loop.next_step()
    assert step["done"] is False
    assert step["turn_index"] == 0
    assert "GOAL" in step["prompt"]


def test_next_step_done_after_recorded_finish(tmp_path):
    loop = GoalLoop(
        "goal", llm=NullProvider(), memory=FileMemory(tmp_path), goal_id="host-driven"
    )
    loop.record_step(
        turn_index=0,
        observation="done",
        critique={"progress_made": True, "confidence": 0.9},
        action={"type": "finish", "detail": "complete"},
        result="goal marked complete",
    )
    step = loop.next_step()
    assert step["done"] is True
    assert "complete" in step["stop_reason"]


def test_next_step_done_after_recorded_abort(tmp_path):
    loop = GoalLoop(
        "goal", llm=NullProvider(), memory=FileMemory(tmp_path), goal_id="host-driven"
    )
    loop.record_step(
        turn_index=0,
        observation="stuck",
        critique={"progress_made": False, "confidence": 0.1},
        action={"type": "abort", "detail": "unreachable"},
        result="aborted: unreachable",
    )
    step = loop.next_step()
    assert step["done"] is True
    assert "aborted" in step["stop_reason"]


def test_next_step_respects_budget_across_calls(tmp_path):
    memory = FileMemory(tmp_path)
    loop = GoalLoop(
        "goal", llm=NullProvider(), memory=memory, goal_id="host-driven", budget=Budget(max_turns=1)
    )
    loop.record_step(
        turn_index=0,
        observation="working",
        critique={"progress_made": True, "confidence": 0.5},
        action={"type": "message", "detail": "still going"},
        result="still going",
    )
    step = loop.next_step()
    assert step["done"] is True
    assert "max_turns" in step["stop_reason"]


def test_record_step_persists_to_memory(tmp_path):
    memory = FileMemory(tmp_path)
    loop = GoalLoop("goal", llm=NullProvider(), memory=memory, goal_id="host-driven")
    result = loop.record_step(
        turn_index=0,
        observation="obs",
        critique={"progress_made": True, "confidence": 0.5},
        action={"type": "message", "detail": "note"},
        result="note",
    )
    assert result == {"finished": False, "aborted": False, "stop_reason": None}
    turns = memory.load_turns("host-driven")
    assert len(turns) == 1
    assert turns[0].observation.summary == "obs"


def test_null_provider_raises_if_actually_called():
    with pytest.raises(RuntimeError):
        NullProvider().complete("prompt")
