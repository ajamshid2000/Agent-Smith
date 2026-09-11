# Model Benchmark Report

This report summarizes the Agent Smith traces currently available in the
repository. The measured runs are MBPP runs; no completed SWE-bench trace is
available in the supplied artifacts.

## Setup

### Benchmark task

The primary task used in the current comparison is MBPP task `96`:

```json
{
  "task_id": 96,
  "task_definition": "Write a python function to find the number of divisors of a given integer.",
  "function_definition": "def divisor(n):",
  "test_imports": [],
  "test_list": [
    "assert divisor(12) == 6",
    "assert divisor(9) == 3"
  ]
}
```

An earlier OpenAI trace used MBPP task `282`, so it is reported separately and
is not treated as a controlled comparison with task `96`.

### Runtime

- Agent: Agent Smith MBPP loop
- Maximum iterations: 10
- Input-token budget: 6000
- Output-token budget: 1500 per request, bounded by the remaining budget
- Evaluation path: the agent's `run_tests` tool followed by `final_answer`
- Correctness status below is the `success` field in each `solution.json`

## Results

| Provider | Model | Task | Result | Iterations | Requests | Input tokens | Output tokens | Time (s) |
|---|---|---:|---|---:|---:|---:|---:|---:|
| OpenRouter | `deepseek/deepseek-v4.1-flash` | 96 | Pass | 1 | 1 | 366 | 1192 | 5.63 |
| Groq | `openai/gpt-oss-120b` | 96 | Pass | 1 | 2 | 397 | 600 | 2.44 |
| OpenAI | `gpt-5.4-mini` | 282 | Pass | 1 | 1 | 375 | 164 | 1.70 |
| Groq | `qwen/qwen3.8-27b` | 96 | Unavailable | 0 | 0 | 0 | 0 | n/a |

### Observations

- OpenRouter completed task `96` in one iteration without a retry.
- Groq `openai/gpt-oss-120b` completed task `96` after one retry; its recorded
  step had one retry, giving two total requests.
- The OpenAI trace completed task `282` in one iteration with the lowest output
  token count among the successful traces. This indicates trace efficiency for
  that task, not better correctness, because it used a different task.
- The Groq Qwen run did not reach the model. Groq rejected the request with
  HTTP 429 because its output-token-per-minute limit was 1000 while the agent
  requested 1500. This is a provider quota/configuration failure, not a failed
  MBPP solution.

## Provider Reliability

| Provider/model | Successful traces | Retry behavior | Recorded request time |
|---|---:|---|---:|
| OpenRouter / `deepseek/deepseek-v4.1-flash` | 1/1 | 0 retries | 5.59 s |
| Groq / `openai/gpt-oss-120b` | 1/1 | 1 retry | 2.40 s |
| OpenAI / `gpt-5.4-mini` | 1/1 | 0 retries | 1.65 s |
| Groq / `qwen/qwen3.8-27b` | 0/1 | Rejected before iteration | n/a |

The reliability sample is too small for production conclusions. The Qwen
failure should be rerun with a lower request output limit or a higher Groq
quota before judging that model's coding ability.

## Intermediary Metrics

The supplied traces contain no SWE-bench patch-edit trace and no failed-test
recovery iteration. Therefore:

- First final-patch read/edit: not measured
- First test-failure reduction: not measured
- MBPP tool execution: present in all three successful traces
- Successful traces requiring multiple reasoning iterations: none

## Ablation Study

No controlled ablation was supplied. The available runs vary by provider,
model, task, and sometimes retry history, so they cannot establish the effect
of changing the system prompt, tools, or token parameters. A valid ablation
would hold the task, model, provider, prompt, and token limits constant while
changing exactly one factor.

## Conclusions

All three completed MBPP traces passed their available task tests. Groq
`openai/gpt-oss-120b` used fewer output tokens than OpenRouter on task `96`,
while OpenAI `gpt-5.4-mini` used the fewest tokens on a different task. Token
count measures generation length, not solution quality. These are directional
results, not a model ranking, because the sample is small and the tasks differ.

