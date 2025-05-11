#!/usr/bin/env python
import ctypes
# --- Hacer que el proceso sea DPI-aware (Windows)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)  # 1 = system DPI aware
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import wx
import sys
import os
from helpers.main_frame import LogAnalyzerFrame, main

# This is the new entry point for the SC Log Analyzer application
# The actual implementation has been moved to the helpers module
# for better organization and maintainability.

if __name__ == "__main__":
    main()