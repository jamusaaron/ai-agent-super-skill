"""Pytest configuration: make the runnable examples importable as modules."""

import os
import sys

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "examples")
if EXAMPLES_DIR not in sys.path:
    sys.path.insert(0, EXAMPLES_DIR)
