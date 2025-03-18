.PHONY: help
help:
	@echo "Make targets for rsp-jupyter-extensions"
	@echo "make init - Set up dev environment"
	@echo "make typing - Run typechecker for Python and Typescript"
	@echo "make lint - Lint Python and Typescript"
	@echo "make test - Run Python unit tests"

.PHONY: init
init:
	pip install --upgrade uv
	uv pip install --editable '.[test]' jupyterlab
	pre-commit install

.PHONY: typing
typing:
	jlpm run build
	mypy rsp_jupyter_extensions

.PHONY: lint
lint:
	jlpm run lint
	pre-commit run --all-files

.PHONY: test
test:
	pytest -vvv rsp_jupyter_extensions
