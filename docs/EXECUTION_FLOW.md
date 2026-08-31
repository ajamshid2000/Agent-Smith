# Agent Smith: Detailed Execution Flow Guide

## Complete Example: Running MBPP Agent Step-by-Step

This guide walks through **exactly** what happens when you run:
```bash
uv run python -m agent_mbpp --task-file task.json --output solution.json
```

---

## Step 0: Before Execution

### File: `task.json` (Input)
```json
{
  "task_id": 42,
  "task_definition": "Write a function to compute the factorial of a given number.",
  "function_definition": "def factorial(n):",
  "test_imports": ["math"],
  "test_list": [
    "assert factorial(5) == 120",
    "assert factorial(0) == 1",
    "assert factorial(1) == 1"
  ]
}
```

### File: `.env` (API Key)
```
OPENAI_API_KEY=sk-proj-abc123...
```

---

## Step 1: Parse Command Line & Load Environment

**File: `agent_mbpp.py`**

```python
# 1.1: Parse arguments
args = parser.parse_args()
# Result: args.task_file = "task.json", args.output = "solution.json", 
#         args.model_name = "gpt-5.4-mini", args.provider_url = "https://api.openai.com/v1"

# 1.2: Load .env file
load_env_file(args.env_file)  # "OPENAI_API_KEY" now in os.environ

# 1.3: Load and validate MBPP task
task_path = Path("task.json")
task_json = task_path.read_text()
task = MBPPTaskInput.model_validate_json(task_json)
# Result: task is now a validated Pydantic model with all required fields
```

**Why this matters:**
- Validates input before proceeding (fail fast)
- Loads credentials securely from .env
- Ensures all fields are present and correct type

---

## Step 2: Start MCP Tool Server

**File: `agent_mbpp.py` → Spawns subprocess**

```python
# 2.1: Start MCP server as subprocess
client = MCPClient(f"{sys.executable} mcp_tools_mbpp.py")
# This runs: python mcp_tools_mbpp.py
# The subprocess starts a JSON-RPC server on stdin/stdout

# 2.2: Get available tools from server
schemas = client.tools()
# Sends JSON-RPC: {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
# Receives: [{"name": "run_tests", "description": "...", "inputSchema": {...}}]

# 2.3: Create tool functions for sandbox
tools = {
    "run_tests": lambda **kwargs: client.call("run_tests", kwargs)
}
# These are now available to the sandbox as callable functions
```

**MCP Server Process (mcp_tools_mbpp.py):**
```python
# Reads JSON-RPC messages from stdin
for line in sys.stdin:
    request = json.loads(line)
    
    if request["method"] == "tools/list":
        # Return available tools
        result = {"tools": TOOLS}
    
    elif request["method"] == "tools/call":
        # Execute the tool
        args = request["params"]["arguments"]
        result = run_tests(**args)  # Actually run the tests
    
    # Send response
    print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}))
```

**Why separate process?**
- Tools might be expensive/slow (subprocess call, test execution)
- Keeps sandbox lightweight
- Tools can be upgraded without restarting agent

---

## Step 3: Initialize Provider, Sandbox, and Loop

**File: `agent_mbpp.py`**

```python
# 3.1: Create LLM provider
provider = OpenAIProvider(
    model_name="gpt-5.4-mini",
    provider_url="https://api.openai.com/v1"
)
# Provider loads API key from environment
# provider.api_keys = ["sk-proj-abc123..."]

# 3.2: Create sandbox with config
sandbox = Sandbox(
    SandboxConfig(max_execution_time_seconds=30),
    tools  # Pass tool functions to sandbox
)

# 3.3: Create agent loop
loop = AgentLoop(
    provider=provider,
    sandbox=sandbox,
    benchmark="mbpp",
    max_iterations=10,  # Stop after 10 attempts
    max_input_tokens=6000,  # Stop if prompt gets too long
    max_output_tokens=1500  # Stop if responses get too long
)
```

**What's ready now:**
- LLM connection configured
- Sandbox with security settings and tools ready
- Loop with iteration limits configured

---

## Step 4: Build Task Prompt

**File: `agent_mbpp.py`**

```python
prompt = f"""Task: {task.task_definition}
Function signature: {task.function_definition}
Tests: {task.test_list}

Write the implementation. In the same Python code block, call 
run_tests(code=<your complete function code>, test_imports={task.test_imports!r}, test_list={task.test_list!r}). 
If the tests pass, immediately call final_answer(<your complete function code as a string>).
Never return only a function definition; the final line must call final_answer."""
```

**Result:**
```
Task: Write a function to compute the factorial of a given number.
Function signature: def factorial(n):
Tests: ['assert factorial(5) == 120', 'assert factorial(0) == 1', 'assert factorial(1) == 1']

Write the implementation. In the same Python code block, call 
run_tests(code=<your complete function code>, test_imports=['math'], test_list=['assert factorial(5) == 120', ...]). 
If the tests pass, immediately call final_answer(<your complete function code as a string>).
```

