# Agent Smith: Execution Flow Walkthrough

A step-by-step trace of one MBPP run, showing the exact messages exchanged at each stage. For the components involved, see [GUIDE.md](GUIDE.md); for why the algorithms are built this way, see [ALGORITHMS_EXPLAINED.md](ALGORITHMS_EXPLAINED.md).

```bash
uv run python -m agent_mbpp --task-file cache/mbpp_task.json --output cache/mbpp_solution.json
```

## Input

`cache/mbpp_task.json`:
```json
{
  "task_id": 42,
  "task_definition": "Write a function to compute the factorial of a given number.",
  "function_definition": "def factorial(n):",
  "test_imports": ["math"],
  "test_list": ["assert factorial(5) == 120", "assert factorial(0) == 1", "assert factorial(1) == 1"]
}
```

## 1. Load task and start the MCP tool server

`agent_mbpp.py` validates the task JSON against `MBPPTaskInput`, then spawns `mcp_tools_mbpp.py` as a subprocess and asks it for its tool list over JSON-RPC (`tools/list`). The response describes `run_tests` (code, test_imports, test_list). See [MCP_JSON_RPC.md](MCP_JSON_RPC.md) for the exact wire format.

## 2. Build the prompt

```
Task: Write a function to compute the factorial of a given number.
Function signature: def factorial(n):
Tests: ['assert factorial(5) == 120', 'assert factorial(0) == 1', 'assert factorial(1) == 1']

Write the implementation. In the same Python code block, call
run_tests(code=<your complete function code>, test_imports=['math'], test_list=[...]).
If the tests pass, immediately call final_answer(<your complete function code as a string>).
Never return only a function definition; the final line must call final_answer.
```

## 3. Iteration 1 — first attempt

The LLM receives the system prompt (Thought → Code → Observation instructions + tool manual) and the task prompt as the user message, and replies with a markdown code block defining `factorial` recursively, followed by a call to `run_tests(...)`.

`extract.py` pulls the code out of the ```` ```python ```` block. `sandbox.execute(code)` forks a child process that:
1. Defines `factorial` in a restricted namespace (no `os`, `eval`, network, etc.).
2. Calls the `run_tests` proxy, which sends `{"type": "tool", "name": "run_tests", "kwargs": {...}}` over the pipe.
3. The parent runs the real `run_tests` (via the MCP client), which writes a temp file with the code + assertions and executes it as a subprocess.
4. The result (`exit_code=1\nstderr=RecursionError: ...` — say the recursive version overflows) comes back to the child, which does not call `final_answer()`, so the sandbox returns with `final_answer=None`.

Recorded in `StepMetrics`: input/output tokens, request time, the exact LLM output, the exact code executed, and the sandbox output.

## 4. Building the next observation

Since no final answer was produced, `loop.py` folds the previous task + this step's extraction and sandbox output into a new observation string and starts iteration 2:

```
Task context: ...
Previous step 1 result:
Extraction: python code block
Observation:
exit_code=1
stderr=RecursionError: maximum recursion depth exceeded
```

## 5. Iteration 2 — learning from failure

The LLM sees the failure, switches to an iterative implementation, and this time also calls `final_answer(<code>)` after `run_tests` reports `exit_code=0`. The sandbox reports `final_answer` set, and the loop breaks.

## 6. Save `solution.json`

```json
{
  "task_id": "42",
  "benchmark": "mbpp",
  "success": true,
  "solution": "def factorial(n): ...",
  "iterations": 2,
  "total_requests": 2,
  "total_input_tokens": 1100,
  "total_output_tokens": 554,
  "total_time_seconds": 8.5,
  "steps": [ /* one StepMetrics object per iteration */ ],
  "error": null,
  "timestamp": "..."
}
```

`agent_mbpp.py` then closes the MCP client. If the loop didn't reach `final_answer` but the last attempted code passed `run_tests` anyway, the entry point retries `run_tests` once and salvages a success — this handles the case where the LLM forgot to call `final_answer`.

## SWE-bench differences

- A Docker container is started first (`docker run -d --rm --network none --memory 512m ...`), and its ID is exported as `AGENT_SMITH_CONTAINER_ID` so `mcp_tools_swebench.py` can route `read_file`/`edit_file`/`run_command` through `docker exec`.
- The tool set is larger: `read_file`, `edit_file`, `list_files`, `search_code`, `search_function_or_class_definition_in_code`, `find_references`, `run_tests`, `get_patch`, `run_command`.
- The final answer is `get_patch()` — a `git -c core.fileMode=false diff` — instead of function source.
- Token budgets are much larger (300000 input / 10000 output vs. MBPP's 6000/6000) since exploring a real repo needs more context.
- The container is stopped (`docker stop -t 5 ...`) in a `finally` block regardless of outcome.
- If the loop ends without `final_answer` but a test run reported `exit_code=0`/`passed` and a diff was captured, `agent_swebench.py` salvages that diff as the solution — the same "LLM forgot to call final_answer" fallback as MBPP.

## Reading the trace afterward

```bash
jq '.success, .iterations, .error' solution.json
jq '.steps[0].llm_output, .steps[0].sandbox_output' solution.json
```

See [GUIDE.md](GUIDE.md#debugging-with-solutionjson) for the full debugging command list.
