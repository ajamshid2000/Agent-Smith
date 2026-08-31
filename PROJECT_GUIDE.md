# Agent Smith: Complete Project Guide

## Table of Contents
1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [Execution Flow](#execution-flow)
5. [Running the Project](#running-the-project)
6. [Benchmarks](#benchmarks)
7. [Key Concepts](#key-concepts)

---

## Project Overview

**Agent Smith** is an autonomous AI coding agent framework that uses a **Thought → Code → Observation loop** to solve programming tasks. It's designed to work with two benchmarks:

1. **MBPP (Mostly Basic Programming Problems)**: Simple programming tasks requiring function implementation
2. **SWE-bench (SoftWare Engineering benchmark)**: Real-world bug-fixing tasks in actual open-source repositories

### Core Purpose
Agent Smith acts like an AI programmer:
- **Receives** a coding task/problem statement
- **Thinks and writes Python code** to solve it
- **Executes** that code in a sandboxed environment
- **Observes** the results
- **Iterates** until it finds a solution

The framework is designed to be:
- **Safe**: Code runs in restricted sandboxes with no network access
- **Flexible**: Works with any OpenAI-compatible LLM provider
- **Observable**: Logs every step, token count, API call, etc.
- **Bounded**: Has limits on iterations, tokens, and execution time to prevent infinite loops

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Agent Smith                              │
│  (Main Reasoning Loop: Thought → Code → Observation)         │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
    ┌────────┐  ┌────────┐  ┌─────────────┐
    │Provider│  │Sandbox │  │MCP Tools    │
    │(OpenAI)   │(Python)   │(File/Tests) │
    └────────┘  └────────┘  └─────────────┘
        │            │            │
        └────────────┼────────────┘
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
    ┌──────────┐          ┌──────────────┐
    │ MBPP     │          │ SWE-bench    │
    │ Agent    │          │ Agent        │
    └──────────┘          └──────────────┘
        │                         │
        └────────────┬────────────┘
                     ▼
              ┌─────────────┐
              │ solution.json
              │ (Results)
              └─────────────┘
```

### Data Flow
1. **Load Task**: Read task.json (MBPP) or swebench_task.json (SWE-bench)
2. **Initialize Provider**: Connect to LLM API (OpenAI or compatible)
3. **Initialize Sandbox**: Create restricted execution environment
4. **Initialize MCP Tools**: Connect to available tools (file operations, tests, etc.)
5. **Run Loop**: Iterate until max iterations or solution found:
   - Send task + observations to LLM
   - Extract code from LLM response
   - Execute code in sandbox
   - Record metrics (tokens, time, output)
   - Update observations with results
6. **Save Solution**: Write solution.json with all details

---

## Core Components

### 1. **Models** (`agent_smith/models.py`)
Data structures using Pydantic for type safety and validation.

```
INPUT MODELS:
├── MBPPTaskInput
│   ├── task_id: int
│   ├── task_definition: str (problem description)
│   ├── function_definition: str (function signature)
│   ├── test_imports: List[str] (imports needed for tests)
│   └── test_list: List[str] (actual test assertions)
│
└── SWEBenchTaskInput
    ├── instance_id: str
    ├── problem_statement: str (bug description)
    ├── docker_image: str (repo container)
    ├── eval_script: str (test runner)
    ├── hints_text: str (optional hints)
    └── repo: str (repository name)

OUTPUT MODEL:
└── SolutionOutput
    ├── task_id: str
    ├── benchmark: str (mbpp or swebench)
    ├── success: bool (did it solve the task?)
    ├── solution: str (final answer)
    ├── iterations: int (how many attempts)
    ├── total_requests: int (LLM API calls)
    ├── total_input_tokens: int
    ├── total_output_tokens: int
    ├── total_time_seconds: float
    ├── steps: List[StepMetrics] (detailed trace of each iteration)
    ├── system_prompt: str (the exact prompt sent to LLM)
    ├── error: Optional[str] (error message if failed)
    └── timestamp: str

STEP METRICS (recorded for each iteration):
└── StepMetrics
    ├── step: int
    ├── input_tokens: int
    ├── output_tokens: int
    ├── request_time_ms: float
    ├── timestamp: str
    ├── api_url: str
    ├── model_name: str
    ├── llm_output: str (raw LLM response)
    ├── sandbox_input: str (code executed)
    ├── sandbox_output: str (execution result)
    ├── retries: int (API key rotations)
```

**Why?** Having structured data models prevents bugs, enables validation, and makes serialization to JSON automatic.

---

### 2. **Provider** (`agent_smith/providers.py`)
Handles communication with the LLM API.

**Key Concepts:**
- **OpenAI-compatible**: Works with OpenAI, Anthropic Claude, local models, etc.
- **API Key Rotation**: If one key fails, try the next one automatically
- **Load from Environment**: Reads API keys from `.env` file and environment variables

**Main Class: `OpenAIProvider`**
```
Input:
  - model_name: "gpt-5.4-mini" or "claude-3.5-sonnet", etc.
  - provider_url: "https://api.openai.com/v1" or any compatible endpoint
  - api_keys: List of keys for rotation

Method: complete()
  - Sends system prompt + user prompt to LLM
  - Returns: Code generated, token counts, request time, retry count
  - Handles timeouts (120 seconds) and API errors gracefully
```

**Why?** Abstracts LLM interaction so the agent doesn't care which provider/model is used.

---

### 3. **Sandbox** (`agent_smith/sandbox.py`)
Safely executes untrusted Python code with security restrictions.

**Security Features:**
- **Import Allowlist**: Only allow "safe" imports (math, collections, itertools, etc.)
- **Path Restrictions**: Can only read/write in allowed directories
- **Memory Limit**: Max 512 MB RAM by default
- **Time Limit**: Max 30 seconds execution by default
- **No Network**: Network operations blocked

**How It Works:**
1. Forks a child process with restricted permissions
2. Child process:
   - Replaces `__import__` to check allowlist
   - Replaces `open()` to check path restrictions
   - Replaces memory limits with `resource.setrlimit`
   - Executes user code in restricted namespace
3. Parent process monitors child:
   - Intercepts tool calls and routes to MCP
   - Waits for final_answer() call
   - Kills process if timeout exceeded
   - Returns: output, errors, whether timed out

**Tool Proxy:**
The sandbox code runs in a restricted namespace but can call MCP tools (e.g., `run_tests()`, `read_file()`). These calls are proxied back to the parent process through a pipe.

**Why?** Prevents malicious or buggy code from crashing the agent or accessing the system.

---

### 4. **MCP Tools** (`mcp_tools_mbpp.py` and `mcp_tools_swebench.py`)
Provides task-specific tools that the sandbox can call.

#### MBPP Tools (`mcp_tools_mbpp.py`):
```
run_tests(code, test_imports, test_list)
  - Executes candidate code with test assertions
  - Returns exit code, stdout, stderr
  - Used to validate solutions
  
Example:
  code = "def factorial(n): return 1 if n <= 1 else n * factorial(n-1)"
  test_imports = ["math"]
  test_list = ["assert factorial(5) == 120", "assert factorial(1) == 1"]
  Result: "exit_code=0\nstdout=\nstderr=" (tests passed)
```

#### SWE-bench Tools (`mcp_tools_swebench.py`):
```
read_file(filepath, start_line, end_line)
  - Read code in the Docker container with line numbers
  
edit_file(filepath, old_str, new_str)
  - Replace exact string in a file (must occur exactly once)
  
list_files(directory, pattern)
  - Find files matching glob pattern
  
search_code(pattern, file_pattern)
  - Grep-like search with regex
  
search_function_or_class_definition_in_code(name)
  - Find where a function/class is defined
  
find_references(name, filepath, line)
  - Find all references to a symbol
  
run_tests()
  - Run the evaluation script
  
get_patch()
  - Return git diff of changes made
  
run_command(command, workdir)
  - Execute arbitrary shell command
```

**Docker Integration:**
- SWE-bench tasks run in Docker containers to isolate the repository
- Environment variable `AGENT_SMITH_CONTAINER_ID` identifies the container
- Tools automatically route commands into the container using `docker exec`

**MCP Protocol:**
- Tools are exposed via **Model Context Protocol** (JSON-RPC over stdin/stdout)
- Agent communicates with tool server by sending JSON messages
- Tool server responds with results

**Why?** Provides the agent with the ability to run tests, read/edit files, search code, etc.

---

### 5. **Loop** (`agent_smith/loop.py`)
The main reasoning loop that orchestrates everything.

**Algorithm:**
```
for iteration in 1 to max_iterations:
  1. Check token limits (break if exceeded)
  2. Call LLM: complete(system_prompt, observation, max_tokens=1500)
  3. Extract Python code from LLM response
  4. Execute code in sandbox
  5. Record metrics (tokens, time, code, output)
  6. If execution returned final_answer:
       - Break loop, return solution
  7. Otherwise:
       - Build observation = previous task + extraction + output
       - Go to step 1 with updated observation

Return SolutionOutput with all metrics and steps
```

**Key Features:**
- **Token Tracking**: Keeps running total of input/output tokens
- **Time Tracking**: Records total time and per-request time
- **Error Handling**: Catches exceptions and records them
- **Metrics Recording**: Every step is logged for reproducibility

**The Observation Loop:**
```
Iteration 1:
  Observation = "Task: implement factorial function"
  LLM thinks and generates code
  Code executes, produces output
  
Iteration 2:
  Observation = "Task: implement factorial function
                 Previous iteration result: tests failed with error..."
  LLM learns from previous attempt and tries again
  
Iteration N:
  Observation = "Task: ... [previous 5 iterations' results]..."
  LLM finally generates working solution
  Code calls final_answer(solution_code)
  Loop terminates successfully
```

**Why?** This is the core algorithm - it's what makes the agent iterative and able to learn from failures.

---

### 6. **Extract** (`agent_smith/extract.py`)
Parses LLM responses to extract executable code.

**Supported Formats:**
```
1. Python code blocks:
   ```python
   code here
   ```

2. XML tool calls:
   <invoke name="run_tests">
     <parameter name="code">...</parameter>
   </invoke>

3. JSON tool calls (Hermes format):
   <tool_call>{"name": "run_tests", "arguments": {...}}
   </tool_call>

4. ReAct format:
   Action: run_tests
   Action Input: {"code": "..."}
```

**Process:**
- Search for code blocks in regex order (Python → XML → JSON → ReAct)
- Return extracted code + description of what was found
- If nothing found, return empty string + error message

**Why?** LLMs output code in different formats. This normalizes all of them.

---

## Execution Flow

### MBPP Agent Flow (`agent_mbpp.py`)

```
1. Parse command-line arguments (task file, output file, model, provider)

2. Load environment:
   - Read .env file for API keys
   
3. Load MBPP task from JSON:
   {
     "task_id": 42,
     "task_definition": "Implement Fibonacci",
     "function_definition": "def fibonacci(n):",
     "test_imports": ["math"],
     "test_list": ["assert fibonacci(5) == 5", ...]
   }

4. Start MCP tool server:
   - Subprocess: python mcp_tools_mbpp.py
   - MCP server provides: run_tests tool
   
5. Build prompt:
   "Task: Implement Fibonacci
    Function signature: def fibonacci(n):
    Tests: assert fibonacci(5) == 5, ...
    
    Write the implementation. In the same Python code block, call 
    run_tests(code=<your complete function code>, test_imports=..., test_list=...).
    If the tests pass, immediately call final_answer(<your complete function code as a string>).
    Never return only a function definition; the final line must call final_answer."

6. Create provider, sandbox, and loop

7. Run AgentLoop.run():
   - Iteration 1:
     * LLM sees the prompt
     * Generates Python code that defines function + calls run_tests()
     * Sandbox executes: function defined, tests run, outputs results
     * If tests pass, final_answer() is called
   
   - Iteration 2+ (if tests failed):
     * LLM sees: previous test output showing which assertions failed
     * Generates improved code
     * Process repeats

8. Save solution to solution.json:
   {
     "task_id": "42",
     "benchmark": "mbpp",
     "success": true,
     "solution": "def fibonacci(n): ...",
     "iterations": 3,
     "total_requests": 3,
     "total_input_tokens": 1500,
     "total_output_tokens": 800,
     "total_time_seconds": 12.5,
     "steps": [
       {
         "step": 1,
         "input_tokens": 500,
         "output_tokens": 300,
         "llm_output": "...",
         "sandbox_input": "def fibonacci(n): ...",
         "sandbox_output": "FAILED: ...",
         ...
       },
       ...
     ],
     "error": null
   }

9. Close MCP connection
```

### SWE-bench Agent Flow (`agent_swebench.py`)

```
1. Parse arguments and load task from swebench_task.json:
   {
     "instance_id": "django/django-12345",
     "problem_statement": "Fix bug where ...",
     "docker_image": "swebench/django:latest",
     "eval_script": "cd /testbed && python -m pytest ...",
     "hints_text": "The bug is in models.py"
   }

2. Start Docker container:
   - docker run -d --rm --network none --memory 512m ... [image] tail -f /dev/null
   - Container keeps running, isolated from network
   - Store container ID in AGENT_SMITH_CONTAINER_ID env var

3. Start MCP tool server:
   - Subprocess: python mcp_tools_swebench.py
   - MCP server provides: read_file, edit_file, search_code, run_tests, get_patch, etc.
   - All file operations route into the Docker container

4. Build prompt:
   "Instance: django/django-12345
    Repository: django
    Problem statement: Fix bug where ...
    Hints: The bug is in models.py
    Evaluation script: cd /testbed && python -m pytest ...
    
    Explore the repository, edit the bug, run focused tests, then call final_answer(get_patch())."

5. Run AgentLoop.run():
   - Iteration 1:
     * LLM sees the problem statement
     * Generates code that calls read_file() to explore repo
     * Sandbox routes calls to MCP tool server
     * MCP tool server runs commands in Docker container
     * LLM learns about the codebase
   
   - Iteration 2+:
     * LLM calls edit_file() to fix bugs
     * LLM calls run_tests() to check if fix works
     * Loop iterates until tests pass and final_answer(get_patch()) is called

6. Save solution.json

7. Stop Docker container:
   - docker stop -t 5 [container_id]

8. Close MCP connection
```

---

## Running the Project

### Prerequisites
- Python 3.10
- `uv` package manager (or pip)
- For SWE-bench: Docker installed and running
- API credentials for LLM provider (OpenAI, etc.)

### Setup

```bash
# 1. Install dependencies
uv sync
# or: pip install -e .

# 2. Create .env file with API key
cat > .env << EOF
OPENAI_API_KEY=sk-...
EOF
```

### Running MBPP Agent

```bash
# Step 1: Get an MBPP task from moulinette
cd moulinette
uv run moulinette_eval dump mbpp --output ../task.json
cd ..

# Step 2: Run agent
uv run python -m agent_mbpp \
  --task-file task.json \
  --output solution.json \
  --model-name "gpt-4-turbo" \
  --provider-url "https://api.openai.com/v1"

# View results
cat solution.json | jq .
```

### Running SWE-bench Agent

```bash
# Step 1: Get a SWE-bench task
cd moulinette
uv run moulinette_eval dump swebench --output ../swebench_task.json
cd ..

# Step 2: Make sure Docker image is available
docker pull swebench/django:latest

# Step 3: Run agent
uv run python -m agent_swebench \
  --task-file swebench_task.json \
  --output solution.json \
  --model-name "gpt-4-turbo" \
  --provider-url "https://api.openai.com/v1"

# View results
cat solution.json | jq '.success, .iterations, .total_time_seconds'
```

### Interactive Sandbox Testing

```bash
# Test sandbox with manual code execution
uv run sandbox

# In sandbox, type Python code:
# > print("Hello")
# {"output":"Hello\n","error":null,"final_answer":null,"timed_out":false,"truncated":false}

# > x = 1/0  # Divide by zero
# {"output":"","error":"...division by zero...","final_answer":null,"timed_out":false,"truncated":false}

# > exit
```

### Makefile Shortcuts

```bash
make install        # Install dependencies
make run            # Launch interactive sandbox
make mbpp           # Run MBPP agent (requires task.json)
make swebench       # Run SWE-bench agent (requires swebench_task.json)
make clean          # Remove __pycache__, .pytest_cache, etc.
make fclean         # Clean + remove .venv and build artifacts
make re             # Clean reinstall from scratch
```

---

## Benchmarks

### MBPP (Mostly Basic Programming Problems)

**What it is:**
- Collection of ~1000 programming problems
- Each problem: function description + test cases
- Difficulty: beginner to intermediate
- Example: "Implement Fibonacci", "Sort a list", "Find palindromes"

**Evaluation:**
- Agent must generate code that passes all tests
- Success = exit code 0 from pytest
- Metrics: accuracy, tokens used, iterations needed, wall-clock time

**Agent Strategy:**
1. Read function signature and tests
2. Generate implementation
3. Run tests; if failed, see error messages
4. Iterate with LLM feedback until tests pass

---

### SWE-bench (SoftWare Engineering)

**What it is:**
- Real open-source repositories with actual bugs
- Each task: problem description + evaluation script
- Difficulty: intermediate to very hard
- Example: "Fix Django ORM query bug", "Fix NumPy array indexing"

**Evaluation:**
- Agent must make code changes that pass evaluation tests
- Success = evaluation script exits with code 0
- Metrics: accuracy, token usage, iterations, time

**Agent Strategy:**
1. Explore repository structure
2. Search for relevant code
3. Understand bug from problem statement
4. Edit files to fix bug
5. Run tests; if still failing, explore more
6. Iterate until evaluation passes

**Docker Setup:**
- Each task runs in isolated Docker container
- Repository is checked out inside container
- Agent can't see host filesystem
- Network is disabled for security

---

## Key Concepts

### 1. **Thought → Code → Observation Loop**
The agent operates in iterations:
- **Thought**: LLM receives task + previous observations
- **Code**: LLM generates Python code
- **Observation**: Code executes, results fed back to LLM
- **Iterate**: Repeat until solution found or max iterations reached

This mimics how human programmers solve problems: try something, see what happens, adjust based on feedback.

### 2. **Token Limits**
The agent has constraints to prevent infinite loops:
- `max_input_tokens`: 6000 for MBPP, 300000 for SWE-bench
- `max_output_tokens`: 1500 for MBPP, 10000 for SWE-bench
- `max_iterations`: 10 for MBPP, 30 for SWE-bench
- If limits reached, agent terminates and returns partial result

### 3. **Sandbox Security**
Code runs in a **restricted child process** with:
- No network access
- Limited file system access (only `/testbed`, `/tmp/agent`)
- Limited memory (512 MB by default)
- Limited execution time (30 seconds by default)
- Limited imports (only "safe" modules)

This allows running untrusted AI-generated code safely.

### 4. **MCP (Model Context Protocol)**
A standardized protocol for LLMs to call external tools:
- Agent sends: `{"method": "tools/call", "name": "run_tests", "arguments": {...}}`
- Tool server processes and responds: `{"result": "..."}`
- Agent's sandbox intercepts these calls and routes to MCP server

This allows the same agent code to work with different sets of tools (MBPP vs SWE-bench).

### 5. **Metrics & Observability**
Every step is recorded:
- Input/output tokens (for cost analysis)
- Request time (for performance analysis)
- LLM output (for debugging)
- Sandbox input/output (for tracing)
- Retries/failures (for reliability analysis)

All stored in `solution.json` for reproducibility and analysis.

### 6. **API Key Rotation**
Multiple API keys can be provided:
```
AGENT_SMITH_API_KEYS="key1,key2,key3"
OPENAI_API_KEY="key4"
ANTHROPIC_API_KEY="key5"
```

If one key fails, the next one is tried. This increases reliability when using multiple providers or accounts.

### 7. **Provider Compatibility**
The framework uses OpenAI-compatible API format. It works with:
- OpenAI (gpt-4, gpt-3.5-turbo, etc.)
- Anthropic Claude (via AWS Bedrock)
- Local models (via Ollama, LM Studio, etc.)
- Other providers (Groq, Together AI, etc.)

Just change `--provider-url` and provide appropriate API key.

---

## Understanding the Code Comments

When you read the code, you'll see comments explaining:
1. **Why** a function exists (not just what it does)
2. **How** data flows through components
3. **When** each component is used in the pipeline
4. **Edge cases** and security considerations

For example, in `sandbox.py`:
```python
# This restricted_import function replaces the normal __import__
# WHY? Because we need to prevent the untrusted code from importing
# dangerous modules like os, subprocess, socket, etc.
# HOW? We check each import against the allowlist and raise ImportError
# WHEN? Every time the untrusted code tries to import something
def restricted_import(name: str, ...):
    if not _allowed_import(name, config):
        raise ImportError(f"Import blocked: {name}")
    return original_import(...)
```

---

## Debugging Tips

### 1. **See what the LLM received**
```bash
jq '.system_prompt' solution.json
jq '.steps[0].llm_output' solution.json
```

### 2. **See what code was executed**
```bash
jq '.steps[0].sandbox_input' solution.json
```

### 3. **See what the sandbox output**
```bash
jq '.steps[0].sandbox_output' solution.json
```

### 4. **Trace iterations**
```bash
jq '.steps | length' solution.json  # How many iterations?
jq '.steps[].step' solution.json     # List all step numbers
```

### 5. **Check token usage**
```bash
jq '.total_input_tokens, .total_output_tokens' solution.json
```

### 6. **Enable verbose output**
Run with stderr visible to see MCP protocol messages:
```bash
uv run python -m agent_mbpp --task-file task.json 2>&1 | tee agent.log
```

---

## File Organization

```
Agent_Smith/
├── agent_smith/              # Main package
│   ├── __init__.py           # Package marker
│   ├── models.py             # Pydantic data models
│   ├── providers.py          # LLM API client (OpenAI-compatible)
│   ├── sandbox.py            # Restricted code execution
│   ├── mcp.py                # Model Context Protocol client
│   ├── loop.py               # Main reasoning loop
│   ├── extract.py            # LLM response parsing
│
├── agent_mbpp.py             # MBPP agent entry point
├── agent_swebench.py         # SWE-bench agent entry point
├── mcp_tools_mbpp.py         # MCP tools for MBPP (run_tests)
├── mcp_tools_swebench.py     # MCP tools for SWE-bench (file ops, commands, etc.)
│
├── pyproject.toml            # Project metadata and dependencies
├── Makefile                  # Build and run shortcuts
├── README.md                 # Quick start guide
│
├── task.json                 # MBPP task (generated by moulinette)
├── swebench_task.json        # SWE-bench task (generated by moulinette)
├── solution.json             # Results (generated by agent)
│
├── moulinette/               # Test framework (ignore for now)
│   └── (testing utilities)
│
└── PROJECT_GUIDE.md          # This file
```

---

## Next Steps

1. **Try it out**: Run the MBPP agent on a simple task
2. **Explore the code**: Read through `loop.py` to understand the main logic
3. **Experiment**: Modify the system prompt in `loop.py` and see how it affects solutions
4. **Debug**: Use the tips above to understand what the LLM is doing
5. **Scale up**: Try SWE-bench on real open-source bugs

Good luck! 🚀
