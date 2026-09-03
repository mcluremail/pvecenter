#!/usr/bin/env python3
"""Setup shim for Fedora RPM %py3_build macro support.

pyproject.toml is authoritative. This exists only because Fedora's
%py3_build macro calls `setup.py build` directly.
"""
from setuptools import find_packages, setup

setup(packages=find_packages(include=["pve_center*"]))
