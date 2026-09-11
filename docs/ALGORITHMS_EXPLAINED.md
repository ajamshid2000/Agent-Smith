# Agent Smith: Design Rationale

Why the core algorithms are built the way they are. For what each component does, see [GUIDE.md](GUIDE.md); for a live trace, see [EXECUTION_FLOW.md](EXECUTION_FLOW.md).

## Sandbox threat model

| Threat | Mitigation |
|---|---|
| Infinite loop hangs the agent | Process timeout (30s default), enforced by the parent polling the child every 50ms and killing it past the deadline. |
| `os.system(...)` / arbitrary shell access | Import allowlist replaces `__import__`; `os`, `subprocess`, `socket` are blocked. |
| Memory exhaustion | `resource.setrlimit(RLIMIT_AS, 512MB)` — kernel-enforced, can't be disabled from inside the child. |
| Path traversal (`open("/testbed/../../etc/passwd")`) | `Path(value).expanduser().resolve()` first, *then* check the resolved path is under an allowed directory. Resolving before checking is what defeats `..` and `~` — checking the raw string would let `/testbed/../../etc/passwd`'s parents fool a naive prefix match. |
| Network exfiltration | No socket/HTTP-capable modules are importable. |
| `eval`/`exec` escapes | Removed from the restricted builtins entirely. |

The three enforcement layers exist for different reasons: the process-timeout deadline lets the **parent** intervene regardless of what the child does; the memory `setrlimit` is **kernel**-enforced and can't be bypassed by the child; the 50ms poll loop keeps the parent responsive to tool-call messages while still watching the deadline.

## API key rotation

Keys are tried round-robin; on an HTTP error the client advances to the next key and retries, raising only once every key has failed once (`agent_smith/providers.py:complete`). Key discovery order: explicit `api_keys` argument → `AGENT_SMITH_API_KEYS` (comma-separated) → any environment variable containing `API_KEY` (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.). This means a single account experiencing a transient rate limit doesn't fail the whole run, and the same code works across providers without special-casing.

## MCP tool routing

The sandboxed child cannot call tools directly — it has no network or subprocess access. Instead, a call like `run_tests(code=...)` inside the child sends a `{"type": "tool", ...}` message over the pipe (see [SANDBOX_MESSAGE_PROTOCOL.md](SANDBOX_MESSAGE_PROTOCOL.md)); the **parent** process — which does have the MCP connection — executes it and returns the result. This keeps the tool implementations (temp files, Docker exec, subprocess calls) entirely out of the restricted process, so a compromised or buggy sandboxed script can't reach them directly.

## Code extraction order

`extract.py` tries formats in this order: markdown ` ```python ` blocks, then XML `<invoke>`, then JSON `<tool_call>`, then ReAct `Action:`/`Action Input:`. The order is chosen by specificity and frequency — markdown is what most OpenAI-compatible models emit and is the least ambiguous pattern to match; ReAct is checked last because its plain-text format is the easiest to false-positive on.

## Token budgets

MBPP: 6000 input tokens (fixed), output tokens capped by `--max-output-tokens` (default 6000), `--max-iterations` (default 10). SWE-bench: 300000 input / 10000 output, fixed — exploring a real repository (reading multiple files, running tests, iterating on a diff) needs far more context than implementing one function. The loop checks the running total before every request and stops early if a call would exceed the input budget, trading a possibly-incomplete answer for a bounded cost.

## Why OpenAI-compatible only

Standardizing on the `/v1/chat/completions` shape means switching between OpenAI, OpenRouter, Groq, or a local server is a matter of changing `--provider-url` and `--model-name` — no per-provider client code. The one adaptation needed: non-OpenAI endpoints get an explicit `stop: ["<end_code>"]` sequence appended, since some open models don't stop cleanly on their own after a code block.
