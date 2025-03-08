import PyInstaller.__main__
import os

# Get the directory containing setup.py
base_dir = os.path.abspath(os.path.dirname(__file__))

PyInstaller.__main__.run([
    'src/log_analyzer.py',
    '--onefile',
    '--add-data', f'src/config.json.template{os.pathsep}.',
    '--name', 'StarCitizenDiscordLogger',
    '--console'
])