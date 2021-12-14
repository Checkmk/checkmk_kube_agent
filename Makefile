.DEFAULT_GOAL := help

define BROWSER_PYSCRIPT
import os, webbrowser, sys

from urllib.request import pathname2url

webbrowser.open("file://" + pathname2url(os.path.abspath(sys.argv[1])))
endef
export BROWSER_PYSCRIPT

define PRINT_HELP_PYSCRIPT
import re, sys

for line in sys.stdin:
	match = re.match(r'^([a-zA-Z_-]+):.*?## (.*)$$', line)
	if match:
		target, help = match.groups()
		print("%-20s %s" % (target, help))
endef
export PRINT_HELP_PYSCRIPT

BROWSER := python -c "$$BROWSER_PYSCRIPT"
PROJECT_NAME := checkmk_kube_agent
PROJECT_VERSION := $(shell python3 -c "import src.${PROJECT_NAME};print(src.${PROJECT_NAME}.__version__)")
DOCKER_IMAGE_TAG := $(PROJECT_VERSION)
DOCKERHUB_PUBLISHER := checkmk
CLUSTER_COLLECTOR_IMAGE_NAME := checkmk-cluster-collector
CLUSTER_COLLECTOR_IMAGE := $(DOCKERHUB_PUBLISHER)/${CLUSTER_COLLECTOR_IMAGE_NAME}:${DOCKER_IMAGE_TAG}
NODE_COLLECTOR_IMAGE_NAME := checkmk-node-collector
NODE_COLLECTOR_IMAGE := $(DOCKERHUB_PUBLISHER)/${NODE_COLLECTOR_IMAGE_NAME}:${DOCKER_IMAGE_TAG}

.PHONY: help
help:
	@python -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)

.PHONY: clean
clean: clean-build clean-pyc clean-test ## remove all build, test, coverage and Python artifacts

.PHONY: clean-build
clean-build: ## remove build artifacts
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

.PHONY: clean-pyc
clean-pyc: ## remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

.PHONY: clean-test
clean-test: ## remove test and coverage artifacts
	rm -fr .tox/
	rm -f .coverage
	rm -fr htmlcov/
	rm -fr .pytest_cache
	rm -fr .mypy_cache
	rm -fr .cache

.PHONY: dev-image
dev-image: dist ## build image to be used to run tests in a Docker container
	docker build --rm --target=dev --build-arg PACKAGE_VERSION="${PROJECT_VERSION}" -t $(CLUSTER_COLLECTOR_IMAGE_NAME)-dev -f docker/cluster_collector/Dockerfile .
	docker build --rm --target=dev --build-arg PACKAGE_VERSION="${PROJECT_VERSION}" -t $(NODE_COLLECTOR_IMAGE_NAME)-dev -f docker/node_collector/Dockerfile .


dist: clean ## builds source and wheel package
	python setup.py sdist
	python setup.py bdist_wheel
	ls -l dist

.PHONY: release-image
release-image: dist ## create the node and cluster collector Docker images
	docker build --rm --no-cache --build-arg PACKAGE_VERSION="${PROJECT_VERSION}" -t $(CLUSTER_COLLECTOR_IMAGE) -f docker/cluster_collector/Dockerfile .
	docker build --rm --no-cache --build-arg PACKAGE_VERSION="${PROJECT_VERSION}" -t $(NODE_COLLECTOR_IMAGE) -f docker/node_collector/Dockerfile .
