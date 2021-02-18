#
# Publishing
#
S3_BUCKET = aws-utils.medmunds.com
S3_PREFIX = cfn-ses-domain
GITHUB_REPO := medmunds/aws-cfn-ses-domain
# If you will run `make release`, obtain a GitHub personal access token with
# 'public_repo' scope ('repo' if private) from https://github.com/settings/tokens,
# and set GITHUB_TOKEN in your environment (*not* in this file).

#
# Directories
#
ARTIFACTS_DIR := publish
LAMBDA_BUILD_DIR := build-lambda
PY_BUILD_DIR := build
PY_DIST_DIR := dist
TESTS_DIR := tests

#
# Python tools
# (You'll generally want to work in a venv.
# pyenv and pyenv-virtualenv can simplify this.)
#

AWS := aws
CFN_LINT := cfn-lint
PYTHON := python3
PIP := $(PYTHON) -m pip
TWINE := twine

#
# Package info
# (These can be expensive to calculate, so skip for simple targets that won't need them)
#
SIMPLE_TARGETS := clean help init
COMPLEX_GOALS := $(filter-out $(SIMPLE_TARGETS), $(MAKECMDGOALS))
ifneq ($(strip $(COMPLEX_GOALS)),)
# at least one goal is not simple...

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

ifdef TERM
BOLD := $(shell tput setaf 15)
RESET := $(shell tput sgr0)
else
BOLD :=
RESET :=
endif

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
	  -e 's=aws-cfn-ses-domain-VERSION.cf.yaml=$(if $(S3_PREFIX),$(S3_PREFIX)/,)aws-cfn-ses-domain-$(VERSION).cf.yaml=' \
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


.PHONY: deploy-example
## Deploy the example CloudFormation stack for DOMAIN or EMAIL
deploy-example: $(ARTIFACTS_DIR)/example-usage-$(VERSION).cf.yaml
ifeq ($(or $(DOMAIN),$(EMAIL)),)
	$(error Set DOMAIN and/or EMAIL to make this target (`make DOMAIN=example.com $@`))
else
	$(AWS) cloudformation deploy \
	  --template-file '$(ARTIFACTS_DIR)/example-usage-$(VERSION).cf.yaml' \
	  --stack-name example-ses-resources \
	  --capabilities CAPABILITY_IAM \
	  --parameter-overrides Domain='$(DOMAIN)' EmailAddress='$(EMAIL)'
endif


.PHONY: init
## Set up the development environment
init:
	$(PIP) install -r requirements-dev.txt


.PHONY: release
## Release this package to GitHub and PyPI
release: release-github release-pypi


.PHONY: release-pypi
release-pypi:
	$(call heading, Releasing $(VERSION) to PyPI)
	rm -rf $(PY_DIST_DIR)  # always start clean
	$(PYTHON) setup.py \
	  sdist --dist-dir '$(PY_DIST_DIR)' \
	  bdist_wheel --dist-dir '$(PY_DIST_DIR)'
	$(TWINE) upload $(PY_DIST_DIR)/*


.PHONY: release-github
release-github: $(cf_packaged) $(lambda_packaged)
ifndef GITHUB_TOKEN
	$(error Set GITHUB_TOKEN in the environment before `make $@`)
else
	$(call heading, Releasing v$(VERSION) to GitHub $(GITHUB_REPO))
	git tag -m 'Release $(VERSION)' 'v$(VERSION)'
	git push --tags
	$(PYTHON) release-github.py \
	  --repo '$(GITHUB_REPO)' \
	  --tag 'v$(VERSION)' \
	  --description 'See the [CHANGELOG](https://github.com/{repo}/blob/main/CHANGELOG.md#{tag_id})' \
	  --assets $^
endif


.PHONY: clean
## Remove all generated files
clean:
	rm -rf '$(ARTIFACTS_DIR)' '$(PY_BUILD_DIR)' '$(PY_DIST_DIR)' '$(LAMBDA_BUILD_DIR)'


.PHONY: test
## Run tests
test:
	$(PYTHON) -m unittest discover \
		--start-directory '$(TESTS_DIR)' \
		--top-level-directory .


.PHONY: check
## Run lint and similar code checks
check: $(cf_sources)
	$(PYTHON) -m flake8 --max-line-length=120 \
		$(filter %.py,$(lambda_sources)) $(TESTS_DIR)
	$(CFN_LINT) --override-spec CustomSESDomainSpecification.json $^


#
# Help
# Adapted from https://gist.github.com/prwhite/8168133#gistcomment-2278355
#
TARGET_COL_WIDTH := 15

.PHONY: help
## Show this usage info
help:
	@echo ''
	@echo '$(BOLD)USAGE$(RESET)'
	@echo '  $(BOLD)make$(RESET) [ VARIABLE=value ... ] target ...'
	@echo ''
	@echo '$(BOLD)TARGETS$(RESET)'
	@awk '/^[a-zA-Z0-9_-]+:/ { \
		description = match(lastLine, /^## (.*)/); \
		if (description) { \
			target = $$1; sub(/:$$/, "", target); \
			description = substr(lastLine, RSTART + 3, RLENGTH); \
			printf "  $(BOLD)%-$(TARGET_COL_WIDTH)s$(RESET) %s\n", target, description; \
		} \
	} \
	{ lastLine = $$0 }' $(MAKEFILE_LIST)
