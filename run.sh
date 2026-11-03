#!/bin/bash
py -m coverage run --branch -m pytest tests/
py -m coverage report -m