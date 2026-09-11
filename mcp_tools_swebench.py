import json
import os
import re
import subprocess
import sys
import base64
from pathlib import Path


ROOT = Path(os.getenv("TESTBED_PATH", "/testbed")).resolve()
CONTAINER_ID = os.getenv("AGENT_SMITH_CONTAINER_ID", "")
TOOLS = [{"name": name, "description": description, "inputSchema": schema} for name, description, schema in [
    ("read_file", "Read a file with cat -n style line numbers.", {"type": "object", "properties": {"filepath": {"type": "string"}, "start_line": {"type": "integer"}, "end_line": {"type": "integer"}}, "required": ["filepath", "start_line", "end_line"]}),
    ("edit_file", "Replace an exact string in a file.", {"type": "object", "properties": {"filepath": {"type": "string"}, "old_str": {"type": "string"}, "new_str": {"type": "string"}}, "required": ["filepath", "old_str", "new_str"]}),
    ("list_files", "List matching files.", {"type": "object", "properties": {"directory": {"type": "string"}, "pattern": {"type": "string"}}, "required": ["directory", "pattern"]}),
    ("search_code", "Search code and return absolute paths and line numbers.", {"type": "object", "properties": {"pattern": {"type": "string"}, "file_pattern": {"type": "string"}}, "required": ["pattern", "file_pattern"]}),
    ("search_function_or_class_definition_in_code", "Find a function or class definition.", {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}),
    ("find_references", "Find symbol references.", {"type": "object", "properties": {"name": {"type": "string"}, "filepath": {"type": "string"}, "line": {"type": "integer"}}, "required": ["name", "filepath", "line"]}),
    ("run_tests", "Execute the evaluation script.", {"type": "object", "properties": {}, "required": []}),
    ("get_patch", "Retrieve the repository git diff.", {"type": "object", "properties": {}, "required": []}),
    ("run_command", "Execute a command in the repository.", {"type": "object", "properties": {"command": {"type": "string"}, "workdir": {"type": "string"}}, "required": ["command", "workdir"]}),
]]


def _path(path: str) -> Path:
    """Resolve a host testbed path and reject traversal outside its root."""
    value = Path(path)
    value = value if value.is_absolute() else ROOT / value
    value = value.resolve()
    if value != ROOT and ROOT not in value.parents:
        raise PermissionError("path is outside the testbed")
    return value


def _docker_exec(command: str, timeout: int = 120) -> str:
    """Execute a shell command inside the active SWE-bench container."""
    result = subprocess.run(["docker", "exec", CONTAINER_ID, "bash", "-lc", command], capture_output=True, text=True, timeout=timeout)
    return f"exit_code={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"


def read_file(filepath: str, start_line: int, end_line: int) -> str:
    """Read a file with one-based line numbers in cat -n format."""
    if CONTAINER_ID:
        return _docker_exec(f"nl -ba {filepath!r} | sed -n '{max(1, start_line)},{end_line}p'")
    lines = _path(filepath).read_text(encoding="utf-8").splitlines()
    return "\n".join(f"{index}: {lines[index - 1]}" for index in range(max(1, start_line), min(end_line, len(lines)) + 1))


def edit_file(filepath: str, old_str: str, new_str: str) -> str:
    """Replace one exact string occurrence in a testbed file."""
    if CONTAINER_ID:
        old_data = base64.b64encode(old_str.encode()).decode()
        new_data = base64.b64encode(new_str.encode()).decode()
        script = "import base64, pathlib, sys; p=pathlib.Path(sys.argv[1]); s=p.read_text(); old=base64.b64decode(sys.argv[2]).decode(); new=base64.b64decode(sys.argv[3]).decode(); assert s.count(old) == 1, 'old_str must occur exactly once'; p.write_text(s.replace(old, new))"
        _docker_exec(f"python -c {script!r} {filepath!r} {old_data!r} {new_data!r}")
        return "File edited successfully"
    path = _path(filepath)
    text = path.read_text(encoding="utf-8")
    if text.count(old_str) != 1:
        raise ValueError("old_str must occur exactly once")
    path.write_text(text.replace(old_str, new_str), encoding="utf-8")
    return "File edited successfully"


