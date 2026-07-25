import json

import pytest


def decision(observation="", progress=True, confidence=0.8, issues=None, action_type="finish", **action_kwargs):
    payload = {
        "observation": observation,
        "critique": {
            "progress_made": progress,
            "confidence": confidence,
            "issues": issues or [],
            "notes": "",
        },
        "action": {"type": action_type, "detail": "detail", **action_kwargs},
    }
    return json.dumps(payload)


@pytest.fixture
def make_decision():
    return decision