Before selecting a final model, run the same set of MBPP tasks for every model,
record correctness using Moulinette validation, and repeat the Groq Qwen run
with an output limit compatible with the account's 1000-token OTPM quota.

## Historical Raw Trace

The original command output and serialized trace are retained below for auditability.

## Setup
{
  "task_id": 96,
  "task_definition": "Write a python function to find the number of divisors of a given integer.",
  "function_definition": "def divisor(n):",
  "test_imports": [],
  "test_list": [
    "assert divisor(12) == 6",
    "assert divisor(9) == 3"
  ]
}


| Model/provider | Tasks | Selection reason |
|---|---|---|
| To be measured | Three SWE-bench tasks | Representative bug-fixing tasks |

## Results

uv run python -m agent_mbpp \
	--task-file task.json \
	--output solution.json \
	--model-name "qwen/qwen3.8-27b" \
	--provider-url "https://api.groq.com/openai/v1"
agent failed: LLM request failed after token rotation: HTTP 429: {"error":{"message":"Request too large for model `qwen/qwen3.8-27b` in organization `org_01m27ydszke1ptnq3qbcq8rd7f` service tier `on_demand` on output tokens per minute (OTPM): Limit 1000, Requested 1500. The request's expected output tokens exceed the enforced limit; reduce max_tokens (or the request's expected output) and try again. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing","type":"tokens","code":"rate_limit_exceeded"}}


