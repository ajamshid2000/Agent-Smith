# Agent Smith

Agent Smith is a Python 3.10 agent framework using a Thought -> Code -> Observation loop, a configurable subprocess sandbox, and MCP tools.

```sh
uv run sandbox
uv run python -m agent_mbpp
uv run python -m agent_swebench
```

The default provider is OpenAI with model `gpt-5.4-mini` and API base URL
`https://api.openai.com/v1`. Override them when using another compatible provider:

The MBPP agent reads `task.json` by default; the SWE-bench agent reads
`swebench_task.json` by default. Both write `solution.json` unless overridden.

```sh
uv run python -m agent_mbpp --task-file task.json --output solution.json \
	--model-name "provider/model" --provider-url "https://provider.example/v1"
```

Set provider credentials through environment variables. Multiple comma-separated keys may be supplied with `AGENT_SMITH_API_KEYS`; provider-specific `*_API_KEY` variables are also discovered. The agents load `.env` by default; use `--env-file` to select another file. The agent never embeds credentials in source code.

For moulinette evaluation:

```sh
cd moulinette
uv run moulinette_eval dump mbpp --output ../task.json
cd ..
uv run python -m agent_mbpp --task-file task.json --output solution.json \
	--model-name "model/name" --provider-url "https://provider.api/v1"
cd moulinette
uv run moulinette_eval validate mbpp ../task.json ../solution.json
```

The SWE-bench agent starts the task's Docker image, routes MCP file and test operations into that container, collects `git -c core.fileMode=false diff`, and stops the container after producing `solution.json`.