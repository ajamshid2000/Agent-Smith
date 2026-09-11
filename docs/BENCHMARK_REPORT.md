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


## Still to measure

- **SWE-bench traces**: no completed run is available yet; the agent's patch-edit and test-failure-recovery behavior is unmeasured.
- **Ablation study**: a controlled before/after comparison (same task, model, and provider; one factor changed — system prompt, tools, or token limits) has not been run.
- **Groq `qwen/qwen3.8-27b` retry**: rerun with an output-token limit at or below the account's 1000-token OTPM quota to get an actual pass/fail instead of a provider-side rejection.
