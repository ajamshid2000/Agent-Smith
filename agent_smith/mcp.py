import json
import subprocess
import urllib.request
from typing import Any


class MCPClient:
    def __init__(self, command: str):
        """Start an MCP server subprocess using the stdio transport."""
        self.process = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.request_id = 0
        self.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "agent-smith", "version": "0.1.0"}})
        self.notify("notifications/initialized")

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        """Send a JSON-RPC notification that does not require a response."""
        assert self.process.stdin
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method, "params": params or {}}) + "\n")
        self.process.stdin.flush()

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a JSON-RPC request and return its result object."""
        self.request_id += 1
        request = {"jsonrpc": "2.0", "id": self.request_id, "method": method, "params": params or {}}
        assert self.process.stdin and self.process.stdout
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError("MCP server closed its output")
        response = json.loads(line)
        if "error" in response:
            raise RuntimeError(str(response["error"]))
        return response.get("result", {})

    def tools(self) -> list[dict[str, Any]]:
        """Return the tools advertised by the connected MCP server."""
        return self.request("tools/list").get("tools", [])

    def call(self, name: str, arguments: dict[str, Any]) -> Any:
        """Call one MCP tool with its structured arguments."""
        return self.request("tools/call", {"name": name, "arguments": arguments}).get("content", [])

    def close(self) -> None:
        """Terminate the stdio MCP server process."""
        self.process.terminate()


class MCPHTTPClient:
    def __init__(self, url: str):
        """Create an MCP client for a streamable HTTP endpoint."""
        self.url = url
        self.request_id = 0
        self.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "agent-smith", "version": "0.1.0"}})

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a JSON-RPC request over HTTP and return its result object."""
        self.request_id += 1
        payload = json.dumps({"jsonrpc": "2.0", "id": self.request_id, "method": method, "params": params or {}}).encode()
        request = urllib.request.Request(self.url, payload, {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.load(response)
        if "error" in result:
            raise RuntimeError(str(result["error"]))
        return result.get("result", {})

    def tools(self) -> list[dict[str, Any]]:
        """Return the tools advertised by the HTTP MCP server."""
        return self.request("tools/list").get("tools", [])

    def call(self, name: str, arguments: dict[str, Any]) -> Any:
        """Call one HTTP MCP tool with its structured arguments."""
        return self.request("tools/call", {"name": name, "arguments": arguments}).get("content", [])

    def close(self) -> None:
        """Close the HTTP client; urllib requires no persistent cleanup."""
        pass


def tool_manual(tools: list[dict[str, Any]]) -> str:
    """Render MCP tool schemas as instructions for the agent system prompt."""
    lines = ["Available MCP tools are callable Python functions:"]
    for tool in tools:
        schema = tool.get("inputSchema", {})
        lines.append(f"- {tool.get('name')}: {tool.get('description', '')}; parameters: {json.dumps(schema)}")
    return "\n".join(lines)