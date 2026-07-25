from selfprompt.tools.base import ToolResult
from selfprompt.tools.filesystem import ListDirTool, ReadFileTool, WriteFileTool
from selfprompt.tools.registry import Permission, ToolRegistry


class DangerousTool:
    name = "danger"
    description = "does something risky"
    dangerous = True

    def run(self, **kwargs):
        return ToolResult(ok=True, output="did the risky thing")


def test_read_write_roundtrip(tmp_path):
    target = tmp_path / "note.txt"
    registry = ToolRegistry([WriteFileTool(), ReadFileTool()], permission_mode=Permission.ALLOW)

    write_result = registry.call("write_file", path=str(target), content="hello")
    assert write_result.ok

    read_result = registry.call("read_file", path=str(target))
    assert read_result.ok
    assert read_result.output == "hello"


def test_list_dir(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "sub").mkdir()
    registry = ToolRegistry([ListDirTool()])
    result = registry.call("list_dir", path=str(tmp_path))
    assert result.ok
    assert "a.txt" in result.data["entries"]
    assert "sub/" in result.data["entries"]


def test_unknown_tool_returns_error():
    registry = ToolRegistry([])
    result = registry.call("does_not_exist")
    assert not result.ok
    assert "unknown tool" in result.error


def test_dangerous_tool_denied_by_default():
    registry = ToolRegistry([DangerousTool()], permission_mode=Permission.DENY)
    result = registry.call("danger")
    assert not result.ok
    assert "denied" in result.error


def test_dangerous_tool_ask_mode_grants_on_true_callback():
    registry = ToolRegistry(
        [DangerousTool()], permission_mode=Permission.ASK, on_permission_request=lambda n, a: True
    )
    result = registry.call("danger")
    assert result.ok
    assert result.output == "did the risky thing"


def test_dangerous_tool_ask_mode_denies_on_false_callback():
    registry = ToolRegistry(
        [DangerousTool()], permission_mode=Permission.ASK, on_permission_request=lambda n, a: False
    )
    result = registry.call("danger")
    assert not result.ok


def test_tool_exception_becomes_tool_result():
    class BrokenTool:
        name = "broken"
        description = "always raises"
        dangerous = False

        def run(self, **kwargs):
            raise RuntimeError("boom")

    registry = ToolRegistry([BrokenTool()])
    result = registry.call("broken")
    assert not result.ok
    assert "boom" in result.error
