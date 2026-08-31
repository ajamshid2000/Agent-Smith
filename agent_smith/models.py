"""
Data models for Agent Smith using Pydantic for validation.

WHY PYDANTIC?
- Automatic type validation (ensures data is correct shape)
- Automatic JSON serialization/deserialization
- Documentation via field descriptions
- Prevents bugs from malformed input

These models represent:
1. Input: What the agent receives (tasks to solve)
2. Output: What the agent produces (solutions)
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class MBPPTaskInput(BaseModel):
    """
    Input for MBPP (Mostly Basic Programming Problems) agent.
    
    WHY SEPARATE CLASSES?
    - MBPP has different structure than SWE-bench
    - MBPP is simpler: just function definition + tests
    - Separate models enforce type safety
    
    Attributes:
        task_id: Unique identifier for this problem
        task_definition: English description of what to implement
        function_definition: Python function signature (e.g., "def factorial(n):")
        test_imports: Modules to import before running tests (e.g., ["math"])
        test_list: Actual test assertions (e.g., ["assert factorial(5) == 120"])
    """
    task_id: int
    task_definition: str
    function_definition: str
    test_imports: List[str] = Field(default_factory=list)
    test_list: List[str] = Field(default_factory=list)


class SWEBenchTaskInput(BaseModel):
    """
    Input for SWE-bench (Software Engineering benchmark) agent.
    
    WHY DIFFERENT FROM MBPP?
    - Real open-source repos with complex codebases
    - Needs Docker container for isolated execution
    - Requires evaluation script (not simple assertions)
    - May have hints about where to look
    
    Attributes:
        instance_id: Unique identifier like "django/django-12345"
        problem_statement: Description of the bug to fix
        docker_image: Container image with the repo (e.g., "swebench/django:latest")
        eval_script: Command to run evaluation (e.g., "python -m pytest tests/test_bug.py")
        hints_text: Optional hints about where the bug might be
        repo: Repository name (e.g., "django", "numpy", "requests")
    """
    instance_id: str
    problem_statement: str
    docker_image: str
    eval_script: str
    hints_text: str = ""
    repo: str = ""


class StepMetrics(BaseModel):
    """
    Metrics for ONE iteration of the Thought → Code → Observation loop.
    
    WHY DETAILED METRICS?
    - Reproducibility: Can replay entire agent execution
    - Debugging: See what went wrong and when
    - Cost analysis: How many tokens per iteration?
    - Performance analysis: Which steps took longest?
    
    Attributes:
        step: Iteration number (1, 2, 3, ...)
        input_tokens: Tokens in LLM request (cost-related)
        output_tokens: Tokens in LLM response (cost-related)
        request_time_ms: API response time in milliseconds
        timestamp: When this step ran
        api_url: Which LLM provider was used
        model_name: Which model (gpt-4, claude, etc.)
        llm_output: Exact response from LLM (may be long)
        sandbox_input: Exact code that was executed
        sandbox_output: Output/errors from execution
        retries: How many API key rotations needed
    """
    step: int
    input_tokens: int
    output_tokens: int
    request_time_ms: float
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    api_url: str = ""
    model_name: str = ""
    llm_output: str = ""
    sandbox_input: str = ""
    sandbox_output: str = ""
    retries: int = 0


class SolutionOutput(BaseModel):
    """
    Final output from agent containing solution and all execution traces.
    
    WHY SAVE ALL DETAILS?
    - Can analyze why agent succeeded or failed
    - Can calculate total cost (tokens * model pricing)
    - Can identify bottlenecks (slow steps, many iterations)
    - Can reproduce the exact execution
    
    Attributes:
        task_id: Which task was solved
        benchmark: "mbpp" or "swebench"
        success: Did the agent solve it?
        solution: The final answer (function code or git diff)
        iterations: How many attempts before success/failure
        total_requests: Total API calls (including retries)
        total_input_tokens: Sum of all input tokens (for cost)
        total_output_tokens: Sum of all output tokens (for cost)
        total_time_seconds: Wall-clock time from start to finish
        steps: Detailed metrics for each iteration
        system_prompt: The exact system prompt sent to LLM
        error: Error message if something went wrong
        timestamp: When the execution started
    """
    task_id: str
    benchmark: str
    success: bool
    solution: str
    iterations: int
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_time_seconds: float
    steps: List[StepMetrics] = Field(default_factory=list)
    system_prompt: str = ""
    error: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())