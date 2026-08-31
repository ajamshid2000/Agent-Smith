# Agent Smith: Documentation Index

## Complete Guide to Understanding Agent Smith

If you're completely new to Agent Smith, follow this progression:

### For Absolute Beginners
Start here if you've never seen this codebase before:

1. **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** (10 minutes)
   - Quick overview of what Agent Smith does
   - Key concepts in simple terms
   - Common commands to run it
   - Debugging checklist
   - **Best for:** Getting the big picture quickly

2. **[PROJECT_GUIDE.md](PROJECT_GUIDE.md)** (30 minutes)
   - What each component does
   - Overview of all files
   - How they fit together
   - Step-by-step running instructions
   - **Best for:** Understanding the overall architecture

### For Intermediate Understanding
Once you have the basics:

3. **[EXECUTION_FLOW.md](EXECUTION_FLOW.md)** (45 minutes)
   - Complete walkthrough of MBPP agent run
   - Example input/output at each step
   - Line-by-line explanation
   - Shows exact JSON messages
   - SWE-bench differences
   - **Best for:** Understanding exactly what happens when you run the agent

4. **[ALGORITHMS_EXPLAINED.md](ALGORITHMS_EXPLAINED.md)** (60 minutes)
   - Detailed explanation of core algorithms
   - Thought → Code → Observation loop
   - Sandbox security model with threat analysis
   - API key rotation strategy
   - MCP protocol details
   - Code extraction (multiple formats)
   - Token limit management
   - Path traversal prevention
   - Timeout detection
   - **Best for:** Understanding the "why" behind design decisions

### For Developers
When you need to modify or extend:

5. **Code with Comments**
   - `agent_smith/models.py` - Data structures
   - `agent_smith/loop.py` - Main algorithm
   - `agent_smith/providers.py` - LLM communication
   - `agent_smith/sandbox.py` - Security
   - `agent_smith/extract.py` - Response parsing
   - `mcp_tools_mbpp.py` - MBPP tools
   - `mcp_tools_swebench.py` - SWE-bench tools
   - **Best for:** Understanding implementation details

---

## Reading Paths by Goal

### Goal: "I want to run the agent"
1. QUICK_REFERENCE.md → Install & Run section
2. Run `make install && uv run python -m agent_mbpp ...`

### Goal: "I want to understand how it works"
1. QUICK_REFERENCE.md (5 min) - Big picture
2. PROJECT_GUIDE.md (20 min) - Architecture
3. EXECUTION_FLOW.md (30 min) - Walkthrough

### Goal: "I want to modify/debug the agent"
1. PROJECT_GUIDE.md - Understand structure
2. EXECUTION_FLOW.md - See exact flow
3. Read code in `agent_smith/` with comments
4. ALGORITHMS_EXPLAINED.md - Understand design decisions

### Goal: "I want to add new features"
1. ALGORITHMS_EXPLAINED.md - Understand design
2. Read relevant code file
3. Understand MCP protocol if adding tools
4. Add code with similar style

### Goal: "The agent failed, I want to debug"
1. QUICK_REFERENCE.md → Debugging Checklist
2. Use `jq` to inspect `solution.json`
3. EXECUTION_FLOW.md → check similar step
4. ALGORITHMS_EXPLAINED.md → understand failure mode

---

## File Reference

### Documentation Files (I Created)
```
PROJECT_GUIDE.md          - Complete overview (32 KB)
EXECUTION_FLOW.md         - Step-by-step walkthrough (28 KB)
ALGORITHMS_EXPLAINED.md   - Deep dive into algorithms (24 KB)
QUICK_REFERENCE.md        - Quick lookup guide (12 KB)
DOCUMENTATION_INDEX.md    - This file
```