---

## Step 5: Run Agent Loop

**File: `agent_smith/loop.py` → `AgentLoop.run()`**

### Iteration 1: Initial Attempt

```python
# PREPARATION
system_prompt = f"""You are Agent Smith. Solve the coding task through a Thought -> Code -> Observation loop.
Available tools are Python functions described below:
- run_tests: Execute the MBPP candidate against its tests; parameters: code, test_imports, test_list
..."""

observation = prompt  # The task description from Step 4
iteration = 1

# STEP 1: THOUGHT (Send to LLM)
completion = provider.complete(
    system_prompt=system_prompt,
    user_prompt=observation,
    max_tokens=min(1500, 1500 - 0)  # First iteration, no tokens used yet
)
```

**LLM Request (HTTP POST to OpenAI):**
```json
{
  "model": "gpt-5.4-mini",
  "messages": [
    {
      "role": "system",
      "content": "You are Agent Smith. Solve the coding task..."
    },
    {
      "role": "user",
      "content": "Task: Write a function to compute the factorial..."
    }
  ],
  "max_completion_tokens": 1500
}
```

**LLM Response (example):**
```
I need to implement a factorial function. Let me write the code and test it:

```python
def factorial(n):
    if n == 0 or n == 1:
        return 1
    return n * factorial(n - 1)

run_tests(code="def factorial(n):\n    if n == 0 or n == 1:\n        return 1\n    return n * factorial(n - 1)", 
          test_imports=['math'], 
          test_list=['assert factorial(5) == 120', 'assert factorial(0) == 1', 'assert factorial(1) == 1'])
```

Let me check if it passes tests first.
```

**What Agent Smith Records:**
- `input_tokens`: 456 (size of system + user prompt)
- `output_tokens`: 234 (size of LLM response)
- `request_time_ms`: 2341 (how long API call took)
- `llm_output`: The exact response above

### STEP 2: CODE EXTRACTION

**File: `agent_smith/extract.py`**

```python
code, extraction = extract_code(completion.text)

# extract_code looks for patterns:
# 1. ```python ... ``` blocks
# 2. XML <invoke> tags
# 3. JSON <tool_call> tags
# 4. ReAct Action: format

# Found: Markdown code block
code = """def factorial(n):
    if n == 0 or n == 1:
        return 1
    return n * factorial(n - 1)

run_tests(code="def factorial(n):\n    if n == 0 or n == 1:\n        return 1\n    return n * factorial(n - 1)", 
          test_imports=['math'], 
          test_list=['assert factorial(5) == 120', 'assert factorial(0) == 1', 'assert factorial(1) == 1'])"""

extraction = "python code block"  # For logging
```

**What Agent Smith Records:**
- `sandbox_input`: The exact code that will be executed

### STEP 3: CODE EXECUTION (in Sandbox)

**File: `agent_smith/sandbox.py` → `Sandbox.execute(code)`**

```python
# 3.1: Validate code
if not code.strip():
    return SandboxResult(error="No valid code block was found...")

# 3.2: Fork child process
parent, child = multiprocessing.Pipe()
process = context.Process(target=_worker, args=(code, config, tools, child))
process.start()
child.close()

# 3.3: Parent waits for child to finish
result = SandboxResult()
deadline = time.monotonic() + 30  # 30-second timeout

while process.is_alive() or parent.poll():
    if not parent.poll(0.05):  # Check every 50ms
        continue
    
    message = parent.recv()  # Get message from child
```

**In Child Process (restricted execution):**

```python
# _worker function runs in child with restrictions:

# Replace dangerous functions
safe_builtins = {
    # Safe functions only: abs, all, any, bool, dict, ...
    # NO: open, __import__, eval, exec, ...
}
namespace = {
    "__builtins__": safe_builtins,
    "final_answer": final_answer_proxy,
    "run_tests": run_tests_proxy  # Tool proxy
}

# Execute the code
exec(compile(code, "<sandbox>", "exec"), namespace, namespace)

# Code defines factorial function
# Code calls run_tests(code=..., test_imports=..., test_list=...)
```

**run_tests_proxy Call in Child:**

```python
# Child can't actually run tests (restricted)
# So it proxies to parent

connection.send({
    "type": "tool",
    "name": "run_tests",
    "args": [],
    "kwargs": {
        "code": "def factorial(n): ...",
        "test_imports": ["math"],
        "test_list": ["assert factorial(5) == 120", ...]
    }
})

# Child waits for response
response = connection.recv()
# Parent handled this, got result from MCP server
result = response["result"]
```

**Parent Receives Tool Call:**

