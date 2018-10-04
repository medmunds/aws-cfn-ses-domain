SRC_DIR := src
BUILD_DIR := build
TESTS_DIR := tests

CF_SOURCES := $(wildcard $(SRC_DIR)/*.cf.yaml)
CF_OUTPUTS := $(patsubst $(SRC_DIR)%, $(BUILD_DIR)%, $(CF_SOURCES))


.PHONY: build
build: $(CF_OUTPUTS)


$(BUILD_DIR)/%.cf.yaml: $(SRC_DIR)/%.cf.yaml
	@mkdir -p $(BUILD_DIR)
	./process-import "$<" > "$@"


.PHONY: clean
clean:
	rm -rf "$(BUILD_DIR)"


.PHONY: test
test:
	pipenv run python -m unittest discover \
		--start-directory "$(TESTS_DIR)" \
		--top-level-directory "$(SRC_DIR)"


.PHONY: lint
lint: $(CF_SOURCES) *.cf.yaml
	# TODO: cfn-lint only checks a single filename
	pipenv run cfn-lint "$<"
