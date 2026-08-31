# Agent Smith: Key Algorithms & Concepts Explained

## 1. The Thought → Code → Observation Loop

### Algorithm
```
START with task description
  ↓
LOOP (up to max_iterations times)
  ├─ SEND task context + observation to LLM
  ├─ LLM THINKS and generates Python code
  ├─ EXTRACT code from LLM response (handles multiple formats)
  ├─ EXECUTE code in sandbox
  ├─ If code calls final_answer():
  │   └─ RETURN solution and EXIT
  └─ Else:
      ├─ OBSERVE execution result (errors, output)
      └─ UPDATE observation with result + error
        └─ BACK to SEND with updated observation

RETURN result (success or failure)
```

### Why This Works
- **LLM learns from feedback**: Each iteration, LLM sees what went wrong
- **Iterative improvement**: Like debugging by hand
- **Self-correcting**: If tests fail, LLM tries different approach
- **Bounded**: Token/iteration limits prevent infinite loops

### Example Observation Evolution

**Iteration 1 - Initial Task:**
```
Task: Write function to compute factorial
Function signature: def factorial(n):
Tests: [assert factorial(5) == 120, ...]

Write the implementation. Call run_tests(...). If tests pass, call final_answer(...).
```

**Iteration 2 - With Feedback:**
```
Task context:
Write function to compute factorial
Function signature: def factorial(n):
Tests: [assert factorial(5) == 120, ...]

Previous step 1 result:
Extraction: python code block
Observation:
exit_code=1
stderr=RecursionError: maximum recursion depth exceeded

Note: Your recursive implementation exceeded recursion limit. 
Try an iterative approach instead.
```

**Iteration 3 - LLM Adapts:**
```
Previous step 2 result:
Extraction: python code block
Observation:
exit_code=0
stdout=
stderr=

Great! All tests passed!
```

The LLM now understands the problem evolved from "implement factorial" → "recursive is too slow" → "use iteration".

---

## 2. Sandbox Security Model

### Threat Model: What We're Protecting Against

**Threat 1: Unintended Resource Consumption**
- Problem: Code with infinite loop crashes agent
- Solution: Process timeout (30 seconds)

**Threat 2: System Access**
- Problem: Code runs `os.system("rm -rf /")` 
- Solution: Import whitelist blocks `os` module

**Threat 3: Memory Bombs**
- Problem: Code allocates 1TB of RAM
- Solution: Memory limit (512 MB)

**Threat 4: File System Escape**
- Problem: Code reads `/etc/passwd` via path traversal
- Solution: Path resolution + allowed directories whitelist

**Threat 5: Network Exfiltration**
- Problem: Code sends data to malicious server
- Solution: No network module imports allowed

### Architecture

```
┌─────────────────────────────────────────┐
│         Parent Process (Agent)          │
│  ┌─────────────────────────────────────┐│
│  │       create sandbox instance       ││
│  │       store tools, config           ││
│  └─────────────────────────────────────┘│
│                  │                      │
│      ┌───────────┼───────────┐          │
│      │ fork()    │ create    │          │
│      │           │ pipe      │          │
│      ▼           ▼           ▼          │
│   Process    Pipe (fds)   (parent end)  │
│   Handle                                │
└──────────────────────┬──────────────────┘
                       │
                ┌──────▼──────────┐
                │ Child Process   │
                │ (untrusted code)│
                │                 │
                │ setrlimit()     │
                │ → 512MB memory  │
                │ → 30s timeout   │
                │                 │
                │ replace imports │
                │ → whitelist     │
                │                 │
                │ replace open()  │
                │ → path checks   │
                │                 │
                │ execute code    │
                │                 │
                │ pipe responses  │
                │ back to parent  │
                └─────────────────┘
```

### Execution Model

**Parent Responsibilities:**
1. Monitor child process with timeout
2. Intercept tool calls via pipe
3. Route tool calls to MCP server
4. Return tool results to child
5. Kill child if timeout exceeded

**Child Restrictions:**
1. Memory: setrlimit(RLIMIT_AS, 512MB)
2. Time: Must send/exit within 30s
3. Imports: Only whitelisted modules
4. Files: Only /testbed and /tmp/agent
5. Network: No socket, urllib, requests allowed

