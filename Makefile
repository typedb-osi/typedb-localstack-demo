VENV_BIN = python3 -m venv
VENV_DIR ?= .venv
VENV_ACTIVATE = $(VENV_DIR)/bin/activate
VENV_RUN = . $(VENV_ACTIVATE)

usage:          ## Shows usage for this Makefile
	@cat Makefile | grep -E '^[a-zA-Z_-]+:.*?## .*$$' | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

venv: $(VENV_ACTIVATE)

$(VENV_ACTIVATE):
	test -d .venv || $(VENV_BIN) .venv

clean:
	rm -rf .venv/ build/

install: venv   ## Install dependencies
	$(VENV_RUN); pip install --upgrade localstack pytest requests ruff terraform-local typedb-driver

tf-deploy:      ## Deploy the app locally via Terraform
	mkdir -p build/lambda
	cp -r app/lambda/* build/lambda/

	docker run -it --platform=linux/amd64 --rm --entrypoint= -v $(PWD)/build/lambda:/tmp/lambda public.ecr.aws/lambda/python:3.11 pip install --upgrade --target /tmp/lambda -r /tmp/lambda/requirements.txt

	##### NOTE: SOMETIMES THE ARM64 VERSION WORKS, SOMETIMES THE AMD64 VERSION WORKS? #####
	#docker run -it --platform=linux/arm64/v8 --rm --entrypoint= -v $(PWD)/build/lambda:/tmp/lambda public.ecr.aws/lambda/python:3.11 pip install --upgrade --target /tmp/lambda -r /tmp/lambda/requirements.txt

	$(VENV_RUN); tflocal init; tflocal apply -auto-approve

test-lambda:    ## Run Lambda API tests
	$(VENV_RUN); pytest tests/test_lambda.py -v -s

format:		    ## Run ruff to format the whole codebase
	$(VENV_RUN); python -m ruff format .; python -m ruff check --output-format=full --fix .

test:		    ## Run integration tests (requires LocalStack running with the Extension installed)
	$(VENV_RUN); pytest tests/test_extension.py -v -s

.PHONY: clean install usage venv format test requests test-lambda tf-deploy
