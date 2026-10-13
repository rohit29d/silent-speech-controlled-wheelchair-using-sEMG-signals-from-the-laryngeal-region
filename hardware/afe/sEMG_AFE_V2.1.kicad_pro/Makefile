PROJECT_NAME ?= $(basename $(notdir $(firstword $(wildcard *.kicad_pro))))
ifeq ($(PROJECT_NAME),)
PROJECT_NAME := $(notdir $(CURDIR))
endif

VENV_DIR := $(HOME)/.venvs/kicad
PYTHON := $(VENV_DIR)/bin/python
PIP := $(VENV_DIR)/bin/pip

# List of required Python packages
PYTHON_REQUIREMENTS := InteractiveHtmlBom pandas openpyxl

# Default target
all: $(VENV_DIR)/bin/activate
	@echo "🐍 Running Python fabrication exporter using virtual environment..."
	$(PYTHON) scripts/export_fab_outputs.py

# Ensure virtual environment and install missing packages
$(VENV_DIR)/bin/activate:
	@echo "🔍 Checking virtual environment at $(VENV_DIR)..."
	@if [ ! -f "$(VENV_DIR)/bin/activate" ]; then \
		echo "🚀 Creating virtual environment..."; \
		mkdir -p $(HOME)/.venvs; \
		python3 -m venv $(VENV_DIR) --system-site-packages; \
	fi
	@echo "📦 Ensuring required Python packages are installed..."
	@for pkg in $(PYTHON_REQUIREMENTS); do \
		$(PYTHON) -m pip show $$pkg > /dev/null 2>&1 || { \
			echo "📦 Installing $$pkg..."; \
			$(PIP) install --upgrade pip; \
			$(PIP) install $$pkg; \
		}; \
	done

# Run design verification checks (ERC + DRC)
check: $(VENV_DIR)/bin/activate
	@echo "🔍 Running design verification checks (ERC + DRC)..."
	$(PYTHON) scripts/run_checks.py

# Alias for all
fab: all

# Generate procurement BOM (CSV + Excel) and position file, DNP parts removed
buy: $(VENV_DIR)/bin/activate
	@echo "📋 Generating procurement BOM + position file..."
	$(PYTHON) export_bom.py

# Package Gerbers into a release archive
release: all
	@echo "📦 Creating release zip for $(PROJECT_NAME)..."
	cd output/Gerbers && zip -r ../$(PROJECT_NAME)_Gerbers.zip .

# Clean output archives and procurement exports
clean:
	rm -rf output/*.zip pcbpower/*.csv pcbpower/*.xlsx

.PHONY: all check fab buy release clean