### Source Code Files (Original + Comments)
```
agent_smith/
├── __init__.py            - Package definition
├── models.py              - Pydantic data models (COMMENTED)
├── providers.py           - LLM API client (COMMENTED)
├── sandbox.py             - Secure execution (COMMENTED)
├── mcp.py                 - MCP protocol client
├── loop.py                - Main loop (COMMENTED)
└── extract.py             - Response parsing (COMMENTED)

Root level:
├── agent_mbpp.py          - MBPP agent entry point
├── agent_swebench.py      - SWE-bench agent entry point
├── mcp_tools_mbpp.py      - MBPP MCP tools
├── mcp_tools_swebench.py  - SWE-bench MCP tools
├── Makefile               - Build commands
└── pyproject.toml         - Project configuration
```

---

## Topic Quick Navigation

### Finding Answers to Common Questions

**Q: What is Agent Smith?**
→ PROJECT_GUIDE.md → Project Overview

**Q: How do I run it?**
→ QUICK_REFERENCE.md → Install & Run
OR PROJECT_GUIDE.md → Running the Project

**Q: What's the Thought → Code → Observation loop?**
→ ALGORITHMS_EXPLAINED.md → Section 1
OR PROJECT_GUIDE.md → Key Concepts

**Q: How does the sandbox work?**
→ ALGORITHMS_EXPLAINED.md → Section 2
OR EXECUTION_FLOW.md → Step 3

**Q: How does security work?**
→ ALGORITHMS_EXPLAINED.md → Section 2
OR agent_smith/sandbox.py (read code)

**Q: What's MCP?**
→ ALGORITHMS_EXPLAINED.md → Section 4
OR EXECUTION_FLOW.md → Step 2

**Q: How are API keys handled?**
→ ALGORITHMS_EXPLAINED.md → Section 3
OR agent_smith/providers.py (read code)

**Q: What happens in each iteration?**
→ EXECUTION_FLOW.md → Iteration 1 & 2

**Q: What's in the output (solution.json)?**
→ PROJECT_GUIDE.md → Key Concepts
OR EXECUTION_FLOW.md → Step 6

**Q: Why did the agent fail?**
→ QUICK_REFERENCE.md → Debugging Checklist
OR EXECUTION_FLOW.md → Common Issues

**Q: How do I debug step X?**
→ EXECUTION_FLOW.md → Find your step
→ ALGORITHMS_EXPLAINED.md → Understand the algorithm

**Q: How do I add a new tool?**
→ mcp_tools_swebench.py (read code)
→ ALGORITHMS_EXPLAINED.md → Section 4

**Q: How do I change the system prompt?**
→ agent_smith/loop.py (search for SYSTEM_PROMPT)
→ PROJECT_GUIDE.md → Loop (Core Components)

**Q: Why does the sandbox reject imports?**
→ ALGORITHMS_EXPLAINED.md → Section 2 (Security)
→ agent_smith/sandbox.py → SandboxConfig class

---

## Understanding the Code

### Before Reading Code Files
1. Read PROJECT_GUIDE.md → Core Components
2. Read ALGORITHMS_EXPLAINED.md → relevant section
3. Now code comments will make sense

### Recommended Code Reading Order
1. `agent_smith/models.py` (10 min) - Understand data
2. `agent_smith/loop.py` (15 min) - Understand main algorithm
3. `agent_smith/sandbox.py` (15 min) - Understand security
4. `agent_smith/providers.py` (10 min) - Understand LLM API
5. `agent_smith/extract.py` (5 min) - Understand parsing
6. `mcp_tools_mbpp.py` (5 min) - Understand simple tools
7. `mcp_tools_swebench.py` (10 min) - Understand complex tools

### Understanding Specific Features
```
Want to understand:          Read these:
─────────────────────────────────────────
Token limits                 loop.py, ALGORITHMS_EXPLAINED.md § 6
Timeout enforcement          sandbox.py, ALGORITHMS_EXPLAINED.md § 8
Path traversal prevention    sandbox.py, ALGORITHMS_EXPLAINED.md § 7
API key rotation             providers.py, ALGORITHMS_EXPLAINED.md § 3
Code format support          extract.py, ALGORITHMS_EXPLAINED.md § 5
Tool communication           mcp.py, ALGORITHMS_EXPLAINED.md § 4
Import restrictions          sandbox.py, ALGORITHMS_EXPLAINED.md § 2
Docker integration           mcp_tools_swebench.py, EXECUTION_FLOW.md
```

