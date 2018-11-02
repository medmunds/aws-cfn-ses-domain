#
# Publishing
#
S3_BUCKET = aws-utils.medmunds.com
S3_PREFIX = cfn-ses-domain
GITLAB_PROJECT_ID := medmunds/aws-cfn-ses-domain

#
# Directories
#
ARTIFACTS_DIR := publish
LAMBDA_BUILD_DIR := build-lambda
PY_BUILD_DIR := build
PY_DIST_DIR := dist
TESTS_DIR := tests

#
# Python pipenv and tools
# - If you want to run without pipenv, use `make PIPENV= target`.
#   (You'll need all the Python tools listed below installed in
#   your own activated virtualenv, or globally.)
PIPENV := pipenv
PIPENV_RUN := $(if $(strip $(PIPENV)), $(PIPENV) run,)

AWS := $(PIPENV_RUN) aws
CFN_LINT := $(PIPENV_RUN) cfn-lint
PYTHON := $(PIPENV_RUN) python
PIP := $(PIPENV_RUN) pip
TWINE := $(PIPENV_RUN) twine

#
# Package info
# (These can be expensive to calculate, so skip for simple targets that won't need them)
#
SIMPLE_TARGETS := clean help init
COMPLEX_GOALS := $(filter-out $(SIMPLE_TARGETS), $(MAKECMDGOALS))
ifneq ($(strip $(COMPLEX_GOALS)),)
# at least one goal is not simple...

# Verify pipenv venv exists--otherwise it'll get auto-created without `--dev`
# by $(PYTHON) (pipenv run python) in later variable defs:
ifdef PIPENV
ifneq ($(shell $(PIPENV) --venv >/dev/null 2>&1; echo $$?), 0)
$(error Pipenv virtualenv does not exist; use `make init` to set it up)
endif
endif

# Package metadata
NAME := $(shell $(PYTHON) setup.py --name)
VERSION := $(shell $(PYTHON) setup.py --version)
LAMBDA_ZIP := $(NAME)-$(VERSION).lambda.zip
S3_LAMBDA_ZIP_KEY := $(if $(S3_PREFIX),$(S3_PREFIX)/,)$(LAMBDA_ZIP)
lambda_packaged := $(ARTIFACTS_DIR)/$(LAMBDA_ZIP)

# CloudFormation template files
cf_sources := $(wildcard *.cf.yaml)
cf_packaged := $(patsubst %.cf.yaml, $(ARTIFACTS_DIR)/%-$(VERSION).cf.yaml, $(cf_sources))