### Escape Attempts Prevented

**Attempt 1: Import os and run command**
```python
import os
os.system("escape")
# Result: ImportError: Import blocked by sandbox: os
```

**Attempt 2: Use open() to read /etc/passwd**
```python
with open("/etc/passwd") as f:
    data = f.read()
# Result: PermissionError: Path blocked by sandbox: /etc/passwd
```

**Attempt 3: Infinite loop**
```python
while True:
    pass
# Result: Process killed after 30 seconds
# "Sandbox execution timed out"
```

**Attempt 4: Allocate 10GB**
```python
big_list = [0] * (10 * 1024 * 1024 * 1024)
# Result: MemoryError after ~512MB
```

**Attempt 5: Use eval() on untrusted code**
```python
eval("import os; os.system('escape')")
# Result: NameError: name 'eval' is not defined
# eval removed from safe_builtins
```

---

## 3. API Key Rotation Strategy

### Why Multiple Keys?
1. Different OpenAI organizations/accounts
2. One key might be rate-limited
3. Provider might blacklist key temporarily
4. Load balancing across accounts

### Algorithm

```python
class OpenAIProvider:
    def __init__(self, api_keys):
        self.api_keys = api_keys  # e.g., ["key1", "key2", "key3"]
        self._key_index = 0
    
    def complete(self, prompt):
        retries = 0
        started = time.time()
        
        while retries <= len(self.api_keys):  # Try each key once
            key = self.api_keys[self._key_index % len(self.api_keys)]
            self._key_index += 1  # Round-robin to next key
            
            try:
                response = call_api(key, prompt)
                # SUCCESS: Return result with retry count
                return Completion(
                    text=response.text,
                    input_tokens=response.tokens_in,
                    output_tokens=response.tokens_out,
                    request_time_ms=elapsed_ms,
                    retries=retries  # Tells us how many keys we tried
                )
            except HTTPError:
                # This key failed, try next one
                retries += 1
                if retries > len(self.api_keys):
                    raise RuntimeError(f"All {len(self.api_keys)} keys failed")
```

### Key Priority

**Order of key discovery:**
1. Explicit `api_keys` parameter (highest priority)
2. `AGENT_SMITH_API_KEYS` env var (comma-separated)
3. Provider-specific vars (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.)

**Example .env:**
```
# Highest priority: explicit list
AGENT_SMITH_API_KEYS=key1,key2,key3

# Fallback: provider-specific
OPENAI_API_KEY=key4
ANTHROPIC_API_KEY=key5
```

### Benefits
- **Reliability**: If one key is rate-limited, try next
- **Observability**: `retries` field shows how many keys needed
- **Flexibility**: Works with any compatible provider
- **Security**: No hardcoding of credentials

---

## 4. MCP (Model Context Protocol) Tool System

### Architecture

```
Agent Loop
    ↓
Generates code that calls: run_tests(code="...")
    ↓
Sandbox intercepts call
    ↓
Sends JSON-RPC message through pipe to MCP server
    ↓
MCP Server (separate process)
    ├─ Receives: {"method": "tools/call", "name": "run_tests", "arguments": {...}}
    ├─ Executes: run_tests(**arguments)
    ├─ Sends back: {"result": "exit_code=0..."}
    ↓
Sandbox receives result
    ↓
Passes to untrusted code as function return value
```

### MCP Protocol (JSON-RPC 2.0)

**Discovery Phase:**
```
Agent → MCP: {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
MCP → Agent: {"result": {"tools": [{"name": "run_tests", "description": "...", "inputSchema": {...}}]}}
```

**Tool Call:**
```
Agent → MCP: {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
        "name": "run_tests",
        "arguments": {
            "code": "def f(): pass",
            "test_list": ["assert True"]
        }
    }
}

MCP → Agent: {
    "result": {
        "content": [
            {"type": "text", "text": "exit_code=0\nstdout=\nstderr="}
        ]
    }
}
```

### Why MCP?

1. **Separation of Concerns**
   - Agent focuses on reasoning
   - Tools focus on execution
   - Easy to add new tools

2. **Extensibility**
   - Add new tools without modifying agent
   - MBPP has 1 tool (run_tests)
   - SWE-bench has 9 tools (read_file, edit_file, etc.)

