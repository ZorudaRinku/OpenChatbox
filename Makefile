.PHONY: install run test clean build-windows build-wine build-linux

VENV         := .venv
PIP          := $(VENV)/bin/pip
PYTHON       := $(VENV)/bin/python
RCC          := $(VENV)/bin/pyside6-rcc
WINE_PYTHON  ?= python
INNO_SETUP   ?= C:\Program Files (x86)\Inno Setup 6\ISCC.exe

$(VENV):
	python -m venv $(VENV)

resources_rc.py: resources.qrc
	$(RCC) resources.qrc -o resources_rc.py

## Setup

install: $(VENV)        ## Create venv and install all dependencies
	$(PIP) install ".[dev]"
	$(RCC) resources.qrc -o resources_rc.py

## Development

run: resources_rc.py    ## Run the application
	$(PYTHON) main.py

test: resources_rc.py   ## Run the test suite
	$(PYTHON) -m pytest

## Building

build-windows: resources_rc.py   ## Build Windows .exe + installer (native Windows)
	rm -rf dist/OpenChatbox dist/OpenChatbox.exe
	python -m PyInstaller OpenChatbox.spec
	"$(INNO_SETUP)" openchatbox_installer.iss
	rm -rf dist/OpenChatbox dist/OpenChatbox.exe
	@echo "Installer: dist/OpenChatboxSetup.exe"

build-wine: resources_rc.py      ## Build Windows .exe + installer via Wine (Linux)
	@command -v wine >/dev/null 2>&1 || { echo "Error: wine is not installed"; exit 1; }
	rm -rf dist/OpenChatbox dist/OpenChatbox.exe
	WINEDEBUG=-all wine $(WINE_PYTHON) -m PyInstaller OpenChatbox.spec
	WINEDEBUG=-all wine "$(INNO_SETUP)" openchatbox_installer.iss
	rm -rf dist/OpenChatbox dist/OpenChatbox.exe
	@echo "Installer: dist/OpenChatboxSetup.exe"

build-linux: resources_rc.py     ## Build Linux executable via PyInstaller
	rm -rf dist/OpenChatbox
	$(PYTHON) -m PyInstaller OpenChatbox.spec
	@echo "Output: dist/OpenChatbox/"

clean:                  ## Remove build artifacts
	rm -rf build dist *.egg-info __pycache__

## Help

help:                   ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-20s %s\n", $$1, $$2}'
