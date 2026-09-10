# Sandbox Message Protocol

Agent Smith runs untrusted model-generated Python in a restricted child process and communicates with it over a multiprocessing pipe. The sandbox does not use JSON-RPC; it uses a lightweight Python-dictionary message protocol.

## Message Transport

The parent process creates a pipe with `multiprocessing.Pipe()`:

```python
parent, child = multiprocessing.Pipe()
```

Then the worker process receives the `child` endpoint as an argument:

```python
process = context.Process(target=_worker, args=(code, config, tool_names, child), daemon=True)
```

The worker sends messages to the parent by calling `connection.send(...)`, and the parent reads them with `parent.recv()`.

This is a simple in-process IPC mechanism, not a network protocol.

## Message Types

Each message is a Python dictionary with a required `type` field.

### 1. Tool Request

The sandboxed child asks the parent to execute a tool on its behalf.

```python
{
  "type": "tool",
  "name": "read_file",
  "args": ["/testbed/file.py"],
  "kwargs": {"start_line": 1, "end_line": 20}
}
```

Fields:
- `type`: always `"tool"`
- `name`: tool identifier, e.g. `read_file`, `edit_file`, `run_tests`
- `args`: positional arguments for the tool call
- `kwargs`: keyword arguments for the tool call

The parent handles this in `Sandbox.execute()`:

```python
if message["type"] == "tool":
    result_value = self.tools[message["name"]](*message["args"], **message["kwargs"])
    parent.send({"result": result_value})
```

### 2. Tool Result Response

The parent replies to a tool request with either a successful result or an error.

Success:

```python
{
  "result": "contents of file"
}
```

Error:

```python
{
  "error": "file not found"
}
```

The child checks for this in `_worker`:

```python
response = connection.recv()
if response.get("error"):
    raise RuntimeError(response["error"])
```

### 3. Final Answer

When sandboxed code calls `final_answer(...)`, the child reports the final value back to the parent.

```python
{
  "type": "final",
  "answer": "42"
}
```

The parent stores it:

```python
elif message["type"] == "final":
    result.final_answer = message["answer"]
```

### 4. Error Event

If the sandboxed code crashes or raises an exception, the child sends a traceback.

```python
{
  "type": "error",
  "error": "Traceback (most recent call last):\n  File ..."
}
```

The parent stores it:

```python
elif message["type"] == "error":
    result.error = message["error"]
```

### 5. Done Event

When the worker finishes successfully without a final answer, it sends:

```python
{
  "type": "done",
  "output": ""
}
```

The parent records it as output:

```python
elif message["type"] == "done":
    result.output = message.get("output", "")
```

## Why This Is Enough

This protocol is intentionally simple:
- `type` tells the receiver how to interpret the payload
- tool requests are synchronous: the child waits for one reply
- every message is a Python object, so no JSON serializer is required

The sandbox is designed to keep the model code isolated, while still allowing it to request safe actions through the parent-controlled tool bridge.

## Example Full Flow

A sandboxed function may do this:

```python
print("hello")
final_answer("done")
```

The actual IPC may look like this:

1. Child executes code.
2. Child sends:

```python
{"type": "final", "answer": "done"}
```

3. Parent receives it and sets:

```python
result.final_answer = "done"
```

If the code tries to call a tool:

```python
read_file("/testbed/example.py")
```

then the child sends:

```python
{
  "type": "tool",
  "name": "read_file",
  "args": ["/testbed/example.py"],
  "kwargs": {}
}
```

and waits for a reply.

## Security Note

The child is not allowed to directly access the real parent tools or the host filesystem. Tool calls are proxied through the parent process, and file access is restricted by the sandbox import and path rules in `agent_smith/sandbox.py`.
