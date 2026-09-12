# Agent Smith

Agent Smith is a Python 3.10 agent framework using a Thought -> Code -> Observation loop, a configurable subprocess sandbox, and MCP tools. It targets two benchmarks: MBPP (function-level coding problems) and SWE-bench (real repository bug fixes, run inside Docker).

```sh
uv sync
uv run sandbox              # interactive sandbox
uv run python -m agent_mbpp
uv run python -m agent_swebench
```

The default provider is OpenAI with model `gpt-5.4-mini` and API base URL
`https://api.openai.com/v1`. Override them when using another compatible provider:

```sh
uv run python -m agent_mbpp --task-file cache/mbpp_task.json --output cache/mbpp_solution.json \
	--model-name "provider/model" --provider-url "https://provider.example/v1"
```

The MBPP agent reads `cache/mbpp_task.json` by default; the SWE-bench agent reads
`cache/swebench_task.json` by default. Both write their `solution.json` next to it unless overridden. `make mbpp`/`make swebench` wrap the same commands with `TASK_FILE=`/`OUTPUT=`/`MODEL_NAME=`/`PROVIDER_URL=` overrides — see `make help`.

Set provider credentials through environment variables. Multiple comma-separated keys may be supplied with `AGENT_SMITH_API_KEYS`; provider-specific `*_API_KEY` variables are also discovered. The agents load `.env` by default; use `--env-file` to select another file. The agent never embeds credentials in source code.

For moulinette evaluation:

```sh
systemctl --user start podman.socket
systemctl --user status podman.socket
docker version
cd moulinette
uv run moulinette_eval dump mbpp --output ../cache/mbpp_task.json
cd ..
uv run python -m agent_mbpp --task-file cache/mbpp_task.json --output cache/mbpp_solution.json \
	--model-name "model/name" --provider-url "https://provider.api/v1"
cd moulinette
uv run moulinette_eval validate mbpp ../cache/mbpp_task.json ../cache/mbpp_solution.json
```

The SWE-bench agent starts the task's Docker image, routes MCP file and test operations into that container, collects `git -c core.fileMode=false diff`, and stops the container after producing `solution.json`.

## Documentation

- **[docs/GUIDE.md](docs/GUIDE.md)** — architecture, core components, sandbox security model, full CLI/Makefile reference, and debugging `solution.json`.
- **[docs/EXECUTION_FLOW.md](docs/EXECUTION_FLOW.md)** — step-by-step trace of one MBPP run, with the exact prompts and messages exchanged, plus SWE-bench differences.
- **[docs/ALGORITHMS_EXPLAINED.md](docs/ALGORITHMS_EXPLAINED.md)** — design rationale: sandbox threat model, API key rotation, MCP tool routing, code-extraction order, token budgets.
- **[docs/MCP_JSON_RPC.md](docs/MCP_JSON_RPC.md)** — JSON-RPC message formats used between the agent and the MCP tool servers.
- **[docs/SANDBOX_MESSAGE_PROTOCOL.md](docs/SANDBOX_MESSAGE_PROTOCOL.md)** — the pipe-based message protocol between the sandboxed child process and its parent.
- **[docs/BENCHMARK_REPORT.md](docs/BENCHMARK_REPORT.md)** — model/provider comparison from available traces.
