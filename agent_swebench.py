"""Command-line entry point for running Agent Smith on SWE-bench tasks.

The runner creates an isolated Docker container for the task repository,
bridges the container tools through MCP, and executes the shared reasoning
loop. The generated patch and per-step diagnostics are written to JSON after
the container is stopped.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from agent_smith.loop import AgentLoop
from agent_smith.mcp import MCPClient, tool_manual
from agent_smith.models import SWEBenchTaskInput
from agent_smith.providers import OpenAIProvider, load_env_file
from agent_smith.sandbox import Sandbox, SandboxConfig


def main() -> None:
    """Run one SWE-bench task inside an isolated Docker container.

    The task file supplies the repository image, issue description, hints, and
    evaluation script. This function ensures the image is available, starts a
    network-disabled container with a memory limit, and exposes repository
    operations through the configured MCP stdio server. The evaluation script
    is passed through ``EVAL_SCRIPT`` so that the sandbox's ``run_tests`` tool
    can execute the task-specific checks.

    Tool callbacks accept both keyword arguments and positional arguments. For
    positional calls, arguments are assigned according to the order of fields
    in each MCP tool schema. This keeps the bridge compatible with models that
    emit ordinary Python calls instead of keyword-only calls.

    After the agent finishes, the result is written to ``--output``. A run may
    still be promoted to success when its recorded steps contain both a passing
    test result and a non-empty git patch, even if the model omitted the final
    ``final_answer`` call. The container and temporary environment variables
    are cleaned up in all cases.

    Raises:
        SystemExit: Via ``argparse`` when the task file is missing or invalid,
            when Docker cannot prepare the task container, or when the agent
            does not produce a successful solution.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-file", default="cache/swebench_task.json")
    parser.add_argument("--output", default="cache/swebench_solution.json")
    parser.add_argument("--model-name", default="~openai/gpt-sol-latest")
    parser.add_argument("--provider-url", default="https://openrouter.ai/api/v1")
    parser.add_argument("--max-iterations", type=int, default=30)
    parser.add_argument("--request-interval-seconds", type=float, default=1.0)
    parser.add_argument("--mcp-stdio", default=f"{sys.executable} mcp_tools_swebench.py")
    parser.add_argument("--env-file", default=".env")
    args = parser.parse_args()
    load_env_file(args.env_file)
    task_path = Path(args.task_file)
    if not task_path.is_file():
        parser.error(f"task file not found: {task_path}. Dump one first with: cd moulinette && uv run moulinette_eval dump swebench --output ../{task_path}")
    try:
        task = SWEBenchTaskInput.model_validate_json(task_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        parser.error(f"invalid SWE-bench task file {task_path}: {error}")
    try:
        image_check = subprocess.run(
            ["docker", "image", "inspect", task.docker_image],
            capture_output=True,
            text=True,
            check=False,
        )
        if image_check.returncode != 0:
            print(f"Docker image not found locally; pulling {task.docker_image}...", file=sys.stderr)
            subprocess.run(["docker", "pull", task.docker_image], check=True)
        container = subprocess.run(
            ["docker", "run", "-d", "--rm", "--network", "none", "--memory", "512m", "--workdir", "/testbed", "--entrypoint", "tail", task.docker_image, "-f", "/dev/null"],
            capture_output=True,
            text=True,
            check=True,
        )
        container_id = container.stdout.strip()
    except (OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"unable to prepare or start Docker image {task.docker_image}: {error}\nCheck that Docker/Podman is running and that the image registry is reachable.\n")
    os.environ["AGENT_SMITH_CONTAINER_ID"] = container_id
    previous_eval_script = os.environ.get("EVAL_SCRIPT")
    os.environ["EVAL_SCRIPT"] = task.eval_script
    try:
        client = MCPClient(args.mcp_stdio)
        schemas = client.tools()

        def make_tool(schema: dict):
            """Build an MCP-backed Python callable from a tool schema."""
            name = schema["name"]
            parameter_names = list(schema.get("inputSchema", {}).get("properties", {}))

            def call(*values, **named):
                """Translate a model call into one structured MCP request."""
                if len(values) > len(parameter_names):
                    raise TypeError(f"{name}() takes at most {len(parameter_names)} positional arguments")
                arguments = dict(zip(parameter_names, values))
                arguments.update(named)
                return client.call(name, arguments)

            return call

        tools = {schema["name"]: make_tool(schema) for schema in schemas}
        provider = OpenAIProvider(args.model_name, args.provider_url)
        sandbox = Sandbox(SandboxConfig(max_execution_time_seconds=30, allowed_directories=["/testbed", "/tmp/agent"]), tools)
        prompt = f"Instance: {task.instance_id}\nRepository: {task.repo}\nProblem statement:\n{task.problem_statement}\nHints:\n{task.hints_text}\nEvaluation script:\n{task.eval_script}\nExplore the repository, edit the bug, run focused tests, then call final_answer(get_patch())."
        solution = AgentLoop(provider, sandbox, "swebench", args.max_iterations, 300000, 10000, args.request_interval_seconds).run(task.instance_id, prompt, tool_manual(schemas))
    finally:
        if "client" in locals():
            client.close()
        os.environ.pop("AGENT_SMITH_CONTAINER_ID", None)
        if previous_eval_script is None:
            os.environ.pop("EVAL_SCRIPT", None)
        else:
            os.environ["EVAL_SCRIPT"] = previous_eval_script
        subprocess.run(["docker", "stop", "-t", "5", container_id], capture_output=True, check=False)
    if not solution.success:
        passed_tests = any(
            "exit_code=0" in step.sandbox_output and "passed" in step.sandbox_output
            for step in solution.steps
        )
        patches = [
            step.sandbox_output[step.sandbox_output.index("diff --git "):].split("\nstderr=", 1)[0]
            for step in solution.steps
            if "diff --git " in step.sandbox_output
        ]
        if passed_tests and patches:
            solution = solution.model_copy(update={
                "success": True,
                "solution": patches[-1],
                "error": None,
            })
    with open(args.output, "w", encoding="utf-8") as output:
        output.write(solution.model_dump_json(indent=2))
    if not solution.success:
        parser.exit(1, f"agent failed: {solution.error or 'no final answer was produced'}\n")


if __name__ == "__main__":
    main()
