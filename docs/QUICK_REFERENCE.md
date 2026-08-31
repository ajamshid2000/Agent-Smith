# Agent Smith: Quick Reference Guide

## For the Impatient: Start Here

### Install & Run
```bash
# Setup
uv sync
echo "OPENAI_API_KEY=sk-..." > .env

# Get a task
cd moulinette
uv run moulinette_eval dump mbpp --output ../task.json
cd ..

# Run agent
uv run python -m agent_mbpp --task-file task.json --output solution.json

# See results
cat solution.json | jq '.success, .iterations, .total_time_seconds'
```

### Files You Need to Know

| File | Purpose |
|------|---------|
| `agent_mbpp.py` | Entry point for MBPP agent |
| `agent_swebench.py` | Entry point for SWE-bench agent |
| `agent_smith/loop.py` | Main Thought → Code → Observation loop |
| `agent_smith/sandbox.py` | Secure code execution |
| `agent_smith/providers.py` | LLM API client |
| `agent_smith/models.py` | Data structures |
| `agent_smith/extract.py` | Parse LLM responses |
| `agent_smith/mcp.py` | Model Context Protocol client |
| `mcp_tools_mbpp.py` | Tools for MBPP (run_tests) |
| `mcp_tools_swebench.py` | Tools for SWE-bench (file ops, commands) |

---

## Key Concepts (TL;DR)

### Thought → Code → Observation Loop
```
Task → LLM generates code → Run code → See results → Back to LLM with feedback
```
LLM learns from failures and improves each iteration.

### Sandbox Security
```
Child process with:
- Import whitelist (no os, subprocess, socket)
- Path restrictions (only /testbed, /tmp/agent)
- Memory limit (512 MB)
- Time limit (30 seconds)
```
Safely runs LLM-generated code without risk.

### MCP Tools
```
Agent wants to call: run_tests(code="...")
  ↓
Sandbox intercepts (blocked from direct access)
  ↓
Sends to MCP server via JSON-RPC
  ↓
MCP server executes tool
  ↓
Returns result to sandbox
```
Tools in separate process, agent stays safe.

### Token Limits
```
Track input/output tokens across iterations
Stop if exceeding limits (cost + safety)
Balance: need tokens for context, but can't spend infinite tokens
```

---

## MBPP Agent Flow

```
┌─────────────────┐
│ task.json       │
│ (problem spec)  │
└────────┬────────┘
         ↓
┌─────────────────────────────────────────┐
│ 1. Load task and validate               │
│ 2. Start MCP server (run_tests tool)    │
│ 3. Initialize provider (OpenAI)         │
│ 4. Initialize sandbox (security)        │
│ 5. Create loop (max 10 iterations)      │
└────────┬────────────────────────────────┘
         ↓
┌─────────────────────────────────────────┐
│ Loop:                                   │
│  - Send task + observations to LLM      │
│  - Extract code from response           │
│  - Execute in sandbox                   │
│  - If final_answer() → done             │
│  - Else update observation and retry    │
└────────┬────────────────────────────────┘
         ↓
┌──────────────────┐
│ solution.json    │
│ (results + trace)│
└──────────────────┘
```

---

## SWE-bench Agent Flow

```
┌────────────────────────┐
│ swebench_task.json     │
│ (bug description)      │
└───────────┬────────────┘
            ↓
┌────────────────────────────────────────────┐
│ 1. Load task and validate                  │
│ 2. Start Docker container (repo isolated)  │
│ 3. Start MCP server (file ops, commands)   │
│ 4. Initialize provider (OpenAI)            │
│ 5. Initialize sandbox (security)           │
│ 6. Create loop (max 30 iterations)         │
└────────┬─────────────────────────────────┘
         ↓
┌────────────────────────────────────────────┐
│ Loop:                                      │
│  - Send problem to LLM (in Docker)         │
│  - LLM reads/edits files (via MCP)         │
│  - LLM runs tests (in Docker)              │
│  - If tests pass → final_answer(git diff)  │
│  - Else retry                              │
└────────┬─────────────────────────────────┘
         ↓
    Docker stops
         ↓
┌──────────────────┐
│ solution.json    │
│ (git diff + trace)
└──────────────────┘
```

---

## Common Commands

### Development
```bash
make install      # Install dependencies
make run          # Interactive sandbox (test security)
make clean        # Remove __pycache__, .pytest_cache
```

### Running Agents
```bash
# MBPP
make mbpp TASK_FILE=task.json OUTPUT=solution.json MODEL_NAME="gpt-4-turbo" PROVIDER_URL="https://api.openai.com/v1"

# SWE-bench
make swebench TASK_FILE=swebench_task.json OUTPUT=solution.json MODEL_NAME="gpt-4-turbo" PROVIDER_URL="https://api.openai.com/v1"
```

### Debugging
```bash
# See solution details
jq . solution.json

# Just success/fail
jq '.success' solution.json

# See LLM outputs
jq '.steps[].llm_output' solution.json

# See execution results
jq '.steps[].sandbox_output' solution.json

# Token usage
jq '.total_input_tokens, .total_output_tokens' solution.json

# Time elapsed
jq '.total_time_seconds' solution.json
```

---

## Key Files Explained

### `agent_smith/loop.py` (Most Important)
**Core Algorithm:** Thought → Code → Observation loop
- Sends observation to LLM
- Extracts and executes code
- Checks for solution
- Updates observation with results
- Repeats

