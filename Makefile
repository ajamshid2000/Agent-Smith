UV      ?= uv
PYTHON  ?= python

TASK_FILE      ?= task.json
OUTPUT         ?= solution.json
MODEL_NAME     ?= gpt-5.4-mini
PROVIDER_URL   ?= https://api.openai.com/v1

.PHONY: all install run mbpp swebench clean fclean re help

all: install

install:
	$(UV) sync

run: install
	$(UV) run sandbox

mbpp: install
	$(UV) run $(PYTHON) -m agent_mbpp \
		--task-file $(TASK_FILE) \
		--output $(OUTPUT) \
		--model-name "$(MODEL_NAME)" \
		--provider-url "$(PROVIDER_URL)"

swebench: install
	$(UV) run $(PYTHON) -m agent_swebench \
		--task-file $(TASK_FILE) \
		--output $(OUTPUT) \
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