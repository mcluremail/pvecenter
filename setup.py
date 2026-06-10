#!/usr/bin/env python3
"""Setup shim for Fedora RPM %py3_build macro support.

pyproject.toml is the authoritative config for pip and Debian builds.
This file exists solely because Fedora's %py3_build macro calls
`setup.py build` directly. It delegates to setuptools via setup.cfg
to avoid duplicating metadata.
"""
from setuptools import setup

setup()