---

## Learning Progression

### Level 1: User (Just Run It)
**Time:** 15 minutes
**Goal:** Get agent working on a task
**Read:**
- QUICK_REFERENCE.md
- EXECUTION_FLOW.md → Install & Run
**Do:**
- Follow install steps
- Run on MBPP task
- View solution.json with jq

### Level 2: Debugger (Fix When Broken)
**Time:** 1 hour
**Goal:** Understand what went wrong
**Read:**
- PROJECT_GUIDE.md
- EXECUTION_FLOW.md
- QUICK_REFERENCE.md → Debugging
**Do:**
- Run on task
- If failed, use debugging checklist
- Read relevant step in EXECUTION_FLOW.md

### Level 3: Developer (Modify Code)
**Time:** 3-4 hours
**Goal:** Understand and change implementation
**Read:**
- All documentation
- Code comments in relevant files
- ALGORITHMS_EXPLAINED.md
**Do:**
- Read loop.py and understand main algorithm
- Try changing system prompt
- Try adding debugging output
- Read sandbox.py, understand security

### Level 4: Architect (Extend System)
**Time:** 8-12 hours
**Goal:** Add new features or tools
**Read:**
- All documentation thoroughly
- All code files with focus on architecture
- External docs (Pydantic, MCP spec)
**Do:**
- Plan changes on paper
- Read all related code
- Write tests
- Make changes
- Test end-to-end

---

## Quick Code Navigation

### "Where does X happen?"

| What | Where |
|------|-------|
| LLM gets called | `agent_smith/loop.py` → run() → completion = provider.complete(...) |
| Code gets executed | `agent_smith/loop.py` → run() → execution = sandbox.execute(code) |
| Imports get checked | `agent_smith/sandbox.py` → restricted_import() |
| Files get read | `mcp_tools_swebench.py` → read_file() |
| Tests get run | `mcp_tools_mbpp.py` → run_tests() |
| Results get saved | `agent_mbpp.py` → output.write(solution.model_dump_json()) |
| Tool calls get routed | `agent_smith/sandbox.py` → call_tool() |
| Timeout gets checked | `agent_smith/sandbox.py` → execute() → deadline |
| Observations get updated | `agent_smith/loop.py` → observation = f"..." |
| Tokens get tracked | `agent_smith/loop.py` → total_input += completion.input_tokens |

---

## Summary

**Agent Smith** is a Python framework for autonomous code generation using:
- **Loop:** Thought → Code → Observation (iterative reasoning)
- **Safety:** Sandbox with restrictions, import whitelist, path checks
- **Flexibility:** Any OpenAI-compatible LLM, multiple tools
- **Observability:** Complete trace of every step

**Documentation Overview:**
- 📖 **PROJECT_GUIDE.md** - Learn the system
- 🚀 **EXECUTION_FLOW.md** - See it in action
- 🧠 **ALGORITHMS_EXPLAINED.md** - Understand the why
- ⚡ **QUICK_REFERENCE.md** - Quick lookup
- 📚 **Code comments** - Implementation details

**Start:** Read QUICK_REFERENCE.md (10 min)
**Next:** Read PROJECT_GUIDE.md (30 min)
**Deep Dive:** Read EXECUTION_FLOW.md (45 min)
**Master:** Read ALGORITHMS_EXPLAINED.md (60 min)

---

**Happy learning! 🚀**

---

## Document Statistics

| Document | Size | Read Time | Best For |
|----------|------|-----------|----------|
| QUICK_REFERENCE.md | 8 KB | 10 min | Overview & commands |
| PROJECT_GUIDE.md | 32 KB | 30 min | Architecture & files |
| EXECUTION_FLOW.md | 28 KB | 45 min | Step-by-step walkthrough |
| ALGORITHMS_EXPLAINED.md | 24 KB | 60 min | Deep understanding |
| DOCUMENTATION_INDEX.md | 12 KB | 15 min | Navigation |
| **Total** | **104 KB** | **160 min** | Complete mastery |

Reading all four main documents = 2.5-3 hours for complete understanding
