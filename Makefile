# TOOLS
GIT = /usr/bin/git

# REVISION INFO
HOSTNAME := $(shell hostname)
COMMIT := $(shell $(GIT) rev-parse HEAD)
REV_HASH := $(shell $(GIT) log --format='%h' -n 1)
REV_TAGS := $(shell $(GIT) describe --abbrev=0 --tags --always)
BRANCH := $(shell echo $(GIT_BRANCH)|cut -f2 -d"/")
PY_VERSION := $(shell cat setup.py | grep version |cut -f2 -d"=" | sed "s/[,\']//g")
VERSION_JSON = newman/version.json

all: build

version:
	@-echo "Building version info in $(VERSION_JSON)"
	@echo "{\n\t\"hash\": \"$(REV_HASH)\"," > $(VERSION_JSON)
	@echo "\t\"version\": \"$(PY_VERSION)\"," >> $(VERSION_JSON)
	@echo "\t\"hostname\": \"$(HOSTNAME)\"," >> $(VERSION_JSON)
	@echo "\t\"commit\": \"$(COMMIT)\"," >> $(VERSION_JSON)
	@echo "\t\"branch\": \"$(BRANCH)\"," >> $(VERSION_JSON)
	@echo "\t\"tags\": \"$(REV_TAGS)\"\n}" >> $(VERSION_JSON)

clean:
	find . -type f -name "*.py[c|o]" -exec rm -f {} \;
	find . -type f -name "*.edited" -exec rm -f {} \;
	find . -type f -name "*.orig" -exec rm -f {} \;
	find . -type f -name "*.swp" -exec rm -f {} \;
	rm -f newman/version.json
	rm -rf dist
	rm -rf build

build: clean version
	python setup.py sdist
	python setup.py bdist_wheel
