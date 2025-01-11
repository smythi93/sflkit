# Fandango Makefile. For development only.

# Settings
MAKEFLAGS=--warn-undefined-variables

# Programs
PYTHON = python
PYTEST = pytest
ANTLR = antlr
BLACK = black
PIP = pip
SED = sed
PAGELABELS = $(PYTHON) -m pagelabels


# Default targets
web: requirements.txt parser html
all: web pdf

.PHONY: web all parser install dev-tools docs html latex pdf


## Requirements

requirements.txt:	pyproject.toml
	pip-compile $<

# Install tools for development
UNAME := $(shell uname)
ifeq ($(UNAME), Darwin)
# Mac
SYSTEM_DEV_TOOLS = antlr
SYSTEM_DEV_INSTALL = brew install
else
# Linux
SYSTEM_DEV_TOOLS = antlr
SYSTEM_DEV_INSTALL = apt-get install
endif


dev-tools: system-dev-tools
	pip install -U black

system-dev-tools:
	$(SYSTEM_DEV_INSTALL) $(SYSTEM_DEV_TOOLS)


## Parser

JAVA_PARSER = src/sflkit/language/java/parser
JAVA_LEXER_G4 = antlr/java/JavaLexer.g4
JAVA_PARSER_G4 = antlr/java/JavaParser.g4

JAVA_PARSERS = \
	$(JAVA_PARSER)/JavaLexer.py \
	$(JAVA_PARSER)/JavaParser.py \
	$(JAVA_PARSER)/JavaParserVisitor.py\
	$(JAVA_PARSER)/JavaParserListener.py

java_parser: $(JAVA_PARSERS)

$(JAVA_PARSERS) &: $(JAVA_LEXER_G4) $(JAVA_PARSER_G4)
	$(ANTLR) -Dlanguage=Python3 -Xexact-output-dir -o $(JAVA_PARSER) \
		-visitor $(JAVA_LEXER_G4) $(JAVA_PARSER_G4)
	$(BLACK) src


## Test
test tests:
	$(PIP) install -e .
	$(PYTEST) tests


## Installation

install:
	$(PIP) install -e .