```python
# Parent intercepts tool call message
message = {"type": "tool", "name": "run_tests", "kwargs": {...}}

# Parent calls tool via MCP
result_value = tools["run_tests"](
    code="def factorial(n): ...",
    test_imports=["math"],
    test_list=[...]
)

# MCP server (mcp_tools_mbpp.py) runs tests
# Creates temporary file with code + tests
# Runs: python /tmp/xyz.py
# Returns: "exit_code=1\nstdout=\nstderr=..."

# Parent sends result back to child
parent.send({"result": "exit_code=1\nstdout=\nstderr=AssertionError: ..."})
```

**Explanation of exit_code=1:**
- Exit code 0 = all tests passed
- Exit code 1 = some tests failed (AssertionError)

**Back in Child Process:**

```python
# run_tests_proxy returns test result
result = "exit_code=1\nstdout=\nstderr=AssertionError: ..."

# Child prints or uses this result
print(result)  # If code had print statement

# Code didn't call final_answer() (tests failed)
# So child doesn't send "final" message
# Child continues executing or exits normally

connection.send({"type": "done", "output": ""})
```

**Back in Parent Process:**

```python
# Parent receives "done" message
# Child process exits normally
# Sandbox detects this and returns result

result = SandboxResult(
    output="",  # Nothing was printed
    error=None,  # No exception
    final_answer=None,  # final_answer() was not called
    timed_out=False
)
```

**What Agent Smith Records:**
- `sandbox_input`: The code that ran
- `sandbox_output`: "exit_code=1\nstdout=\nstderr=AssertionError: ..."
- Whether execution timed out

### STEP 4: CHECK FOR SOLUTION

```python
execution = sandbox.execute(code)

if execution.final_answer is not None:
    answer = execution.final_answer
    break  # Loop exits, solution found
else:
    # Tests failed, update observation with feedback
    sandbox_output = "exit_code=1\nstdout=\nstderr=AssertionError: ..."
    
    observation = f"""Task context:
Write a function to compute the factorial of a given number...
Function signature: def factorial(n):
Tests: ['assert factorial(5) == 120', ...]

Previous step 1 result:
Extraction: python code block
Observation:
exit_code=1
stdout=
stderr=AssertionError: expected 120, got 120
(or some actual error)"""
```

---

### Iteration 2: Learning from Failure

```python
iteration = 2

# Send previous attempt + error to LLM
observation = "Task context: ...\n\nPrevious step 1 result:\n..."

# LLM now sees what went wrong
# LLM tries to improve the code
completion = provider.complete(system_prompt, observation, 1500)

# LLM response (example):
# "The issue was... let me fix it:
# ```python
# def factorial(n):
#     if n < 0:
#         return None
#     if n == 0 or n == 1:
#         return 1
#     result = 1
#     for i in range(2, n + 1):
#         result *= i
#     return result
# 
# run_tests(code=..."

code, extraction = extract_code(completion.text)
execution = sandbox.execute(code)  # Run new code

# If tests pass, LLM will call final_answer()
if execution.final_answer is not None:
    answer = execution.final_answer
    break  # SUCCESS!
```

---

## Step 6: Record and Save Results

**File: `agent_mbpp.py`**

```python
# Agent loop returns SolutionOutput
solution = AgentLoop(...).run(
    task_id=str(task.task_id),
    task_prompt=prompt,
    manual=tool_manual(schemas)  # Tool descriptions
)

# solution contains:
{
    "task_id": "42",
    "benchmark": "mbpp",
    "success": true,
    "solution": "def factorial(n):\n    if n == 0 or n == 1:\n        return 1\n    result = 1\n    for i in range(2, n + 1):\n        result *= i\n    return result",
    "iterations": 2,
    "total_requests": 2,  # 2 API calls
    "total_input_tokens": 450 + 650,
    "total_output_tokens": 234 + 320,
    "total_time_seconds": 8.5,
    "steps": [
        {
            "step": 1,
            "input_tokens": 450,
            "output_tokens": 234,
            "request_time_ms": 2341,
            "api_url": "https://api.openai.com/v1",
            "model_name": "gpt-5.4-mini",
            "llm_output": "I need to implement... [full response]",
            "sandbox_input": "def factorial(n):\n    if n == 0 or n == 1:\n        return 1\n    return n * factorial(n - 1)\n\nrun_tests(...)",
            "sandbox_output": "exit_code=1\nstdout=\nstderr=...",
            "retries": 0
        },
        {
            "step": 2,
            "input_tokens": 650,
            "output_tokens": 320,
            "request_time_ms": 1840,
            "llm_output": "The issue was... [full response]",
            "sandbox_input": "def factorial(n):\n    if n == 0 or n == 1:\n        return 1\n    result = 1\n    for i in range(2, n + 1):\n        result *= i\n    return result\n\nrun_tests(...)",
            "sandbox_output": "exit_code=0\nstdout=\nstderr=",
            "retries": 0
        }
    ],
    "error": null,
    "timestamp": "2026-08-31T10:30:45.123456"
}

