UV      ?= uv
PYTHON  ?= python

TASK_FILE_SWEBENCH      ?= cache/swebench_task.json
TASK_FILE      ?= cache/mbpp_task.json
OUTPUT         ?= cache/mbpp_solution.json
OUTPUT_SWEBENCH ?= cache/swebench_solution.json
MODEL_NAME     ?= ~openai/gpt-astra-latest
PROVIDER_URL   ?= https://openrouter.ai/api/v1

.PHONY: all install run mbpp swebench clean fclean re help

all: install

install:
	$(UV) sync

run: install
	$(UV) run sandbox

mbpp: install
	mkdir -p cache
	$(UV) run $(PYTHON) -m agent_mbpp \
		--task-file $(TASK_FILE) \
		--output $(OUTPUT) \
		--model-name "$(MODEL_NAME)" \
		--provider-url "$(PROVIDER_URL)"

swebench: install
	mkdir -p cache
	$(UV) run $(PYTHON) -m agent_swebench \
		--task-file $(TASK_FILE_SWEBENCH) \
		--output $(OUTPUT_SWEBENCH) \
		--model-name "$(MODEL_NAME)" \
		--provider-url "$(PROVIDER_URL)"

clean:
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache \) -prune -exec rm -rf {} +
	rm -rf .coverage htmlcov

fclean: clean
	rm -rf .venv build dist *.egg-info

re: fclean all

help:
	@printf '%s\n' \
		'make             Install dependencies' \
		'make run         Launch the interactive sandbox' \
		'make mbpp        Run the MBPP agent' \
		'make swebench    Run the SWE-bench agent' \
		'make clean       Remove generated caches' \
		'make fclean      Remove caches, environment, and build artifacts' \
		'make re          Reinstall the project from scratch'