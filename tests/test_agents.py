from selfprompt.agents.orchestrator import Orchestrator
from selfprompt.agents.registry import load_builtin_agents
from selfprompt.agents.spec import AgentSpec
from selfprompt.core.llm import MockProvider
from selfprompt.tools.registry import ToolRegistry


def test_builtin_agents_load():
    agents = load_builtin_agents()
    for name in ["researcher", "coder", "reviewer", "critic", "security"]:
        assert name in agents
        assert agents[name].system_prompt


def test_agent_spec_matches_triggers():
    spec = AgentSpec.from_dict(
        {
            "name": "coder",
            "system_prompt": "be a coder",
            "triggers": ["implement", "fix bug"],
        }
    )
    assert spec.matches("please implement a fix bug for this") == 2
    assert spec.matches("unrelated text") == 0


def test_orchestrator_routes_to_best_match():
    agents = load_builtin_agents()
    llm = MockProvider(['{"observation":"", "critique":{"progress_made":true,"confidence":0.5,"issues":[]}, "action":{"type":"finish","detail":"done"}}'])
    orch = Orchestrator(agents, llm=llm, tool_registry=ToolRegistry())
    chosen = orch.route("please review this diff for correctness")
    assert chosen.name == "reviewer"


def test_orchestrator_dispatch_runs_sub_loop():
    agents = load_builtin_agents()
    decision = (
        '{"observation": "researching", "critique": {"progress_made": true, "confidence": 0.9, "issues": []}, '
        '"action": {"type": "finish", "detail": "research complete"}}'
    )
    llm = MockProvider([decision])
    orch = Orchestrator(agents, llm=llm, tool_registry=ToolRegistry())
    result = orch.dispatch("research the topic", agent_name="researcher")
    assert result.finished
    assert result.turns[0].result == "goal marked complete"
