@echo off

:: Check for push parameter
SET PUSH_CHANGES=0
IF NOT "%1"=="" SET PUSH_CHANGES=1
echo Getting commit short hash for patch identifier...
FOR /F "tokens=* USEBACKQ" %%C IN (`git rev-parse --short HEAD`) DO (
  SET commit_hash=%%C
)
echo Current commit hash: %commit_hash%

echo Incrementing version...
IF NOT "%1"=="" python src\increment_version.py %commit_hash% %1
echo.
echo Building SC Log Analyzer...
FOR /F "tokens=* USEBACKQ" %%F IN (`python -c "from src.version import get_version; print(get_version())"`) DO (
  SET version=%%F
)
echo Current version: %version%


:: Only push if the parameter was provided
IF %PUSH_CHANGES%==1 (
  echo Committing and pushing version %version% to repository...
  git add src\version.py
  git commit -m "Increment version to %version%"
  echo Pushing changes to remote repository...
  git push
) ELSE (
  echo Skipping push to remote repository. Use -p or --push parameter to push changes.
)
echo.
IF "%1"=="" exit
echo Building Star Citizen Discord Logger Executable

:: Create virtual environment
:: python -m venv venv
call venv\Scripts\activate

:: Install requirements
:: pip install -r requirements.txt

:: Build executable using PyInstaller
pyinstaller --onefile --console --clean --add-data "src/config.json.template;." --name log_analyzer src/log_analyzer.py
pyinstaller --onefile --console --clean --add-data "src/bot/config.json.template;." --name StatusBoardBot src/bot/bot.py

:: Update ZIP files with new executables
powershell -Command "Compress-Archive -Path 'dist\log_analyzer.exe' -DestinationPath 'dist\log_analyzer.zip' -Update"
powershell -Command "Compress-Archive -Path 'dist\StatusBoardBot.exe' -DestinationPath 'dist\StatusBoardBot.zip' -Update"
echo Build complete. Executable will be in the 'dist' directory.
