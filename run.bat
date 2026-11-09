@echo off
py -m coverage run --branch -m pytest tests/ 2>nul || python -m coverage run --branch -m pytest tests/
py -m coverage report -m 2>nul || python -m coverage report -m
