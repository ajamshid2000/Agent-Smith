"""
Secure sandbox for executing untrusted Python code.

SECURITY MODEL:
- Code runs in a child process (isolated from parent)
- Child process has restricted privileges:
  * Can only import "safe" modules (math, collections, etc.)
  * Can only access allowed directories (/testbed, /tmp/agent)
  * Limited memory (512 MB by default)
  * Limited time (30 seconds by default)
  * No network access
- Parent monitors child and kills if timeout
- Tool calls proxied back to parent through pipe (child can't directly call tools)

WHY THIS MATTERS?
- LLM-generated code might be buggy or malicious
- Sandbox prevents it from:
  * Crashing the agent (running in separate process)
  * Accessing system files (path restrictions)
  * Consuming all resources (memory/time limits)
  * Exfiltrating data (no network)
  * Running malicious imports (import whitelist)

PERFORMANCE:
- Fork is fast (copy-on-write)
- Communication through pipe is efficient
- Timeout detection is responsive
"""

import argparse
import builtins
import contextlib
import json
import io
import multiprocessing
import os
import resource
import socket
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

from .mcp import MCPClient, MCPHTTPClient, tool_manual


class SandboxConfig(BaseModel):
    """
    Configuration for the sandbox security restrictions.
    
    DEFAULTS ARE CONSERVATIVE (safe):
    - Only allow very common, safe standard library modules
    - Only allow /testbed and /tmp/agent for file access
    - 30-second timeout (prevent infinite loops)
    - 512 MB RAM limit (prevent memory bombs)
    """
    authorized_imports: list[str] = Field(default_factory=lambda: [
        # SAFE MODULES: No file/network/subprocess access
        "math", "math.*",  # Math operations
        "collections", "collections.*",  # Data structures
        "itertools",  # Iteration tools
        "re",  # Regex
        "json",  # JSON parsing
        "typing", "typing.*",  # Type hints
        "functools",  # Function tools
        "operator",  # Operator functions
        "heapq",  # Heap queue
        "bisect",  # Binary search
        "copy",  # Copy objects
        "string",  # String constants
        "random",  # Random numbers
        "datetime", "datetime.*",  # Date/time
        "array",  # Arrays
        "cmath"  # Complex math
    ])
    allowed_directories: list[str] = Field(default_factory=lambda: [
        "/testbed",  # For SWE-bench (repository code)
        "/tmp/agent"  # For temporary files
    ])
    max_execution_time_seconds: int = 30  # Timeout to prevent infinite loops
    max_memory_mb: int = 512  # Memory limit to prevent resource exhaustion


class SandboxResult(BaseModel):
    """
    Result from executing code in the sandbox.
    
    Attributes:
        output: What the code printed to stdout
        error: Exception or error message (if any)
        final_answer: Value passed to final_answer() call (if any)
        timed_out: Did execution exceed time limit?
        truncated: Was output truncated (too large)?
    """
    output: str = ""
    error: str | None = None
    final_answer: str | None = None
    timed_out: bool = False
    truncated: bool = False


def _allowed_import(name: str, config: SandboxConfig) -> bool:
    """
    Check if an import matches the allowlist.
    
    EXAMPLES:
    - name="math", item="math" → True (exact match)
    - name="math.sqrt", item="math.*" → True (wildcard match)
    - name="os", config.authorized_imports=["math", "json"] → False (denied)
    """
    return any(name == item or item.endswith(".*") and name.startswith(item[:-2] + ".") for item in config.authorized_imports)


