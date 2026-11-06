from errors import ToolError, error_dict, run_tool

def test_tool_error_shape():
    assert ToolError("NO_RESULTS", "没找到").to_dict() == {
        "error": {"code": "NO_RESULTS", "message": "没找到"}
    }

def test_run_tool_catches_tool_error():
    def f():
        raise ToolError("NO_RESULTS", "没找到")
    assert run_tool(f)["error"]["code"] == "NO_RESULTS"

def test_run_tool_catches_unexpected():
    def f():
        raise RuntimeError("boom")
    assert run_tool(f)["error"]["code"] == "INTERNAL"