{
  "task_id": "96",
  "benchmark": "mbpp",
  "success": true,
  "solution": "def divisor(n):\n    \"\"\"Return the number of positive divisors of integer n.\"\"\"\n    if n <= 0:\n        return 0\n    count = 0\n    i = 1\n    while i * i <= n:\n        if n % i == 0:\n            count += 1\n            if i != n // i:\n                count += 1\n        i += 1\n    return count\n",
  "iterations": 1,
  "total_requests": 2,
  "total_input_tokens": 397,
  "total_output_tokens": 600,
  "total_time_seconds": 2.4412279441021383,
  "steps": [
    {
      "step": 1,
      "input_tokens": 397,
      "output_tokens": 600,
      "request_time_ms": 2397.3483671434224,
      "timestamp": "2026-09-11T12:51:55.306576",
      "api_url": "https://api.groq.com/openai/v1",
      "model_name": "openai/gpt-oss-120b",
      "llm_output": "```python\ndef divisor(n):\n    \"\"\"Return the number of positive divisors of integer n.\"\"\"\n    if n <= 0:\n        return 0\n    count = 0\n    i = 1\n    while i * i <= n:\n        if n % i == 0:\n            count += 1\n            if i != n // i:\n                count += 1\n        i += 1\n    return count\n\n# Run the provided tests\nrun_tests(\n    code=(\n        \"def divisor(n):\\n\"\n        \"    \\\"\\\"\\\"Return the number of positive divisors of integer n.\\\"\\\"\\\"\\n\"\n        \"    if n <= 0:\\n\"\n        \"        return 0\\n\"\n        \"    count = 0\\n\"\n        \"    i = 1\\n\"\n        \"    while i * i <= n:\\n\"\n        \"        if n % i == 0:\\n\"\n        \"            count += 1\\n\"\n        \"            if i != n // i:\\n\"\n        \"                count += 1\\n\"\n        \"        i += 1\\n\"\n        \"    return count\\n\"\n    ),\n    test_imports=[],\n    test_list=[\n        \"assert divisor(12) == 6\",\n        \"assert divisor(9) == 3\"\n    ]\n)\n\n# If tests pass, return the solution\nfinal_answer(\n    \"def divisor(n):\\n\"\n    \"    \\\"\\\"\\\"Return the number of positive divisors of integer n.\\\"\\\"\\\"\\n\"\n    \"    if n <= 0:\\n\"\n    \"        return 0\\n\"\n    \"    count = 0\\n\"\n    \"    i = 1\\n\"\n    \"    while i * i <= n:\\n\"\n    \"        if n % i == 0:\\n\"\n    \"            count += 1\\n\"\n    \"            if i != n // i:\\n\"\n    \"                count += 1\\n\"\n    \"        i += 1\\n\"\n    \"    return count\\n\"\n)\n```",
      "sandbox_input": "def divisor(n):\n    \"\"\"Return the number of positive divisors of integer n.\"\"\"\n    if n <= 0:\n        return 0\n    count = 0\n    i = 1\n    while i * i <= n:\n        if n % i == 0:\n            count += 1\n            if i != n // i:\n                count += 1\n        i += 1\n    return count\n\n# Run the provided tests\nrun_tests(\n    code=(\n        \"def divisor(n):\\n\"\n        \"    \\\"\\\"\\\"Return the number of positive divisors of integer n.\\\"\\\"\\\"\\n\"\n        \"    if n <= 0:\\n\"\n        \"        return 0\\n\"\n        \"    count = 0\\n\"\n        \"    i = 1\\n\"\n        \"    while i * i <= n:\\n\"\n        \"        if n % i == 0:\\n\"\n        \"            count += 1\\n\"\n        \"            if i != n // i:\\n\"\n        \"                count += 1\\n\"\n        \"        i += 1\\n\"\n        \"    return count\\n\"\n    ),\n    test_imports=[],\n    test_list=[\n        \"assert divisor(12) == 6\",\n        \"assert divisor(9) == 3\"\n    ]\n)\n\n# If tests pass, return the solution\nfinal_answer(\n    \"def divisor(n):\\n\"\n    \"    \\\"\\\"\\\"Return the number of positive divisors of integer n.\\\"\\\"\\\"\\n\"\n    \"    if n <= 0:\\n\"\n    \"        return 0\\n\"\n    \"    count = 0\\n\"\n    \"    i = 1\\n\"\n    \"    while i * i <= n:\\n\"\n    \"        if n % i == 0:\\n\"\n    \"            count += 1\\n\"\n    \"            if i != n // i:\\n\"\n    \"                count += 1\\n\"\n    \"        i += 1\\n\"\n    \"    return count\\n\"\n)",
      "sandbox_output": "",
      "retries": 1
    }
  ],
  "system_prompt": "You are Agent Smith. Solve the coding task through a Thought -> Code -> Observation loop.\nAvailable tools are Python functions described below. Write one executable Python code block per turn.\nUse the tools to inspect the task, edit only what is needed, and run tests. Never fetch patches or solutions\nfrom external sources. When the task is solved, call final_answer(solution), where solution is MBPP function\ncode or the SWE-bench git diff. If code is missing or malformed, the sandbox will report that explicitly.\n\nAvailable MCP tools are callable Python functions:\n- run_tests: Execute the MBPP candidate against its tests.; parameters: {\"type\": \"object\", \"properties\": {\"code\": {\"type\": \"string\"}, \"test_imports\": {\"type\": \"array\", \"items\": {\"type\": \"string\"}}, \"test_list\": {\"type\": \"array\", \"items\": {\"type\": \"string\"}}}, \"required\": [\"code\", \"test_list\"]}\n",
  "error": null,
  "timestamp": "2026-09-11T12:51:55.306606"
}





| Model | Task | Pass/Fail | Iterations | Input tokens | Output tokens | Wall-clock time |
|---|---|---:|---:|---:|---:|---:|
| To be measured | To be measured | - | - | - | - | - |

## Provider Reliability

To be populated from `solution.json` step metrics: average request time, retries, and availability.

## Intermediary Metrics

The step of first reading or editing the final-patch file and the step of first reducing test failures are recorded from each solution trace.

## Ablation Study

A before/after comparison of the system prompt, tools, or parameters is recorded after the same tasks are run with the same model.

## Conclusions

The final model selection is based on pass rate, token usage, iteration efficiency, and provider reliability.