def _worker(code: str, config_data: dict[str, Any], tool_names: list[str], connection: Any) -> None:
    """Execute untrusted code in the restricted child process."""
    config = SandboxConfig.model_validate(config_data)
    if config.max_memory_mb:
        resource.setrlimit(resource.RLIMIT_AS, (config.max_memory_mb * 1024 * 1024,) * 2)
    original_import = builtins.__import__
    original_open = builtins.open
    allowed = tuple(Path(path).resolve() for path in config.allowed_directories)

    def restricted_import(name: str, globals: Any = None, locals: Any = None, fromlist: tuple[str, ...] = (), level: int = 0) -> Any:
        """Enforce the configured import allowlist."""
        if level or not _allowed_import(name, config):
            raise ImportError(f"Import blocked by sandbox: {name}")
        return original_import(name, globals, locals, fromlist, level)

    def safe_path(value: Any) -> Path:
        """Resolve a path and reject locations outside allowed directories."""
        path = Path(value).expanduser().resolve()
        if not any(path == root or root in path.parents for root in allowed):
            raise PermissionError(f"Path blocked by sandbox: {path}")
        return path

    def restricted_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        """Open a file only after applying sandbox path restrictions."""
        return original_open(safe_path(file), mode, *args, **kwargs)

    def call_tool(tool_name: str, *args: Any, **kwargs: Any) -> Any:
        """Proxy a sandbox tool call to the parent MCP bridge."""
        connection.send({"type": "tool", "name": tool_name, "args": args, "kwargs": kwargs})
        response = connection.recv()
        if response.get("error"):
            raise RuntimeError(response["error"])
        result = response.get("result")
        if isinstance(result, list) and all(isinstance(item, dict) and item.get("type") == "text" for item in result):
            return "\n".join(str(item.get("text", "")) for item in result)
        return result

    def final_answer(answer: Any) -> None:
        """Signal the completed answer to the parent agent loop."""
        connection.send({"type": "final", "answer": str(answer)})

    def make_tool(name: str) -> Callable[..., Any]:
        """Create a callable proxy for one dynamically discovered MCP tool."""
        return lambda *args, **kwargs: call_tool(name, *args, **kwargs)

    safe_builtins = {name: getattr(builtins, name) for name in (
        "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float", "format", "hasattr",
        "int", "isinstance", "len", "list", "map", "max", "min", "print", "range", "repr", "reversed",
        "round", "set", "sorted", "str", "sum", "tuple", "type", "zip", "Exception", "ValueError",
        "RuntimeError", "True", "False", "None"
    ) if hasattr(builtins, name)}
    safe_builtins.update({"__import__": restricted_import, "open": restricted_open})
    namespace = {"__builtins__": safe_builtins, "final_answer": final_answer}
    namespace.update({name: make_tool(name) for name in tool_names})
    try:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(compile(code, "<sandbox>", "exec"), namespace, namespace)
        connection.send({"type": "done", "output": output.getvalue()})
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException:
        connection.send({"type": "error", "error": traceback.format_exc()})


class Sandbox:
    def __init__(self, config: SandboxConfig | None = None, tools: dict[str, Callable[..., Any]] | None = None):
        """Create a sandbox with security settings and optional MCP tool proxies."""
        self.config = config or SandboxConfig()
        self.tools = tools or {}

    def execute(self, code: str) -> SandboxResult:
        """Execute one code block and return output, errors, timeout, and answer state."""
        if not code.strip():
            return SandboxResult(error="No valid code block was found in the model response")
        parent, child = multiprocessing.Pipe()
        context = multiprocessing.get_context("fork")
        process = context.Process(target=_worker, args=(code, self.config.model_dump(), list(self.tools), child), daemon=True)
        process.start()
        child.close()
        result = SandboxResult()
        deadline = time.monotonic() + self.config.max_execution_time_seconds
        try:
            while (process.is_alive() or parent.poll()) and time.monotonic() < deadline:
                if not parent.poll(0.05):
                    continue
                try:
                    message = parent.recv()
                except EOFError:
                    if process.exitcode:
                        result.error = result.error or f"Sandbox worker exited with code {process.exitcode}"
                    break
                if message["type"] == "tool":
                    try:
                        result_value = self.tools[message["name"]](*message["args"], **message["kwargs"])
                        parent.send({"result": result_value})
                    except Exception as error:
                        parent.send({"error": str(error)})
                elif message["type"] == "final":
                    result.final_answer = message["answer"]
                elif message["type"] == "error":
                    result.error = message["error"]
                elif message["type"] == "done":
                    result.output = message.get("output", "")
        finally:
            process.join(max(0, deadline - time.monotonic()))
            if process.is_alive():
                process.kill()
                result.timed_out = True
                result.error = "Sandbox execution timed out; output may be partial"
            parent.close()
        return result


def _load_config(path: str | None) -> SandboxConfig:
    """Load a JSON sandbox configuration or return the defaults."""
    if not path:
        return SandboxConfig()
    with open(path, encoding="utf-8") as stream:
        return SandboxConfig.model_validate(json.load(stream))


def main() -> None:
    """Run the interactive sandbox CLI with optional MCP connectivity."""
    parser = argparse.ArgumentParser()
    parser.add_argument("config", nargs="?")
    parser.add_argument("--mcp-stdio")
    parser.add_argument("--mcp-server")
    args = parser.parse_args()
    client = None
    if args.mcp_stdio:
        client = MCPClient(args.mcp_stdio)
    elif args.mcp_server:
        client = MCPHTTPClient(args.mcp_server)
    tools = {}
    if client:
        schemas = client.tools()
        tools = {schema["name"]: (lambda *values, _name=schema["name"], **named: client.call(_name, dict(named))) for schema in schemas}
        print(tool_manual(schemas), file=sys.stderr)
    sandbox = Sandbox(_load_config(args.config), tools)
    for line in sys.stdin:
        code = line.rstrip("\n")
        if code.strip().lower() in {"exit", "quit"}:
            break
        print(sandbox.execute(code).model_dump_json(), flush=True)
    if client:
        client.close()


if __name__ == "__main__":
    main()