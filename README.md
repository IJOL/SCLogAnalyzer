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
   ```bash
   # For production/runtime use:
   pip install -r requirements.txt
   
   # For development (includes testing and build tools):
   pip install -r requirements.txt -r requirements-dev.txt
   ```

## Usage

Run the script with the path to the configuration file:

StarCitizenDiscordLogger.exe "path/to/config.json" [--process-all | -p]

## Building Executables

The project includes a modern build system with support for two compilation methods:

### PyInstaller Build (Default)
```bash
python src/build.py --build
```
- Creates `dist/SCLogAnalyzer.exe`
- Fast compilation time
- Larger executable size
- Good compatibility

### Nuitka Build (Advanced)
```bash
python src/build.py --nuitka
```
- Creates `dist/SCLogAnalyzer-nuitka.exe`
- Longer compilation time
- Smaller executable size
- Better performance
- Native compilation

### Build Options
- `--dry-run`: Show commands without executing them
- `--console`: Build console mode instead of windowed
- `--skip-venv`: Skip virtual environment activation
- `--skip-requirements`: Skip dependency installation

### Real-time Build Output ✨
Both PyInstaller and Nuitka builds now display **real-time output** during compilation:
- See build progress as it happens
- Monitor compilation stages
- Identify issues immediately
- No more waiting in the dark during long builds

### Version Management
```bash
# Auto-increment version and commit
python src/build.py --increment

# Increment, commit and push to repository
python src/build.py --increment --push
```


## Configuration

- Modify the `config.json` file to set the log file path, Discord webhook URLs, regex patterns, and important players.

### Example `config.json`

```json
{
    "log_file_path": "path/to/log/file",
    "discord_webhook_url": "https://discord.com/api/webhooks/...",
    "technical_webhook_url": "https://discord.com/api/webhooks/...",
    "regex_patterns": {
        "player": "m_ownerGEID\\[(?P<player>\\w+)\\]",
        "timestamp": "<(?P<timestamp>\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}\\.\\d+Z)>",
        "zone": "\\[InstancedInterior\\] (?P<action>OnEntityEnterZone|OnEntityLeaveZone) - InstancedInterior \\[(?P<zone>\\w+)\\]",
        "actor_death": "<(?P<timestamp>\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}\\.\\d+Z)> \\[Notice\\] <Actor Death> CActor::Kill: '(?P<victim>\\w+)' \\[\\d+\\] in zone '(?P<zone>\\w+)' killed by '(?P<killer>\\w+)' \\[\\d+\\] using '(?P<weapon>\\w+)' \\[Class unknown\\] with damage type '(?P<damage_type>\\w+)'",
        "commodity": "\\[InstancedInterior\\] OnEntityEnterZone - InstancedInterior \\[.*\\] \\[.*\\] -> Entity \\[(?P<commodity>.*)\\] \\[.*\\] -- .* \\[.*\\], .* \\[.*\\], .* \\[.*\\], .* \\[.*\\] \\[(?P<owner>.*)\\]\\[.*\\] \\[(?P<zone>.*)\\]"
    },
    "important_players": ["player1", "player2"]
}
```

## Troubleshooting
- Check internet connection
- Verify Discord webhook URL
- Ensure log file path is correct
- Confirm Python is correctly installed and added to PATH

----------------------------------------------------------------























