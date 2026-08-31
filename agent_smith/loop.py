"""
Core reasoning loop: Thought → Code → Observation

This is the HEART of Agent Smith.
It implements the main algorithm that makes the agent intelligent.

Algorithm:
  1. Start with task description as observation
  2. Loop up to max_iterations times:
     a. Send (system_prompt + observation) to LLM
     b. Extract Python code from LLM response
     c. Execute code in sandbox
     d. If code calls final_answer(), stop and return solution
     e. Otherwise, update observation with execution result and go to step 2

WHY THIS WORKS?
- LLM gets feedback (observation) from each execution
- LLM learns from failures and improves
- Similar to how humans solve problems: try → observe → adjust
"""

import time
from typing import Callable

from .extract import extract_code, extract_final_answer
from .models import SolutionOutput, StepMetrics
from .providers import OpenAIProvider
from .sandbox import Sandbox


SYSTEM_PROMPT = """You are Agent Smith. Solve the coding task through a Thought -> Code -> Observation loop.
Available tools are Python functions described below. Write one executable Python code block per turn.
Use the tools to inspect the task, edit only what is needed, and run tests. Never fetch patches or solutions
from external sources. When the task is solved, call final_answer(solution), where solution is MBPP function
code or the SWE-bench git diff. If code is missing or malformed, the sandbox will report that explicitly.

{manual}
"""


class AgentLoop:
    """
    Main reasoning loop that orchestrates the Thought → Code → Observation cycle.
    
    WHY A CLASS?
    - Stores configuration (provider, sandbox, limits)
    - Can run multiple tasks with same configuration
    - Keeps code organized and testable
    
    Configuration:
        provider: LLM client (OpenAI, Claude, etc.)
        sandbox: Restricted code execution environment
        benchmark: "mbpp" or "swebench" (affects how we interpret success)
        max_iterations: Stop after this many attempts (prevent infinite loops)
        max_input_tokens: Stop if input tokens exceed this (cost/safety)
        max_output_tokens: Stop if output tokens exceed this (cost/safety)
    """
    
    def __init__(self, provider: OpenAIProvider, sandbox: Sandbox, benchmark: str, max_iterations: int, max_input_tokens: int, max_output_tokens: int):
        """Configure an agent loop with benchmark-specific iteration and token limits."""
        self.provider = provider
        self.sandbox = sandbox
        self.benchmark = benchmark
        self.max_iterations = max_iterations
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens

    def run(self, task_id: str, task_prompt: str, manual: str) -> SolutionOutput:
        """
        Run Thought → Code → Observation iterations until an answer is produced.
        
        HOW IT WORKS:
        1. Build system prompt by injecting available tools
        2. Initialize observation with the task
        3. Loop: send to LLM → extract code → execute → check if done
        4. Return detailed results including all steps
        
        Args:
            task_id: Unique identifier for tracking
            task_prompt: Initial task description
            manual: Description of available MCP tools (generated from schemas)
            
        Returns:
            SolutionOutput with success status, solution, and detailed metrics
        """
        system_prompt = SYSTEM_PROMPT.format(manual=manual)
        observation = task_prompt  # Start with just the task description
        steps: list[StepMetrics] = []
        total_input = total_output = 0
        started = time.perf_counter()
        answer = ""
        error = None
        
        # MAIN LOOP: Iterate until success, failure, or limit reached
        for iteration in range(1, self.max_iterations + 1):
            # CHECK TOKEN LIMITS (safety mechanism)
            remaining_input = self.max_input_tokens - total_input
            remaining_output = self.max_output_tokens - total_output
            if remaining_input <= 0 or remaining_output <= 0:
                error = "Configured token limit reached"
                break  # Stop if we're out of tokens
            
            try:
                # STEP 1: THOUGHT - Get LLM to think about the problem
                # Send: current observation (task + previous results)
                # Receive: model's reasoning and code
                # max_tokens = min(remaining, 1500) ensures we don't exceed limits
                completion = self.provider.complete(system_prompt, observation, min(remaining_output, 1500))
                total_input += completion.input_tokens
                total_output += completion.output_tokens
                
                # STEP 2: CODE - Extract executable Python from LLM response
                # LLM might output markdown code blocks, XML, JSON, etc.
                # extract_code normalizes all formats to executable Python
                code, extraction = extract_code(completion.text)
                
                # STEP 3: OBSERVATION - Execute the code and see what happens
                # Sandbox runs code with security restrictions
                # If code calls final_answer(), sandbox captures that
                execution = self.sandbox.execute(code)
                sandbox_output = execution.error or execution.output
                if execution.timed_out:
                    sandbox_output = execution.error or "Sandbox execution timed out; output may be partial"
                
                # RECORD THIS STEP for reproducibility and analysis
                steps.append(StepMetrics(
                    step=iteration,
                    input_tokens=completion.input_tokens,
                    output_tokens=completion.output_tokens,
                    request_time_ms=completion.request_time_ms,
                    api_url=self.provider.provider_url,
                    model_name=self.provider.model_name,
                    llm_output=completion.text,  # Exact LLM response
                    sandbox_input=code,  # Exact code executed
                    sandbox_output=sandbox_output,  # Exact output
                    retries=completion.retries  # API key rotations needed
                ))
                
                # CHECK IF DONE: Did code call final_answer()?
                if execution.final_answer is not None:
                    answer = execution.final_answer  # Capture the solution
                    break  # Exit loop successfully
                
                # NOT DONE YET: Build new observation with feedback
                # This is the key to learning: LLM sees its code, the result, and errors
                # Example observation:
                #   "Task context: Implement Fibonacci
                #    Previous step 1 result:
                #    Extraction: python code block
                #    Observation:
                #    exit_code=1
                #    stderr: AssertionError: expected 5, got 3"
                observation = f"Task context:\n{task_prompt}\n\nPrevious step {iteration} result:\nExtraction: {extraction}\nObservation:\n{sandbox_output}"
                
            except Exception as exc:
                # EXCEPTION HANDLING: If something crashes, record it and stop
                error = str(exc)
                break
        
        # CALCULATE FINAL METRICS
        total_requests = sum(1 + step.retries for step in steps)  # 1 initial + retries
        
        # RETURN COMPLETE SOLUTION RECORD
        return SolutionOutput(
            task_id=task_id,
            benchmark=self.benchmark,
            success=bool(answer) and error is None,  # Success: got answer AND no exception
            solution=answer,
            system_prompt=system_prompt,
            iterations=len(steps),
            total_requests=total_requests,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_time_seconds=time.perf_counter() - started,
            steps=steps,
            error=error
        )