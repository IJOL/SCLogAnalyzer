# Star Citizen Discord Logger

## Prerequisites

### Python Installation
1. Download Python Installer: [Python 3.12.1 Windows Installer (64-bit)](https://www.python.org/ftp/python/3.12.1/python-3.12.1-amd64.exe)
   - Direct link to the latest stable version as of December 2024
   - Make sure to check "Add Python to PATH" during installation

### Important Installation Notes
- Choose "Install Now" option
- Ensure "Add python.exe to PATH" is selected
- Click "Disable path length limit" if prompted

## Setup

1. Clone the repository
2. Create a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```

3. Install requirements:
   ```
   pip install -r requirements.txt
   ```

## Usage

Run the executable with two arguments:
```
StarCitizenDiscordLogger.exe "C:\path\to\logfile.log" "https://discord.com/api/webhooks/your_webhook_url"
```

## Building from Source

1. Run the build script:
   ```
   build.bat
   ```

2. The executable will be in the `dist` directory.

## Configuration

- Modify the log file path
- Use your Discord webhook URL
- Ensure the log file is accessible

## Troubleshooting
- Check internet connection
- Verify Discord webhook URL
- Ensure log file path is correct
- Confirm Python is correctly installed and added to PATH