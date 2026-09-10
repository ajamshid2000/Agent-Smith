# MCP JSON-RPC Messages

Agent Smith uses JSON-RPC 2.0 messages to communicate between the MCP client and MCP tool servers.

## Message Transport

For stdio transport, `MCPClient` starts the server as a subprocess. JSON messages are written as newline-delimited text:

```text
client -> server stdin
client <- server stdout
```

The client builds a Python dictionary, converts it to JSON with `json.dumps()`, and writes one line. The server reads one line and converts it back to a Python dictionary with `json.loads()`.

HTTP transport uses the same JSON-RPC message structures, but sends them in HTTP requests.

## Initialize Request

Sent when the client starts:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {
      "name": "agent-smith",
      "version": "0.1.0"
    }
  }
}
```

The server responds with its protocol information and capabilities.

## Initialized Notification

After initialization, the client sends a notification:

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/initialized",
  "params": {}
}
```

This is not a request because it has no `id` and does not require a response.

## List Tools Request

The client asks the server which tools are available:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}
```

The server responds with tool metadata, not function implementations:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {
        "name": "run_tests",
        "description": "Execute the MBPP candidate against its tests.",
        "inputSchema": {
          "type": "object",
          "properties": {
            "code": {"type": "string"},
            "test_list": {
              "type": "array",
              "items": {"type": "string"}
            }
          },
          "required": ["code", "test_list"]
        }
      }
    ]
  }
}
```

`TOOLS` in `mcp_tools_mbpp.py` and `mcp_tools_swebench.py` contains this metadata. The actual Python functions are defined separately in those server files.

## Call Tool Request

The client calls a tool using its name and arguments:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "TOOL_NAME",
    "arguments": {}
  }
}
```

### MBPP Example

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "run_tests",
    "arguments": {
      "code": "def add(a, b): return a + b",
      "test_imports": [],
      "test_list": ["assert add(2, 3) == 5"]
    }
  }
}
```

The MBPP server extracts `arguments` and invokes:

```python
run_tests(**args)
```

### SWE-bench Examples

Read a file:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "read_file",
    "arguments": {
      "filepath": "models.py",
      "start_line": 1,
      "end_line": 40
    }
  }
}
```

Edit a file:

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "edit_file",
    "arguments": {
      "filepath": "models.py",
      "old_str": "old code",
      "new_str": "new code"
    }
  }
}
```

Run the evaluation tests:

```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "tools/call",
  "params": {
    "name": "run_tests",
    "arguments": {}
  }
}
```

## Responses

A successful response contains the same request `id` and a `result`:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "exit_code=0\nstdout=\nstderr="
      }
    ]
  }
}
```

An error response contains an `error` object instead:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "error": {
    "message": "Tool failed"
  }
}
```

## What to Store

Store representative, sanitized messages as documentation or test fixtures. Useful fixtures include:

```text
tests/fixtures/initialize_request.json
tests/fixtures/tools_list_request.json
tests/fixtures/mbpp_tools_call_request.json
tests/fixtures/swebench_tools_call_request.json
```

Do not store every runtime request. Requests may contain generated code, repository contents, large arguments, or sensitive data. Use placeholders in examples and redact sensitive values in temporary logs.

## Project Locations

- `agent_smith/mcp.py`: client-side JSON-RPC construction and transport.
- `mcp_tools_mbpp.py`: MBPP MCP server and `run_tests` implementation.
- `mcp_tools_swebench.py`: SWE-bench MCP server and repository tool implementations.
