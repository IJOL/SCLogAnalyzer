@echo off
echo Building Star Citizen Discord Logger Executable

:: Create virtual environment
:: python -m venv venv
call .venv\Scripts\activate

:: Install requirements
:: pip install -r requirements.txt

:: Build executable using PyInstaller
pyinstaller --onefile --console --clean src/log_analyzer.py

echo Build complete. Executable will be in the 'dist' directory.
pause
