@echo off
echo Building Star Citizen Discord Logger Executable

:: Create virtual environment
:: python -m venv venv
call venv\Scripts\activate

:: Install requirements
:: pip install -r requirements.txt

:: Build executable using PyInstaller
:: pyinstaller --onefile --console --clean --add-data "src/config.json.template;." --name log_analyzer src/log_analyzer.py
pyinstaller --onefile --console --clean --add-data "src/bot/config.json.template;." --name StatusBoardBot src/bot/bot.py

echo Build complete. Executable will be in the 'dist' directory.
