import json
import subprocess
import sys
import tempfile


TOOLS = [{"name": "run_tests", "description": "Execute the MBPP candidate against its tests.", "inputSchema": {"type": "object", "properties": {"code": {"type": "string"}, "test_imports": {"type": "array", "items": {"type": "string"}}, "test_list": {"type": "array", "items": {"type": "string"}}}, "required": ["code", "test_list"]}}]


def run_tests(code: str, test_imports: list[str] | None = None, test_list: list[str] | None = None) -> str:
    """Execute candidate MBPP code and assertions in a bounded subprocess."""
    source = "\n".join(test_imports or []) + "\n" + code + "\n" + "\n".join(test_list or [])
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as file:
        file.write(source)
        path = file.name
    try:
        result = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=30)
        return f"exit_code={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
    except subprocess.TimeoutExpired as error:
        return f"timeout: {error}"


def serve() -> None:
    """Serve the MBPP MCP tool over newline-delimited JSON-RPC."""
    for line in sys.stdin:
        request = json.loads(line)
        if request.get("method", "").startswith("notifications/"):
            continue
        try:
            if request.get("method") == "initialize":
                result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "agent-smith-mbpp", "version": "0.1.0"}}
            elif request.get("method") == "tools/list":
                result = {"tools": TOOLS}
            elif request.get("method") == "tools/call":
                args = request.get("params", {}).get("arguments", {})
                result = {"content": [{"type": "text", "text": run_tests(**args)}]}
            else:
                result = {}
            print(json.dumps({"jsonrpc": "2.0", "id": request.get("id"), "result": result}), flush=True)
        except Exception as error:
            print(json.dumps({"jsonrpc": "2.0", "id": request.get("id"), "error": {"message": str(error)}}), flush=True)


if __name__ == "__main__":
    serve()