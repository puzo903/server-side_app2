#!/bin/bash
python -m coverage run --branch -m pytest tests/ 2>/dev/null || python3 -m coverage run --branch -m pytest tests/ 2>/dev/null || py -m coverage run --branch -m pytest tests/
python -m coverage report -m 2>/dev/null || python3 -m coverage report -m 2>/dev/null || py -m coverage report -m
