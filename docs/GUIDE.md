# Agent Smith: Guide

Agent Smith is a Python 3.10 agent framework built around a **Thought → Code → Observation** loop: the LLM writes Python, a sandbox runs it, the result feeds back into the next prompt. It targets two benchmarks:

- **MBPP** (Mostly Basic Programming Problems): implement a function against a set of `assert` tests.
- **SWE-bench**: fix a real bug in an open-source repo running inside a Docker container.

## Architecture

```
                        Agent Smith
        (AgentLoop: Thought -> Code -> Observation)
                            |
        +-------------------+-------------------+
        v                   v                   v
    Provider             Sandbox             MCP Tools
   (LLM client)      (restricted exec)    (file ops / tests)
        |                   |                   |
        +-------------------+-------------------+
                            |
                +-----------+-----------+
                v                       v
            MBPP agent            SWE-bench agent
                |                       |
                +-----------+-----------+
                            v
                       solution.json
```

Each run:
1. Loads the task (`task.json` for MBPP, `swebench_task.json` for SWE-bench).
2. Starts the matching MCP tool server as a subprocess (SWE-bench also starts a Docker container).
3. Loops (`agent_smith/loop.py`): send prompt → LLM returns code → extract code → run it in the sandbox → check for `final_answer()` → otherwise fold the result into the next observation.
4. Writes `solution.json` with the full trace (every step's tokens, code, and output).

## Core components

| File | Responsibility |
|---|---|
| `agent_smith/models.py` | Pydantic models for task input/output (`MBPPTaskInput`, `SWEBenchTaskInput`, `SolutionOutput`, `StepMetrics`). |
| `agent_smith/providers.py` | `OpenAIProvider` — OpenAI-compatible chat completion client with API key rotation. |
| `agent_smith/sandbox.py` | Forks a restricted child process to run LLM-generated code: import allowlist, path restrictions, memory/time limits, tool-call proxying. See [SANDBOX_MESSAGE_PROTOCOL.md](SANDBOX_MESSAGE_PROTOCOL.md) for the IPC format. |
| `agent_smith/mcp.py` | MCP (JSON-RPC) client used to talk to the tool servers. See [MCP_JSON_RPC.md](MCP_JSON_RPC.md) for message formats. |
| `agent_smith/loop.py` | `AgentLoop` — the Thought → Code → Observation algorithm and token/iteration bookkeeping. |
| `agent_smith/extract.py` | Parses LLM output into executable code (markdown blocks, XML `<invoke>`, JSON tool calls, ReAct `Action:` format). |
| `agent_mbpp.py` | MBPP entry point. |
| `agent_swebench.py` | SWE-bench entry point (also manages the Docker container lifecycle). |
| `mcp_tools_mbpp.py` | MCP server exposing `run_tests`. |
| `mcp_tools_swebench.py` | MCP server exposing `read_file`, `edit_file`, `list_files`, `search_code`, `search_function_or_class_definition_in_code`, `find_references`, `run_tests`, `get_patch`, `run_command`. |

For a worked example of one full run, see [EXECUTION_FLOW.md](EXECUTION_FLOW.md). For the reasoning behind the sandbox's security model, token limits, and code-extraction strategy, see [ALGORITHMS_EXPLAINED.md](ALGORITHMS_EXPLAINED.md).

## Sandbox security

Untrusted, LLM-generated code runs in a forked child process with:
- **Import allowlist** — only "safe" modules (`math`, `collections`, `itertools`, ...); `os`, `subprocess`, `socket`, `eval`, `exec` are blocked.
- **Path restrictions** — file access limited to configured directories (`/testbed`, `/tmp/agent` for SWE-bench).
- **Memory limit** — 512 MB by default (`resource.setrlimit`).
- **Time limit** — 30 seconds by default, enforced by the parent process, which kills the child on timeout.
- **No network access.**

The child can still call MCP tools (e.g. `run_tests`, `edit_file`) — calls are proxied over a pipe to the parent, which executes them and returns the result.

## Running the project

### Prerequisites
- Python 3.10, `uv`
- Docker (SWE-bench only)
- LLM API credentials

### Setup

```bash
uv sync
echo "OPENAI_API_KEY=sk-..." > .env
```

Credentials load from `.env` (override with `--env-file`). Provide multiple keys for rotation via `AGENT_SMITH_API_KEYS=key1,key2,key3`, or use provider-specific vars (`OPENAI_API_KEY`, etc.) — see [ALGORITHMS_EXPLAINED.md](ALGORITHMS_EXPLAINED.md#api-key-rotation) for the lookup order.

### MBPP

```bash
cd moulinette && uv run moulinette_eval dump mbpp --output ../cache/mbpp_task.json && cd ..
uv run python -m agent_mbpp \
  --task-file cache/mbpp_task.json --output cache/mbpp_solution.json \
  --model-name "provider/model" --provider-url "https://provider.example/v1"
cd moulinette && uv run moulinette_eval validate mbpp ../cache/mbpp_task.json ../cache/mbpp_solution.json && cd ..
```

### SWE-bench

```bash
cd moulinette && uv run moulinette_eval dump swebench --output ../cache/swebench_task.json && cd ..
uv run python -m agent_swebench \
  --task-file cache/swebench_task.json --output cache/swebench_solution.json \
  --model-name "provider/model" --provider-url "https://provider.example/v1"
```

The SWE-bench agent pulls the task's Docker image if missing, starts it network-isolated, routes all file/test operations through it, collects `git -c core.fileMode=false diff` as the solution, and stops the container afterward.

### CLI flags

Both entry points accept: `--task-file`, `--output`, `--model-name` (default `gpt-5.4-mini`), `--provider-url` (default `https://api.openai.com/v1`), `--max-iterations` (default 10), `--env-file` (default `.env`). MBPP also has `--max-output-tokens` (default 6000); the input-token budget is fixed at 6000 for MBPP and 300000/10000 (input/output) for SWE-bench.

### Makefile shortcuts

```bash
make install    # uv sync
make run        # interactive sandbox (uv run sandbox)
make mbpp       # run MBPP agent — override with TASK_FILE=, OUTPUT=, MODEL_NAME=, PROVIDER_URL=
make swebench   # run SWE-bench agent — same overrides, plus TASK_FILE_SWEBENCH=, OUTPUT_SWEBENCH=
make clean      # remove caches (__pycache__, .pytest_cache, .coverage, htmlcov)
make fclean     # clean + remove .venv and build artifacts
make re         # fclean + install
make help       # list targets
```

Defaults: `MODEL_NAME=~openai/gpt-astra-latest`, `PROVIDER_URL=https://openrouter.ai/api/v1`.

### Interactive sandbox

```bash
uv run sandbox
# > print("Hello")
# {"output":"Hello\n","error":null,"final_answer":null,"timed_out":false,"truncated":false}
# > exit
```

## Debugging with `solution.json`

```bash
jq '.success, .iterations, .total_time_seconds' solution.json
jq '.steps[].llm_output' solution.json        # what the LLM generated each step
jq '.steps[].sandbox_input' solution.json     # code that was executed
jq '.steps[].sandbox_output' solution.json    # execution results
jq '.total_input_tokens, .total_output_tokens' solution.json
jq '.error' solution.json                     # null if successful
```

Common failure modes:
- **"No valid code block was found"** — the LLM didn't output a recognized format; see `agent_smith/extract.py`.
- **"Import blocked by sandbox: X"** — expected behavior; the sandbox is doing its job.
- **`timed_out: true`** — code exceeded the execution time limit.
- **"Configured token limit reached"** — raise `--max-iterations`/`--max-output-tokens`, or the task needs a smaller prompt.
