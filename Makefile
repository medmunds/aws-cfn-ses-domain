ARTIFACTS_S3_BUCKET ?= aws-utils.medmunds.com
ARTIFACTS_S3_PREFIX ?= cfn-ses-domain
DOMAIN ?= example.com

BUILD_DIR := build
SRC_DIR := cfn_ses_domain
TESTS_DIR := tests

CF_SOURCES := $(wildcard *.cf.yaml)
CF_OUTPUTS := $(patsubst %, $(BUILD_DIR)/%, $(CF_SOURCES))
LAMBDA_SOURCES := $(wildcard $(SRC_DIR)/*.py)

.PHONY: package deploy clean lint test lint


package: $(CF_OUTPUTS)

# Some non-obvious dependencies (caused by packaging)
$(BUILD_DIR)/cfn-ses-domain.cf.yaml: $(LAMBDA_SOURCES)

$(BUILD_DIR)/example-usage.cf.yaml: $(BUILD_DIR)/cfn-ses-domain.cf.yaml

# Rule for packaging CF templates
$(BUILD_DIR)/%.cf.yaml: %.cf.yaml
	@mkdir -p "$(BUILD_DIR)"
	pipenv run aws cloudformation package \
		--template-file "$<" \
		--s3-bucket "$(ARTIFACTS_S3_BUCKET)" \
		--s3-prefix "$(ARTIFACTS_S3_PREFIX)" \
		--output-template-file "$@"


deploy: $(BUILD_DIR)/example-usage.cf.yaml
ifeq ($(DOMAIN), example.com)
	@echo 'Set DOMAIN before making this target (`DOMAIN=example.com make $@`)'
else
	pipenv run aws cloudformation deploy \
		--template-file "$(BUILD_DIR)/example-usage.cf.yaml" \
		--stack-name example-cfn-ses-domain \
		--capabilities CAPABILITY_IAM \
		--parameter-overrides "Domain=$(DOMAIN)"
endif


clean:
	rm -rf "$(BUILD_DIR)"


test:
	pipenv run python -m unittest discover \
		--start-directory "$(TESTS_DIR)" \
		--top-level-directory "$(SRC_DIR)"


lint: $(CF_SOURCES)
	@# cfn-lint only allows a single file
	@echo $^ | xargs -n 1 -t pipenv run cfn-lint