**Read this to understand:** How agent reasons

### `agent_smith/sandbox.py` (Most Secure)
**Security:** Executes untrusted code safely
- Forks child process
- Restricts imports (whitelist)
- Restricts file access (allowed dirs only)
- Limits memory (512 MB)
- Limits time (30 seconds)
- Proxies tool calls back to parent

**Read this to understand:** How agent stays safe

### `agent_smith/providers.py` (Most Flexible)
**LLM Communication:** Abstracts API details
- Supports any OpenAI-compatible provider
- Handles API key rotation
- Measures tokens and time
- Retries on failure
- Works with OpenAI, Claude, local models

**Read this to understand:** How agent talks to LLM

### `mcp_tools_mbpp.py` (Simple Tool)
**MBPP Tools:** One tool that runs tests
- `run_tests(code, test_imports, test_list)`
- Creates temp file with code + tests
- Runs as subprocess
- Returns exit code + output

**Read this to understand:** How tools work in MBPP

### `mcp_tools_swebench.py` (Complex Tools)
**SWE-bench Tools:** Many tools for code exploration/editing
- `read_file()`: Read code in repo
- `edit_file()`: Modify code
- `search_code()`: Find patterns
- `run_tests()`: Run evaluation
- `get_patch()`: Get git diff
- `run_command()`: Execute arbitrary command

**Read this to understand:** How tools work in SWE-bench

---

## Data Structures

### Input
```python
# MBPP
{
  "task_id": int,
  "task_definition": str,
  "function_definition": str,
  "test_imports": List[str],
  "test_list": List[str]
}

# SWE-bench
{
  "instance_id": str,
  "problem_statement": str,
  "docker_image": str,
  "eval_script": str,
  "hints_text": str,
  "repo": str
}
```

### Output (solution.json)
```python
{
  "task_id": str,
  "benchmark": "mbpp" | "swebench",
  "success": bool,
  "solution": str,  # Function code or git diff
  "iterations": int,
  "total_requests": int,
  "total_input_tokens": int,
  "total_output_tokens": int,
  "total_time_seconds": float,
  "steps": [
    {
      "step": int,
      "input_tokens": int,
      "output_tokens": int,
      "request_time_ms": float,
      "llm_output": str,  # What LLM generated
      "sandbox_input": str,  # Code executed
      "sandbox_output": str,  # Execution result
      "retries": int
    },
    ...
  ],
  "error": str | null
}
```

---

## Environment Variables

### API Keys (Priority Order)
```bash
AGENT_SMITH_API_KEYS=key1,key2,key3    # Explicit list
OPENAI_API_KEY=sk-...                   # Provider-specific
ANTHROPIC_API_KEY=sk-...                # Provider-specific
```

### For SWE-bench
```bash
AGENT_SMITH_CONTAINER_ID=abc123...     # Set by agent internally
TESTBED_PATH=/testbed                   # Root path in container
```

---

## Debugging Checklist

### If Agent Fails

1. **Check sandbox output**
   ```bash
   jq '.steps[-1].sandbox_output' solution.json
   ```

2. **Check LLM output**
   ```bash
   jq '.steps[-1].llm_output' solution.json
   ```

3. **Check if it's a timeout**
   ```bash
   jq '.steps[-1] | {timed_out, error}' solution.json
   ```

4. **Check token usage**
   ```bash
   jq '.total_input_tokens, .total_output_tokens' solution.json
   ```

5. **Try with more tokens**
   ```bash
   python -m agent_mbpp --max-iterations 20 ...
   ```

---

## Architecture Diagram

```
┌────────────────────────────────────────────────────────────┐
│                      Agent Smith                            │
├────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────┐    ┌──────────────┐    ┌─────────────┐ │
│  │   Provider     │    │   Sandbox    │    │ MCP Client  │ │
│  │  (OpenAI API)  │    │  (Security)  │    │  (Tools)    │ │
│  └────────┬───────┘    └──────┬───────┘    └──────┬──────┘ │
│           │                   │                   │        │
│  ┌────────▼───────────────────▼───────────────────▼──────┐  │
│  │           AgentLoop (Reasoning)                       │  │
│  │                                                        │  │
│  │  Thought → Code → Observation loop                   │  │
│  │  Tracks metrics, iterations, tokens                   │  │
│  └────────┬───────────────────────────────────────────────┘  │
│           │                                                    │
│  ┌────────▼──────────┐                                        │
│  │  solution.json    │                                        │
│  │  (complete trace) │                                        │
│  └───────────────────┘                                        │
│                                                              │
└────────────────────────────────────────────────────────────┘
```

---

## Next Steps

1. **Understand the loop:** Read `agent_smith/loop.py`
2. **Understand security:** Read `agent_smith/sandbox.py`
3. **Try it out:** Run MBPP agent on simple task
4. **Analyze results:** Use `jq` to explore `solution.json`
5. **Experiment:** Modify system prompt, try different models
6. **Scale up:** Try SWE-bench on real bugs

---

## Additional Resources

- **PROJECT_GUIDE.md**: Comprehensive overview of entire system
- **EXECUTION_FLOW.md**: Step-by-step walkthrough with examples
- **ALGORITHMS_EXPLAINED.md**: Deep dive into key algorithms
- **Code comments**: Every function has detailed docstrings explaining why

---

**Good luck exploring Agent Smith! 🚀**