3. **Process Isolation**
   - Tools run in separate process
   - Tool crash doesn't crash agent
   - Tools can be slow without blocking agent

4. **Multiple Transport Options**
   - Stdio (default)
   - HTTP (MCPHTTPClient)
   - Custom implementations

---

## 5. Code Extraction: Handling Multiple LLM Formats

### Challenge
Different LLMs output code in different formats:
- OpenAI: Markdown code blocks
- Claude: XML tool calls
- Llama: JSON tool calls
- ReAct models: Action format

### Solution: Sequential Pattern Matching

```python
def extract_code(response):
    # Try Format 1: Markdown
    blocks = re.findall(r"```python\n(.*?)```", response, re.S)
    if blocks:
        return blocks[0].strip(), "python code block"
    
    # Try Format 2: XML
    xml = re.search(r"<invoke name='(\w+)'>(.*?)</invoke>", response)
    if xml:
        args = parse_xml_parameters(xml.group(2))
        return convert_to_python(xml.group(1), args), "XML tool call"
    
    # Try Format 3: JSON
    json_call = re.search(r"<tool_call>(\{.*?\})</tool_call>", response)
    if json_call:
        payload = json.loads(json_call.group(1))
        return convert_to_python(payload['name'], payload['arguments']), "JSON tool call"
    
    # Try Format 4: ReAct
    react = re.search(r"Action: (\w+)\nAction Input: (\{.*?\})", response)
    if react:
        args = json.loads(react.group(2))
        return convert_to_python(react.group(1), args), "ReAct format"
    
    # Nothing found
    return "", "No valid code found"
```

### Order Matters

**Why try markdown first?**
- Most common for LLMs
- Fastest to match (most specific)
- Simplest format to handle

**Why try XML second?**
- Claude prefers XML
- More structured than markdown
- Medium specificity

**Why ReAct last?**
- Least common
- Most ambiguous (many models could match)

### Example Conversions

**Input: XML Tool Call**
```xml
<invoke name="run_tests">
  <parameter name="code">def f(): pass</parameter>
  <parameter name="test_list">["assert True"]</parameter>
</invoke>
```

**Output: Python Code**
```python
result = run_tests(code="def f(): pass", test_list=["assert True"])
```

**Input: ReAct Format**
```
Action: run_tests
Action Input: {"code": "def f(): pass", "test_list": ["assert True"]}
```

**Output: Python Code**
```python
result = run_tests(code="def f(): pass", test_list=["assert True"])
```

---

## 6. Token Limit Management

### Why Token Limits?

1. **Cost Control**: Tokens = dollars spent
2. **Latency**: More tokens = slower responses
3. **Context Window**: Models have max token limit
4. **Safety**: Prevent runaway prompts

### Algorithm

```python
class AgentLoop:
    def __init__(self, max_input_tokens=6000, max_output_tokens=1500):
        self.max_input = max_input_tokens
        self.max_output = max_output_tokens
    
    def run(self):
        total_input = 0
        total_output = 0
        
        for iteration in range(1, max_iterations + 1):
            # Check limits before API call
            if total_input >= self.max_input or total_output >= self.max_output:
                error = "Token limit reached"
                break
            
            # Get LLM response
            completion = self.provider.complete(
                system_prompt,
                observation,
                min(self.max_output - total_output, 1500)  # Cap at 1500 per turn
            )
            
            # Accumulate
            total_input += completion.input_tokens
            total_output += completion.output_tokens
            
            # Check again after API call
            if total_input >= self.max_input:
                # This might be the last iteration
                pass
```

### Example Budget Allocation

**MBPP (Simple):**
```
max_input_tokens: 6000
max_output_tokens: 1500
max_iterations: 10

Budget per iteration: 6000/10 = 600 input tokens, 150 output tokens
Typical use: 2-3 iterations = 200-300 tokens total
Remaining: Can still iterate 15-20 times before hitting limit
```

**SWE-bench (Complex):**
```
max_input_tokens: 300000 (!)
max_output_tokens: 10000
max_iterations: 30

Budget per iteration: 300000/30 = 10000 input tokens, 333 output tokens
Typical use: 10-20 iterations needed
Remaining: Plenty of room for exploration
```