def list_files(directory: str, pattern: str) -> list[str]:
    """List files matching a glob inside the testbed."""
    if CONTAINER_ID:
        return _docker_exec(f"find {directory!r} -type f -name {pattern!r}").splitlines()
    return [str(path) for path in _path(directory).glob(pattern)]


def _grep(pattern: str, file_pattern: str = "**/*") -> str:
    """Search testbed text files and return path, line, and content matches."""
    if CONTAINER_ID:
        return _docker_exec(f"grep -RInE {pattern!r} {ROOT!s} --include={file_pattern!r} || true")
    regex = re.compile(pattern)
    result = []
    for path in _path(".").glob(file_pattern):
        if not path.is_file():
            continue
        try:
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if regex.search(line):
                    result.append(f"{path}:{number} {line}")
        except UnicodeDecodeError:
            continue
    return "\n".join(result)


def search_code(pattern: str, file_pattern: str = "**/*") -> str:
    """Search source files using a regular expression."""
    return _grep(pattern, file_pattern)


def search_function_or_class_definition_in_code(name: str) -> str:
    """Find function or class definitions with the requested name."""
    return _grep(rf"^\s*(?:async\s+)?(?:def|class)\s+{re.escape(name)}\b")


def find_references(name: str, filepath: str, line: int) -> str:
    """Find all textual references to a symbol in the testbed."""
    return _grep(rf"\b{re.escape(name)}\b")


def run_tests() -> str:
    """Run the configured SWE-bench evaluation script."""
    script = os.getenv("EVAL_SCRIPT", "")
    if not script:
        return "No evaluation script configured"
    if CONTAINER_ID:
        return _docker_exec(script, 600)
    result = subprocess.run(["bash", "-lc", script], cwd=ROOT, capture_output=True, text=True, timeout=600)
    return f"exit_code={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"


def get_patch() -> str:
    """Return the repository diff using the moulinette git command."""
    if CONTAINER_ID:
        return _docker_exec("git -c core.fileMode=false diff")
    result = subprocess.run(["git", "-c", "core.fileMode=false", "diff"], cwd=ROOT, capture_output=True, text=True, check=False)
    return result.stdout


def run_command(command: str, workdir: str) -> str:
    """Run a shell command in an allowed testbed working directory."""
    if CONTAINER_ID:
        return _docker_exec(f"cd {workdir!r} && {command}")
    result = subprocess.run(["bash", "-lc", command], cwd=_path(workdir), capture_output=True, text=True, timeout=120)
    return f"exit_code={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"


def serve() -> None:
    """Serve all SWE-bench MCP tools over newline-delimited JSON-RPC."""
    functions = {name: globals()[name] for name in [tool["name"] for tool in TOOLS]}
    for line in sys.stdin:
        request = json.loads(line)
        if request.get("method", "").startswith("notifications/"):
            continue
        try:
            if request.get("method") == "initialize":
                result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "agent-smith-swebench", "version": "0.1.0"}}
            elif request.get("method") == "tools/list":
                result = {"tools": TOOLS}
            elif request.get("method") == "tools/call":
                #                 {
                #   "method": "tools/call",
                #   "params": {
                #     "name": "run_tests",
                #     "arguments": {
                #       "code": "...",
                #       "test_list": ["..."]
                #     }
                #   }
                # }
                params = request.get("params", {})
                result = {"content": [{"type": "text", "text": str(functions[params["name"]](**params.get("arguments", {})))}]}
            else:
                result = {}
            print(json.dumps({"jsonrpc": "2.0", "id": request.get("id"), "result": result}), flush=True)
        except Exception as error:
            print(json.dumps({"jsonrpc": "2.0", "id": request.get("id"), "error": {"message": str(error)}}), flush=True)


if __name__ == "__main__":
    serve()