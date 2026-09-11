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
    """Run the SWE-bench agent in a task-specific Docker container."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-file", default="cache/swebench_task.json")
    parser.add_argument("--output", default="cache/swebench_solution.json")
    parser.add_argument("--model-name", default="gpt-5.4-mini")
    parser.add_argument("--provider-url", default="https://api.openai.com/v1")
    parser.add_argument("--max-iterations", type=int, default=10)
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
    try:
        client = MCPClient(args.mcp_stdio)
        schemas = client.tools()
        tools = {schema["name"]: (lambda *values, _name=schema["name"], **named: client.call(_name, dict(named))) for schema in schemas}
        provider = OpenAIProvider(args.model_name, args.provider_url)
        sandbox = Sandbox(SandboxConfig(max_execution_time_seconds=30, allowed_directories=["/testbed", "/tmp/agent"]), tools)
        prompt = f"Instance: {task.instance_id}\nRepository: {task.repo}\nProblem statement:\n{task.problem_statement}\nHints:\n{task.hints_text}\nEvaluation script:\n{task.eval_script}\nExplore the repository, edit the bug, run focused tests, then call final_answer(get_patch())."
        solution = AgentLoop(provider, sandbox, "swebench", args.max_iterations, 300000, 10000).run(task.instance_id, prompt, tool_manual(schemas))
    finally:
        if "client" in locals():
            client.close()
        os.environ.pop("AGENT_SMITH_CONTAINER_ID", None)
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