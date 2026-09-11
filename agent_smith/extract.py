"""
Extract code from LLM responses.

CHALLENGE: LLMs output code in different formats
- Some wrap in markdown: ```python code ```
- Some use XML: <invoke name="func">
- Some use JSON: {"name": "func"}
- Some use ReAct: Action: func\nAction Input: ...

SOLUTION: Try each format in order until one matches
This normalizes all formats to executable Python.
"""

import json
import re
from typing import Optional


def _tool_call(name: str, arguments: object) -> str:
    """
    Convert a structured tool call into executable Python.
    
    WHY THIS FUNCTION?
    - XML/JSON/ReAct formats describe tool calls structurally
    - We need executable Python, so convert to function call
    
    Example:
        Input: name="run_tests", arguments={"code": "def f(): pass", ...}
        Output: 'result = run_tests(code="def f(): pass", ...)'
    
    Args:
        name: Function/tool name
        arguments: Dict of parameters or JSON string representation
        
    Returns:
        Executable Python function call as string
    """
    # NORMALIZE ARGUMENTS to dict
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            arguments = {}
    arguments = arguments if isinstance(arguments, dict) else {}
    
    # BUILD function call syntax
    values = ", ".join(f"{key}={value!r}" for key, value in arguments.items())
    return f"result = {name}({values})"


def extract_code(response: str) -> tuple[str, str]:
    """
    Extract Python or tool-call code from LLM response.
    
    STRATEGY: Try formats in order of likelihood
    1. Markdown code blocks (most common for Python)
    2. XML tool calls (Claude format)
    3. JSON tool calls (Hermes format)
    4. ReAct format (some OSS models)
    
    WHY TRY MULTIPLE FORMATS?
    - Different models have different training/fine-tuning
    - Same agent should work with any model
    - Falls back gracefully if model outputs unexpected format
    
    Returns:
        (code, description) tuple where:
        - code: Executable Python string (empty if nothing found)
        - description: What format was found (for debugging)
    """
    
    # FORMAT 1: Python markdown code blocks
    # Pattern: ```python code ``` or ``` code ```
    blocks = re.findall(r"```(?:python|py)?\s*\n?(.*?)```", response, re.I | re.S)
    if blocks:
        actionable = [
            block for block in blocks
            if any(marker in block for marker in ("edit_file(", "run_tests(", "final_answer("))
        ]
        return (actionable[-1] if actionable else blocks[0]).strip(), "python code block"
    
    # FORMAT 2: XML tool calls (Claude/some providers)
    # Pattern: <invoke name="tool_name">...</invoke>
    # Example:
    #   <invoke name="run_tests">
    #     <parameter name="code">def f(): pass</parameter>
    #   </invoke>
    xml = re.search(r"<invoke\s+name=[\"']([^\"']+)[\"']>(.*?)</invoke>", response, re.I | re.S)
    if xml:
        # Extract parameters from XML
        args = {
            key: value
            for key, value in re.findall(
                r"<parameter\s+name=[\"']([^\"']+)[\"']>(.*?)</parameter>",
                xml.group(2),
                re.I | re.S
            )
        }
        return _tool_call(xml.group(1), args), "XML tool call converted to Python"
    
    # FORMAT 3: JSON tool calls (Hermes, some OSS models)
    # Pattern: <tool_call>{"name": "tool", "arguments": {...}}</tool_call>
    hermes = re.search(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", response, re.I | re.S)
    if hermes:
        payload = json.loads(hermes.group(1))
        return _tool_call(payload.get("name", ""), payload.get("arguments", {})), "JSON tool call converted to Python"

    # FORMAT 4: DeepSeek DSML tool calls
    # Example: <｜｜DSML｜｜ invoke name="read_file">...</｜｜DSML｜｜ invoke>
    dsml = re.findall(
        r"invoke\s+name=[\"']([^\"']+)[\"']>(.*?)</[^>]*invoke>",
        response,
        re.I | re.S,
    )
    if dsml:
        calls = []
        for name, body in dsml:
            arguments = {}
            for key, is_string, value in re.findall(
                r"parameter\s+name=[\"']([^\"']+)[\"'][^>]*string=[\"'](true|false)[\"'][^>]*>(.*?)</[^>]*parameter>",
                body,
                re.I | re.S,
            ):
                arguments[key] = value if is_string.lower() == "true" else int(value)
            calls.append(f"print({_tool_call(name, arguments).removeprefix('result = ')})")
        return "\n".join(calls), "DSML tool call converted to Python"
    
    # FORMAT 5: ReAct format (common in some OSS models)
    # Pattern: Action: func_name\nAction Input: {...}
    react = re.search(r"Action:\s*([\w.-]+)\s*\nAction Input:\s*(\{.*?\})", response, re.I | re.S)
    if react:
        return _tool_call(react.group(1), json.loads(react.group(2))), "ReAct tool call converted to Python"
    
    # NO VALID CODE FOUND
    return "", "No valid Python or supported tool-call code was found"


def extract_final_answer(code: str) -> Optional[str]:
    """
    Extract the argument passed to final_answer() call.
    
    WHY THIS FUNCTION?
    - Agent signals completion by calling final_answer(solution)
    - We need to extract the solution value
    - Must handle quoted strings and multiline
    
    Example:
        Input: 'final_answer("def fibonacci(n): ...")'
        Output: '"def fibonacci(n): ..."'
    
    Args:
        code: Code block that might contain final_answer() call
        
    Returns:
        The argument to final_answer() or None if not found
    """
    match = re.search(r"final_answer\((.*)\)\s*$", code, re.S)
    return match.group(1).strip().strip("'\"") if match else None