### Cost Calculation

```python
# From solution.json
input_tokens = 1100
output_tokens = 554

# OpenAI gpt-4-turbo pricing:
input_price = 0.01 / 1000  # $0.01 per 1K tokens
output_price = 0.03 / 1000  # $0.03 per 1K tokens

cost = (input_tokens * input_price) + (output_tokens * output_price)
# = (1100 * 0.00001) + (554 * 0.00003)
# = $0.011 + $0.017
# = $0.028 (less than 3 cents!)
```

---

## 7. Path Traversal Prevention in Sandbox

### Vulnerability: Path Traversal

**Without Checks:**
```python
# Attacker provides path
user_path = "/testbed/../../../etc/passwd"
content = open(user_path).read()  # ESCAPES TESTBED!
```

**Why It Works:**
- `..` means "go up one directory"
- `/testbed/../../../` = `/../../` = `/`
- Now you can read any file on system

### Solution: Path Resolution

```python
def safe_path(value):
    # Step 1: Resolve ../, ~, symlinks, etc.
    path = Path(value).expanduser().resolve()
    # /testbed/../../../etc/passwd → /etc/passwd (RESOLVED)
    
    # Step 2: Check if result is under allowed directory
    allowed_dirs = [Path("/testbed"), Path("/tmp/agent")]
    
    if not any(
        path == allowed_dir or allowed_dir in path.parents
        for allowed_dir in allowed_dirs
    ):
        raise PermissionError(f"Path blocked: {path}")
    
    return path

# Test cases:
safe_path("/testbed/models.py")  # ✓ OK
safe_path("/testbed/subdir/file.py")  # ✓ OK
safe_path("/testbed/../../../etc/passwd")  # ✗ BLOCKED
safe_path("~/file.py")  # ✗ BLOCKED (~ expands outside testbed)
safe_path("/etc/passwd")  # ✗ BLOCKED
```

### Why `.resolve()` is Critical

```python
# Without .resolve()
path = Path("/testbed/../../../etc/passwd")
# path.parents = [/testbed/.., /testbed, /, /etc, /]
# Any might match allowed directory!

# With .resolve()
path = Path("/testbed/../../../etc/passwd").resolve()
# path = /etc/passwd
# path.parents = [/, /etc]
# Doesn't match allowed directories - BLOCKED!
```

---

## 8. Timeout Detection and Enforcement

### Challenge
How do we detect if code is stuck in infinite loop?

### Solution: Multi-Layer Timeout

```python
class Sandbox:
    def execute(self, code):
        # Layer 1: Process timeout
        deadline = time.monotonic() + 30  # 30-second deadline
        
        # Layer 2: Resource limit (enforced by kernel)
        setrlimit(RLIMIT_AS, (512MB,) * 2)  # Memory limit
        
        # Layer 3: Polling loop in parent
        while process.is_alive() and time.monotonic() < deadline:
            if parent.poll(timeout=0.05):  # Check every 50ms
                # Parent received message from child
                process_message(parent.recv())
            
            if time.monotonic() > deadline:
                # TIMEOUT: Force kill
                process.kill()
                return SandboxResult(error="Timed out", timed_out=True)
```

### Why Multi-Layer?

**Layer 1 (Deadline):** Parent monitoring
- Detects when child takes too long
- Parent can intervene (e.g., kill process)
- Can't be bypassed from child

**Layer 2 (Resource Limit):** OS enforces
- Kernel kills process if memory exceeded
- Child can't disable setrlimit
- Hardest for attacker to overcome

**Layer 3 (Polling):** Responsive parent
- Check every 50ms (not blocked on child)
- Can receive tool call responses
- Parent always responsive

### Example Timeout Scenario

```
T=0s:  Child starts executing code (infinite loop)
T=0.05s: Parent polls, checks deadline, child alive
T=0.10s: Parent polls, checks deadline, child alive
...
T=29.95s: Parent polls, checks deadline, child alive
T=30.00s: Deadline reached!
         Parent calls: process.kill()
         Sets: timed_out = True
         Returns: "Sandbox execution timed out"
```

---

This completes the detailed explanation of all major algorithms and concepts in Agent Smith!
