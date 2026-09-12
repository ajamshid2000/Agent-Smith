"""Command-line entry point for running Agent Smith on MBPP tasks.

The module loads a serialized MBPP task, exposes the benchmark's test tool to
the sandbox, and runs the shared :class:`agent_smith.loop.AgentLoop`. The
result is persisted as JSON so that benchmark runs can be inspected or
evaluated later.
"""

import argparse
import json
from pathlib import Path
import sys

from agent_smith.loop import AgentLoop
from agent_smith.mcp import MCPClient, tool_manual
from agent_smith.models import MBPPTaskInput
from agent_smith.providers import OpenAIProvider, load_env_file
from agent_smith.sandbox import Sandbox, SandboxConfig


def _content_text(content: object) -> str:
    """Flatten an MCP response into the text consumed by the fallback check.

    MCP clients normally return a list of content objects, each of which may
    contain a ``text`` field. This helper joins those fields while accepting a
    scalar response as well, keeping the fallback path tolerant of both the
    JSON-RPC response shape and direct test-tool return values.

    Args:
        content: An MCP content list, a single response value, or any object
            returned by the MBPP test tool.

    Returns:
        The response represented as a single string. Non-dictionary list
        entries are ignored because they do not provide textual MCP content.
    """
    if isinstance(content, list):
        return "\n".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
    return str(content)


def main() -> None:
    """Run one MBPP task from the command line.

    The command reads and validates the task file, starts the local MCP server
    that executes MBPP tests, and configures a bounded agent loop with the
    selected model provider. A successful agent normally calls
    ``final_answer`` itself. If it stops after producing only a function
    definition, this function performs one final test and promotes that
    candidate when it passes.

    Command-line options control the task and output paths, model endpoint,
    iteration limit, output-token budget, and environment file. The serialized
    :class:`agent_smith.models.SolutionOutput` is written to ``--output`` even
    when the agent fails; failures then terminate the process with status 1.

    Raises:
        SystemExit: Via ``argparse`` when the task file is missing or invalid,
            or when the agent does not produce a successful solution.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-file", default="cache/mbpp_task.json")
    parser.add_argument("--output", default="cache/mbpp_solution.json")
    parser.add_argument("--model-name", default="~openai/gpt-sol-latest")
    parser.add_argument("--provider-url", default="https://openrouter.ai/api/v1")
    parser.add_argument("--max-iterations", type=int, default=10)
    parser.add_argument("--max-output-tokens", type=int, default=6000)
    parser.add_argument("--env-file", default=".env")
    args = parser.parse_args()
    load_env_file(args.env_file)
    task_path = Path(args.task_file)
    if not task_path.is_file():
        parser.error(f"task file not found: {task_path}. Dump one first with: cd moulinette && uv run moulinette_eval dump mbpp --output ../cache/{task_path}")
    try:
        task = MBPPTaskInput.model_validate_json(task_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        parser.error(f"invalid MBPP task file {task_path}: {error}")
    client = MCPClient(f"{sys.executable} mcp_tools_mbpp.py")
    try:
        schemas = client.tools()
        tools = {schema["name"]: (lambda *values, _name=schema["name"], **named: client.call(_name, dict(named))) for schema in schemas}
        provider = OpenAIProvider(args.model_name, args.provider_url)
        sandbox = Sandbox(SandboxConfig(max_execution_time_seconds=30), tools)
        prompt = f"Task: {task.task_definition}\nFunction signature: {task.function_definition}\nTests: {task.test_list}\nWrite the implementation. In the same Python code block, call run_tests(code=<your complete function code>, test_imports={task.test_imports!r}, test_list={task.test_list!r}). If the tests pass, immediately call final_answer(<your complete function code as a string>). Never return only a function definition; the final line must call final_answer."
        solution = AgentLoop(provider, sandbox, "mbpp", args.max_iterations, 6000, args.max_output_tokens).run(str(task.task_id), prompt, tool_manual(schemas))
        if not solution.success and solution.steps:
            candidate = solution.steps[-1].sandbox_input.strip()
            if candidate.startswith("def "):
                test_result = _content_text(tools["run_tests"](code=candidate, test_imports=task.test_imports, test_list=task.test_list))
                if "exit_code=0" in test_result:
                    solution = solution.model_copy(update={"success": True, "solution": candidate, "error": None})
    finally:
        client.close()
    with open(args.output, "w", encoding="utf-8") as output:
        output.write(solution.model_dump_json(indent=2))
    if not solution.success:
        parser.exit(1, f"agent failed: {solution.error or 'no final answer was produced'}\n")


if __name__ == "__main__":
    main()
