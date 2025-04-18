@echo off
echo Building SCLogAnalyzer with Nuitka...
echo.

:: Activate virtual environment if it exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo Virtual environment not found. Creating one...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
    pip install nuitka orderedset
)

:: Create output directory
if not exist nuitka-build mkdir nuitka-build

:: Build with Nuitka
python -m nuitka --standalone ^
    --follow-imports ^
    --windows-console-mode=disable ^
    --include-package=wx ^
    --include-package=pyzbar ^
    --include-package=watchdog ^
    --include-package=_distutils_hack ^
    --include-package=setuptools ^
    --include-data-files=src/config.json.template=config.json.template ^
    --include-data-dir=venv\Lib\site-packages\pyzbar=pyzbar ^
    --windows-icon-from-ico=src/SCLogAnalyzer.ico ^
    --output-dir=nuitka-build ^
    --onefile ^
    src/gui.py

:: Copy the final executable to the dist folder with a better name
if not exist dist mkdir dist
if exist nuitka-build\gui.exe (
    copy nuitka-build\gui.exe dist\SCLogAnalyzer-nuitka.exe /Y
    echo.
    echo Build successful! Executable is at dist\SCLogAnalyzer-nuitka.exe
) else (
    echo.
    echo Build failed. Check the errors above.
)

pause