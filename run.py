#!/usr/bin/env python3
"""Запуск PVE Dashboard. Можно запускать из любого места."""
import sys
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)
os.chdir(parent_dir)

from pve_center.main import main
main()
