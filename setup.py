import sys
from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options = {
    "packages": ["os", "sys", "requests", "watchdog"],
    "excludes": ["tkinter", "matplotlib", "scipy", "numpy"],
    "include_files": [
        "src/config.json.template"
    ]
}

# GUI applications require a different base on Windows
base = None
if sys.platform == "win32":
    base = "Console"

setup(
    name="StarCitizenDiscordLogger",
    version="0.1",
    description="Star Citizen Log to Discord Logger",
    options={"build_exe": build_exe_options},
    executables=[Executable("src/log_analyzer.py", base=base)]
)