# Lambda Package files
# Faster search for package sources (could be fooled by some Python packaging approaches):
#package_sources := setup.py $(shell find '$(subst -,_,$(NAME))' -name '*.py')
# Slower, but accurate, list of source files from `python setup.py egg_info` (run in a temp dir):
package_sources := $(shell EGG_BASE=`mktemp -d` \
					&& ($(PYTHON) setup.py -q egg_info --egg-base="$$EGG_BASE" \
						&& grep -v .egg-info "$$EGG_BASE"/*/SOURCES.txt; \
                	 	rm -rf "$$EGG_BASE"))
lambda_sources := index.py $(package_sources)

endif  # has COMPLEX_GOALS

#
# Misc
#

BOLD := $(shell tput setaf 15)
RESET := $(shell tput sgr0)

# print a bold heading comment in the output
# $(call heading, Banner Text [no commas allowed])
heading = @printf -- '$(BOLD)\# %s$(RESET)\n' '$(strip $1)'

.DEFAULT_GOAL := help

#
# Goals
#

.PHONY: all
## Package the Lambda Function and the CloudFormation templates
all: package template


#
# Lambda Function package
#
.PHONY: package
## Package the Lambda Function zip file
package: $(lambda_packaged)

$(lambda_packaged): $(lambda_sources)
	$(call heading, Stage $(NAME) and requirements into $(LAMBDA_BUILD_DIR))
	rm -rf '$(LAMBDA_BUILD_DIR)'  # always start clean
	mkdir -p '$(LAMBDA_BUILD_DIR)'
	$(PIP) install --no-compile --target '$(LAMBDA_BUILD_DIR)' .
	cp -p index.py '$(LAMBDA_BUILD_DIR)'
	$(call heading, Package Lambda zip $@ from $(LAMBDA_BUILD_DIR))
	mkdir -p '$(@D)'
	rm -f '$@'
	(cd '$(LAMBDA_BUILD_DIR)'; zip -r -9 '$(abspath $@)' .)


#
# CloudFormation templates, packaged
#
.PHONY: template
## Package the CloudFormation templates (for upload to S3_BUCKET)
template: $(cf_packaged)


# Rule for packaging CloudFormation templates
$(ARTIFACTS_DIR)/%-$(VERSION).cf.yaml: %.cf.yaml
	$(call heading, Package CloudFormation template $@)
	@mkdir -p '$(@D)'
	sed -e 's=YOUR_BUCKET_NAME=$(S3_BUCKET)=' \
	  -e 's=YOUR_LAMBDA_ZIP_KEY=$(S3_LAMBDA_ZIP_KEY)=' \
	  -e 's=LAMBDA_ZIP=$(LAMBDA_ZIP)=' \
	  '$<' >'$@'
#	$(AWS) cloudformation package \
#	  --template-file '$<' \
#	  --s3-bucket '$(S3_BUCKET)' $(if $(S3_PREFIX),--s3-prefix '$(S3_PREFIX)',) \
#	  --output-template-file '$@'



.PHONY: upload
## Upload packaged Lambda zip file and templates to S3_BUCKET
upload: | all
	$(AWS) s3 cp --recursive $(ARTIFACTS_DIR)/ \
	  's3://$(S3_BUCKET)$(if $(S3_PREFIX),/$(S3_PREFIX),)/'


.PHONY: deploy
## Deploy the example CloudFormation stack for DOMAIN
deploy: $(ARTIFACTS_DIR)/example-usage-$(VERSION).cf.yaml
ifndef DOMAIN
	$(error Set DOMAIN to make this target (`make DOMAIN=example.com $@`))
else
	$(AWS) cloudformation deploy \
	  --template-file '$(ARTIFACTS_DIR)/example-usage-$(VERSION).cf.yaml' \
	  --stack-name example-ses-domain \
	  --capabilities CAPABILITY_IAM \
	  --parameter-overrides \
	    Domain='$(DOMAIN)' \
	    CfnSESDomainTemplateURL='https://s3.amazonaws.com/$(S3_BUCKET)/$(S3_LAMBDA_ZIP_KEY)'
endif


.PHONY: init
## Set up the development environment (using pipenv)
init:
ifeq ($(strip $(PIPENV)),)
	$(error You must manage your own Python virtualenv when PIPENV is disabled)
else ifeq ($(shell which $(PIPENV)),)
	$(error Can't find $(PIPENV); see https://pipenv.readthedocs.io/ to install)
else
	$(PIPENV) install
endif


.PHONY: release
## Release this package to GitLab and PyPI
release: release-gitlab release-pypi


.PHONY: release-pypi
release-pypi:
	$(call heading, Releasing $(VERSION) to PyPI)
	rm -rf $(PY_DIST_DIR)  # always start clean
	$(PYTHON) setup.py --dist-dir '$(PY_DIST_DIR)' sdist bdist_wheel
	$(TWINE) upload $(PY_DIST_DIR)/*


.PHONY: release-gitlab
release-gitlab: $(cf_packaged) $(lambda_packaged)
	$(call heading, Releasing v$(VERSION) to GitLab $(GITLAB_PROJECT_ID))
	git tag -m 'Release $(VERSION)' 'v$(VERSION)'
	git push --tags
	$(PYTHON) release-gitlab.py \
	  --id '$(GITLAB_PROJECT_ID)' \
	  --name 'v$(VERSION)' \
	  --description '{artifacts}' \
	  --artifacts $^


.PHONY: clean
## Remove all generated files
clean:
	rm -rf '$(ARTIFACTS_DIR)' '$(PY_BUILD_DIR)' '$(PY_DIST_DIR)' '$(LAMBDA_BUILD_DIR)'


.PHONY: test
## Run tests
test:
	$(PYTHON) -m unittest discover \
		--start-directory '$(TESTS_DIR)'


.PHONY: check
## Run lint and similar code checks
check: $(cf_sources)
	$(PIPENV) check --style
	@# (cfn-lint only handles a single file at once)
	@echo $^ | xargs -n 1 -t $(CFN_LINT)


#
# Help
# Adapted from https://gist.github.com/prwhite/8168133#gistcomment-2278355
#
TARGET_COL_WIDTH := 10

.PHONY: help
## Show this usage info
help:
	@echo ''
	@echo '$(BOLD)USAGE$(RESET)'
	@echo '  $(BOLD)make$(RESET) [ VARIABLE=value ... ] target ...'
	@echo ''
	@echo '$(BOLD)TARGETS$(RESET)'
	@awk '/^[a-zA-Z\-\_0-9]+:/ { \
		description = match(lastLine, /^## (.*)/); \
		if (description) { \
			target = $$1; sub(/:$$/, "", target); \
			description = substr(lastLine, RSTART + 3, RLENGTH); \
			printf "  $(BOLD)%-$(TARGET_COL_WIDTH)s$(RESET) %s\n", target, description; \
		} \
	} \
	{ lastLine = $$0 }' $(MAKEFILE_LIST)