# Write to file
with open("solution.json", "w") as f:
    f.write(solution.model_dump_json(indent=2))
```

---

## SWE-bench Differences

### Key Differences from MBPP:

1. **Docker Container:**
   ```python
   container_id = subprocess.check_output(
       ["docker", "run", "-d", "--rm", "--network", "none", 
        "--memory", "512m", "--workdir", "/testbed", 
        "--entrypoint", "tail", docker_image, "-f", "/dev/null"]
   ).strip()
   # Container runs the entire time, isolated from network
   ```

2. **Environment Variable:**
   ```python
   os.environ["AGENT_SMITH_CONTAINER_ID"] = container_id
   # MCP tools route all commands into this container
   ```

3. **More Complex Tools:**
   - `read_file()`: Read code in the repo
   - `edit_file()`: Edit files to fix bugs
   - `search_code()`: Find relevant code
   - `run_tests()`: Run evaluation script
   - `get_patch()`: Get git diff of changes

4. **Docker Exec:**
   ```python
   # In mcp_tools_swebench.py
   def _docker_exec(command):
       result = subprocess.run(
           ["docker", "exec", CONTAINER_ID, "bash", "-lc", command],
           capture_output=True,
           text=True
       )
       return result.stdout
   ```

5. **Final Answer is a Diff:**
   ```python
   # MBPP: final_answer(function_code)
   # SWE-bench: final_answer(get_patch())
   # get_patch() returns: git -c core.fileMode=false diff
   ```

6. **Cleanup:**
   ```python
   subprocess.run(["docker", "stop", "-t", "5", container_id])
   # Stop and clean up container when done
   ```

---

## Performance Summary

### Example Metrics from solution.json:

```json
{
  "total_time_seconds": 8.5,
  "iterations": 2,
  "total_requests": 2,
  "total_input_tokens": 1100,
  "total_output_tokens": 554,
  "steps": [
    {
      "step": 1,
      "request_time_ms": 2341,
      "input_tokens": 450,
      "output_tokens": 234,
      "retries": 0
    },
    {
      "step": 2,
      "request_time_ms": 1840,
      "input_tokens": 650,
      "output_tokens": 320,
      "retries": 0
    }
  ]
}
```

### Cost Analysis:
- OpenAI gpt-4-turbo: ~$0.01 / 1K input + $0.03 / 1K output
- This task: (1100 × 0.01 + 554 × 0.03) / 1000 = ~$0.027 (2.7 cents)
- Much cheaper than manual programming!

### Success Factors:
- **Iteration count**: Needed 2 attempts (typical for MBPP)
- **Token efficiency**: 1654 total tokens (good for this problem)
- **Speed**: 8.5 seconds wall-clock (includes API latency)

---

## Debugging: How to Read solution.json

### 1. Did it succeed?
```bash
jq '.success' solution.json
# true or false
```

### 2. How many attempts?
```bash
jq '.iterations' solution.json
# Number of Thought → Code → Observation cycles
```

### 3. What was the error?
```bash
jq '.error' solution.json
# null if successful, error message if failed
```

### 4. View the solution:
```bash
jq '.solution' solution.json
# The actual code/diff returned
```

### 5. See LLM responses:
```bash
jq '.steps[0].llm_output' solution.json
# What the LLM generated in iteration 1
```

### 6. See execution results:
```bash
jq '.steps[0].sandbox_output' solution.json
# What happened when code ran
```

### 7. Token analysis:
```bash
jq '.total_input_tokens, .total_output_tokens' solution.json
# For cost calculation
```

---

## Common Issues and Debugging

### Issue: No code block found
**Symptom:** `sandbox_output` shows "No valid code block was found"
**Cause:** LLM didn't output code in recognized format
**Fix:** Try different model or adjust system prompt

### Issue: Import denied
**Symptom:** `sandbox_output` contains "Import blocked by sandbox"
**Cause:** Code tried to import unsafe module (e.g., `os`, `subprocess`)
**Fix:** This is working as intended - sandbox is preventing dangerous access

### Issue: Timeout
**Symptom:** `timed_out: true` in result
**Cause:** Code got stuck in infinite loop or took too long
**Fix:** Increase `max_execution_time_seconds` or improve code

### Issue: Token limit reached
**Symptom:** `error: "Configured token limit reached"`
**Cause:** Too many iterations with long prompts
**Fix:** Increase `max_input_tokens` or `max_output_tokens` limits

---

This completes the full flow! Every message, every step, every error is recorded in `solution.json` for complete reproducibility.
