PACKAGE_NAME := $(shell basename $(CURDIR))

ARTIFACTS_S3_BUCKET ?= aws-utils.medmunds.com
ARTIFACTS_S3_PREFIX ?= $(PACKAGE_NAME)
DOMAIN ?= example.com

AWS ?= pipenv run aws
PYTHON ?= pipenv run python

DIST_DIR := dist
BUILD_DIR := build
SRC_DIR := aws_cfn_ses_domain
TESTS_DIR := tests

CF_SOURCES := $(wildcard *.cf.yaml)
CF_PACKAGED := $(patsubst %, $(DIST_DIR)/%, $(CF_SOURCES))
LAMBDA_SOURCES := index.py $(shell find $(SRC_DIR) -name '*.py')
LAMBDA_ZIP := $(DIST_DIR)/$(PACKAGE_NAME).lambda.zip


.PHONY: all
all: lambda package


#
# Lambda zip
#
.PHONY: lambda
lambda: $(LAMBDA_ZIP)

$(LAMBDA_ZIP): $(BUILD_DIR)
	rm -f '$@'
	(cd '$(BUILD_DIR)'; zip -r -9 '$(abspath $@)' .)

$(BUILD_DIR): $(LAMBDA_SOURCES) | Pipfile Pipfile.lock $(DIST_DIR)
	rm -rf '$@'
	mkdir -p '$@'
	# Add $(PACKAGE_NAME)...
	@# FUTURE: pipenv run pip install -t '$@' -e .
	ls -1 $^ | cpio -p -dumv '$@'
	# Add dependencies...
	pipenv lock -r > '$@/requirements.txt'
	pipenv run pip install --no-deps -t '$(BUILD_DIR)' -r '$@/requirements.txt'


#
# CloudFormation templates, packaged
#
.PHONY: package
package: $(CF_PACKAGED)

# Some non-obvious dependencies (resulting from `aws cloudformation package`)
$(DIST_DIR)/aws-cfn-ses-domain.cf.yaml: $(BUILD_DIR)
$(DIST_DIR)/example-usage.cf.yaml: $(DIST_DIR)/aws-cfn-ses-domain.cf.yaml

# Rule for packaging CF templates
$(DIST_DIR)/%.cf.yaml: %.cf.yaml | $(DIST_DIR)
	$(AWS) cloudformation package \
		--template-file '$<' \
		--s3-bucket '$(ARTIFACTS_S3_BUCKET)' \
		--s3-prefix '$(ARTIFACTS_S3_PREFIX)' \
		--output-template-file '$@'


$(DIST_DIR):
	@mkdir -p "$(DIST_DIR)"


.PHONY: deploy-example
deploy-example: $(DIST_DIR)/example-usage.cf.yaml
ifeq ($(DOMAIN), example.com)
	@echo 'Set DOMAIN before making this target (`DOMAIN=example.com make $@`)'
else
	$(AWS) cloudformation deploy \
		--template-file "$(DIST_DIR)/example-usage.cf.yaml" \
		--stack-name example-ses-domain \
		--capabilities CAPABILITY_IAM \
		--parameter-overrides "Domain=$(DOMAIN)"
endif


.PHONY: clean
clean:
	rm -rf '$(DIST_DIR)' '$(BUILD_DIR)'


.PHONY: test
test:
	$(PYTHON) -m unittest discover \
		--start-directory "$(TESTS_DIR)"


.PHONY: lint
lint: $(CF_SOURCES)
	@# cfn-lint only allows a single file
	@echo $^ | xargs -n 1 -t pipenv run cfn-lint
