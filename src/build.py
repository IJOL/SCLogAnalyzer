#!/usr/bin/env python
"""
Modern Build script for SC Log Analyzer using Plumbum
This replaces subprocess calls with elegant Plumbum syntax
"""

import os
import re
import sys
import argparse
import importlib.util
import shutil
import zipfile
from pathlib import Path
from plumbum import local, ProcessExecutionError
import subprocess

# Directory settings
ROOT_DIR = Path(__file__).parent.parent
SRC_DIR = ROOT_DIR / "src"
VERSION_FILE = SRC_DIR / "version.py"
DIST_DIR = ROOT_DIR / "dist"
NUITKA_BUILD_DIR = ROOT_DIR / "nuitka-build"
CONFIG_TEMPLATE = SRC_DIR / "config.json.template"

# Default virtual environment directory name (can be overridden via CLI)
DEFAULT_VENV_NAME = ".venv"
# This will be overwritten after parsing CLI args, but provide default for function definitions
VENV_DIR = ROOT_DIR / DEFAULT_VENV_NAME

# Plumbum commands
git = local["git"]
pyinstaller = local["pyinstaller"]
nuitka = local[sys.executable]["-m", "nuitka"]
python = local[sys.executable]
pip = local[sys.executable]["-m", "pip"]


# === FAKE DATA GENERATORS FOR DRY-RUN MODE ===

def get_realistic_fake_data():
    """Lee version.py y genera datos fake realistas basados en la versión actual"""
    import importlib.util
    try:
        # Leer version.py actual
        spec = importlib.util.spec_from_file_location("version", VERSION_FILE)
        version_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(version_module)
        
        current_major = version_module.MAJOR
        current_minor = version_module.MINOR  
        current_release = version_module.RELEASE
        current_maturity = version_module.MATURITY
        
        # Incrementar RELEASE de forma realista
        new_release = current_release + 1
        
        return {
            'current_version': f"v{current_major}.{current_minor}.{current_release}",
            'new_version': f"v{current_major}.{current_minor}.{new_release}",
            'full_new_version': f"v{current_major}.{current_minor}.{new_release}-abc1234-{current_maturity}",
            'commit_hash': 'abc1234',
            'old_release': current_release,
            'new_release': new_release,
            'major': current_major,
            'minor': current_minor,
            'maturity': current_maturity
        }
    except Exception:
        # Fallback si no se puede leer
        return {
            'current_version': 'v0.10.3',
            'new_version': 'v0.10.4', 
            'full_new_version': 'v0.10.4-abc1234-attritus',
            'commit_hash': 'abc1234',
            'old_release': 3,
            'new_release': 4,
            'major': 0,
            'minor': 10,
            'maturity': 'attritus'
        }

def get_fake_commit_hash():
    """Genera un hash fake consistente y realista"""
    return get_realistic_fake_data()['commit_hash']

def get_fake_version_increment(current_version=None):
    """Genera incremento fake realista basado en la versión actual"""
    data = get_realistic_fake_data()
    return data['new_version']

def get_fake_tag():
    """Genera un tag fake basado en la versión actual del proyecto"""
    return get_realistic_fake_data()['current_version']

def get_fake_commits():
    """Genera commits fake pero coherentes"""
    return [
        ("abc1234", "feat: Add new feature"),
        ("def5678", "fix: Fix critical bug"),
        ("ghi9012", "docs: Update documentation")
    ]


def run_command(cmd, dry_run=False, description="", stream_output=False):
    """Execute or display a Plumbum command based on dry-run mode
    
    Args:
        cmd: Plumbum command to execute
        dry_run: If True, only show what would be executed
        description: Human-readable description of the command
        stream_output: If True, stream output in real-time (useful for long-running commands)
    """
    if not dry_run:
        try:
            if stream_output:
                # Use popen for real-time output streaming
                import subprocess
                cmd_str = str(cmd)
                print(f"Executing: {cmd_str}")
                print("-" * 60)
                
                # Start the process with real-time output
                process = subprocess.Popen(
                    cmd_str,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    shell=True
                )
                
                # Stream output line by line
                output_lines = []
                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    if line:
                        # Print the line immediately and store it
                        print(line.rstrip())
                        output_lines.append(line.rstrip())
                
                # Wait for process to complete
                return_code = process.wait()
                print("-" * 60)
                
                if return_code != 0:
                    raise ProcessExecutionError(cmd_str, return_code, "", "\n".join(output_lines))
                
                return "\n".join(output_lines)
            else:
                # Use normal Plumbum execution for quick commands
                return cmd()
        except ProcessExecutionError as e:
            raise
    else:
        # Show the exact command that would be executed
        cmd_str = str(cmd)
        if description:
            print(f"[DRY-RUN] {description}")
            print(f"[DRY-RUN] Command: {cmd_str}")
        else:
            print(f"[DRY-RUN] {cmd_str}")
        
        if stream_output:
            print(f"[DRY-RUN] (This command would stream output in real-time)")
        
        return ""


def get_current_commit_hash(dry_run=False):
    """
    Get the short hash of the current commit using Plumbum
    Returns the commit hash or None if there's an error
    """
    if dry_run:
        return get_fake_commit_hash()
    
    try:
        return git["rev-parse", "--short", "HEAD"]().strip()
    except ProcessExecutionError as e:
        print(f"Error getting current commit hash: {e}")
        return None


def get_last_tag(dry_run=False):
    """
    Get the name of the last tag in the git repository using Plumbum
    Returns the tag name or None if no tags exist
    """
    if dry_run:
        return get_fake_tag()
    
    try:
        return git["describe", "--tags", "--abbrev=0"]().strip()
    except ProcessExecutionError:
        print("No tags found or error getting tags")
        return None


def get_recent_commits(since_tag=None, dry_run=False):
    """
    Get all commit messages since the specified tag using Plumbum
    Returns a list of tuples containing (commit_hash, commit_message)
    """
    if dry_run:
        return get_fake_commits()
    
    try:
        if since_tag:
            start_tag = since_tag
        else:
            # Try to determine the current major.minor version from version.py
            current_version = None
            try:
                with open(VERSION_FILE, 'r', encoding='utf-8') as f:
                    content = f.read()
                    major_match = re.search(r'MAJOR = (\d+)', content)
                    minor_match = re.search(r'MINOR = (\d+)', content)
                    
                    if major_match and minor_match:
                        major = major_match.group(1)
                        minor = int(minor_match.group(1))-1
                        current_version = f"v{major}.{minor}"
                        print(f"Current version detected as {current_version}.x")
            except Exception as e:
                print(f"Error reading version.py: {e}")
                
            # Get all tags in chronological order using Plumbum
            try:
                all_tags_unfiltered = git["tag", "--sort=creatordate"]().strip().split('\n')
                
                # Filter out tags with -docker or -cli, and prioritize SCLogAnalyzer tags
                all_tags = [tag for tag in all_tags_unfiltered 
                           if tag and "-docker" not in tag and "-cli" not in tag]
                
                print(f"Found {len(all_tags_unfiltered)} total tags, {len(all_tags)} after filtering")
                
                start_tag = None
                
                if current_version and all_tags:
                    # Find the first tag in the current version series
                    version_pattern = re.compile(rf'^{re.escape(current_version)}\.(\d+)')
                    current_series_tags = [tag for tag in all_tags if version_pattern.match(tag)]
                    
                    if current_series_tags:
                        first_tag_in_series = current_series_tags[0]
                        print(f"First tag in current series: {first_tag_in_series}")
                        
                        # Find the tag immediately before the first tag in the current series
                        try:
                            first_tag_index = all_tags.index(first_tag_in_series)
                            if first_tag_index > 0:
                                start_tag = all_tags[first_tag_index - 1]
                                print(f"Using previous tag: {start_tag}")
                            else:
                                print("First tag in current series is the oldest tag")
                                start_tag = first_tag_in_series
                        except ValueError:
                            print("Could not find first tag in array (should never happen)")
                            start_tag = get_last_tag()
                    else:
                        print(f"No tags found for current version {current_version}.x")
                        start_tag = get_last_tag()
                else:
                    print("Could not determine version or no tags found")
                    start_tag = get_last_tag()
            except ProcessExecutionError as e:
                print(f"Error getting tags: {e}")
                start_tag = get_last_tag()
                
        # Get commits using Plumbum
        if start_tag:
            cmd = git["log", f'{start_tag}..HEAD', "--pretty=format:%h|||%s"]
            print(f"Getting commits from {start_tag} to HEAD")
        else:
            cmd = git["log", "-5", "--pretty=format:%h|||%s"]
            print("No starting tag found, getting last 5 commits")
            
        result = cmd()
        commits = []
        for line in result.strip().split('\n'):
            if line and '|||' in line:
                hash_val, message = line.split('|||', 1)
                commits.append((hash_val.strip(), message.strip()))
        return commits
    except ProcessExecutionError as e:
        print(f"Error fetching git commits: {e}")
        return []


def update_commit_messages(content, commits):
    """
    Update the COMMIT_MESSAGES list in version.py
    Organizes commits by version tag to show all changes since major.minor.0
    """
    # Get all tags and their commit hashes using Plumbum
    try:
        result = git["tag", "--format=%(refname:short)|||%(objectname:short)"]()
        tag_info = {}
        for line in result.strip().split('\n'):
            if line and '|||' in line:
                tag, hash_val = line.split('|||', 1)
                tag_info[hash_val.strip()] = tag.strip()
    except ProcessExecutionError:
        tag_info = {}

    # Get current version info
    current_version = None
    try:
        with open(VERSION_FILE, 'r', encoding='utf-8') as f:
            content_version = f.read()
            major_match = re.search(r'MAJOR = (\d+)', content_version)
            minor_match = re.search(r'MINOR = (\d+)', content_version)
            if major_match and minor_match:
                major = major_match.group(1)
                minor = minor_match.group(1)
                current_version = f"v{major}.{minor}"
    except Exception:
        pass

    # Format the commits as a Python list of strings
    commits_lines = []
    if current_version:
        commits_lines.append(f"    # Commits for {current_version}.x series")
    current_tag_section = None
    commits_reversed = commits  # commits ya está en orden más reciente primero
    for hash_val, message in commits_reversed:
        if hash_val in tag_info:
            tag = tag_info[hash_val]
            commits_lines.append(f"\n    # Version {tag}")
            current_tag_section = tag
        escaped_message = message.replace('"', '\\"')
        commits_lines.append(f'    "{hash_val}: {escaped_message}"')
    # Unir las líneas con comas, pero sin coma final extra
    commits_str = "[\n" + ",\n".join(commits_lines) + "\n]"

    # Regex robusto: busca desde 'COMMIT_MESSAGES' hasta un ']' que esté solo en una línea (fin de la lista)
    commit_pattern = re.compile(r'COMMIT_MESSAGES\s*=\s*\[.*?^\s*\]\s*', re.DOTALL | re.MULTILINE)
    commit_match = commit_pattern.search(content)

    if commit_match:
        # Replace existing COMMIT_MESSAGES y cualquier texto residual tras el cierre
        content = content.replace(commit_match.group(0), f"COMMIT_MESSAGES = {commits_str}\n")
        print("Updated commit messages in version.py")
    else:
        # Add COMMIT_MESSAGES if it doesn't exist
        content += f"\n\n# Recent commit messages\nCOMMIT_MESSAGES = {commits_str}\n"
        print("Added commit messages to version.py")
    return content


def increase_version(content, key='MINOR', save=False):
    pattern = re.compile(key+r' = (\d+)')
    match = pattern.search(content)
        
    if match:
        old_value = int(match.group(1))
        new_value = old_value + 1
        if new_value > 99:
            new_value = 0
        if save:
            content = content.replace(f"{key} = {old_value}", f"{key} = {new_value}")
    return content, old_value, new_value


def increment_version_unified(increment_type, maturity=None, dry_run=False):
    """
    Función unificada para incrementar versiones
    
    Args:
        increment_type: 'release', 'minor', 'major'
        maturity: string de madurez (requerido para minor/major)
        dry_run: modo de prueba
    
    Returns:
        calculated_version string, True (para release), o False en caso de error
    """
    # Validar parámetros
    if increment_type not in ['release', 'minor', 'major']:
        print(f"Error: increment_type debe ser 'release', 'minor' o 'major', recibido: {increment_type}")
        return False
    
    if increment_type in ['minor', 'major'] and not maturity:
        print(f"Error: maturity es requerido para incremento {increment_type}")
        return False
    
    try:
        # Leer valores actuales de version.py
        spec = importlib.util.spec_from_file_location("version", VERSION_FILE)
        version_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(version_module)
        
        current_major = version_module.MAJOR
        current_minor = version_module.MINOR
        current_release = version_module.RELEASE
        
        # Calcular nuevos valores según el tipo de incremento
        if increment_type == 'release':
            new_major = current_major
            new_minor = current_minor
            new_release = current_release + 1
            if new_release > 99:
                new_release = 0
            calculated_version = None  # Para release, no calculamos versión completa
        elif increment_type == 'minor':
            new_major = current_major
            new_minor = current_minor + 1
            if new_minor > 99:
                new_minor = 0
            new_release = 0
        elif increment_type == 'major':
            new_major = current_major + 1
            if new_major > 99:
                new_major = 0
            new_minor = 0
            new_release = 0
        
        # Obtener commit hash
        commit_hash = get_current_commit_hash(dry_run=dry_run)
        
        # Calcular versión para minor/major
        if increment_type in ['minor', 'major']:
            calculated_version = f"v{new_major}.{new_minor}.{new_release}-{commit_hash}-{maturity}"
        
        if not dry_run:
            # Leer archivo y hacer cambios reales
            with open(VERSION_FILE, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Aplicar cambios según el tipo
            if increment_type == 'release':
                content, old_release, new_release = increase_version(content, 'RELEASE', True)
            elif increment_type == 'minor':
                content, old_minor, new_minor = increase_version(content, 'MINOR', True)
                content = re.sub(r'RELEASE = \d+', 'RELEASE = 0', content)
                content = re.sub(r'MATURITY = [\'"].*?[\'"]', f'MATURITY = "{maturity}"', content)
            elif increment_type == 'major':
                content, old_major, new_major = increase_version(content, 'MAJOR', True)
                content = re.sub(r'MINOR = \d+', 'MINOR = 0', content)
                content = re.sub(r'RELEASE = \d+', 'RELEASE = 0', content)
                content = re.sub(r'MATURITY = [\'"].*?[\'"]', f'MATURITY = "{maturity}"', content)
            
            # Actualizar PATCH con commit hash
            if commit_hash:
                patch_pattern = re.compile(r'PATCH = [\'"]?([^\'"]+)[\'"]?')
                patch_match = patch_pattern.search(content)
                if patch_match:
                    old_patch = patch_match.group(1)
                    content = content.replace(f'PATCH = "{old_patch}"' if '"' in patch_match.group(0) else f"PATCH = '{old_patch}'", f'PATCH = "{commit_hash}"')
                    if increment_type == 'release':
                        print(f'Patch version set to commit hash: "{commit_hash}"')
            else:
                print("Warning: Unable to get current commit hash, PATCH version not updated")
            
            # Obtener y actualizar commit messages
            if increment_type == 'release':
                print("Getting commits from the first tag of the current major.minor version")
            commits = get_recent_commits(dry_run=dry_run)
            if commits:
                content = update_commit_messages(content, commits)
                
            # Escribir archivo
            with open(VERSION_FILE, 'w', encoding='utf-8') as file:
                file.write(content)
        else:
            # Modo dry-run
            if increment_type == 'release':
                data = get_realistic_fake_data()
                print(f"[DRY-RUN] Update version.py: RELEASE {data['old_release']} → {data['new_release']}, PATCH → {data['commit_hash']}")
            elif increment_type == 'minor':
                print(f"[DRY-RUN] Update version.py: MINOR {current_minor} → {new_minor}, RELEASE → 0, MATURITY → {maturity}")
            elif increment_type == 'major':
                print(f"[DRY-RUN] Update version.py: MAJOR {current_major} → {new_major}, MINOR → 0, RELEASE → 0, MATURITY → {maturity}")
        
        # Imprimir resultado
        if increment_type == 'release':
            print(f"Version incremented from {current_release} to {new_release}")
            return True
        elif increment_type == 'minor':
            print(f"Minor version incremented from {current_minor} to {new_minor}, release reset to 0, maturity set to {maturity}")
            return calculated_version
        elif increment_type == 'major':
            print(f"Major version incremented from {current_major} to {new_major}, minor and release reset to 0, maturity set to {maturity}")
            return calculated_version
            
    except Exception as e:
        print(f"Error incrementing {increment_type} version: {e}")
        return False


def get_version():
    """
    Get the current version from version.py
    """
    try:
        # Import version.py dynamically
        spec = importlib.util.spec_from_file_location("version", VERSION_FILE)
        version_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(version_module)
        return version_module.get_version()
    except Exception as e:
        print(f"Error getting version: {e}")
        return None


def commit_and_push_changes(version, push=False, dry_run=False):
    """
    Commit version.py changes and push to repository using Plumbum
    """
    try:
        # Use the version that was calculated by the increment functions
        display_version = version
            
        run_command(git["add", str(VERSION_FILE)], 
                   dry_run=dry_run, description=f"Stage version.py changes")
        run_command(git["commit", "-m", f"[chore] Increment version to {display_version}"], 
                   dry_run=dry_run, description=f"Commit version {display_version}")
        
        print(f"Changes committed for version {display_version}")
        
        if push:
            print("Pushing changes to remote repository...")
            run_command(git["push"], 
                       dry_run=dry_run, description="Push to remote repository")
        else:
            print("Skipping push to remote repository. Use --push to push changes.")
        
        return True
    except ProcessExecutionError as e:
        print(f"Error committing/pushing changes: {e}")
        return False


def get_latest_tag(dry_run=False):
    """Get the latest tag using Plumbum"""
    if dry_run:
        return get_fake_tag()
    
    try:
        return git["describe", "--tags", "--abbrev=0"]().strip()
    except ProcessExecutionError:
        print("No tags found. Proceeding with build.")
        return None


def get_commit_hash(ref, dry_run=False):
    """Get commit hash for a reference using Plumbum"""
    if dry_run:
        return get_fake_commit_hash()
    
    try:
        return git["rev-list", "-n", "1", ref]().strip()
    except ProcessExecutionError:
        return None


def get_head_commit(dry_run=False):
    """Get HEAD commit hash using Plumbum"""
    if dry_run:
        return get_fake_commit_hash()
    
    try:
        return git["rev-parse", "HEAD"]().strip()
    except ProcessExecutionError:
        return None


def should_auto_increment_and_push(dry_run=False):
    """
    Determine if we should automatically increment version AND push
    Returns: (should_increment: bool, should_push: bool, reason: str)
    """
    # En dry-run mode, saltarse todas las validaciones y simular éxito
    if dry_run:
        return True, True, "Found 3 non-chore commits - increment and push (simulated)"
        
    try:
        # Check 1: Are there uncommitted .py files?
        status_output = git["status", "--porcelain"]()
        lines = status_output.strip().split('\n') if status_output.strip() else []
        py_changes = [line for line in lines if line and line[-3:] == '.py']
        py_changes = [line for line in py_changes 
                     if not any(exclude in line for exclude in ['build.py', 'build_plumbum.py'])]
        
        if py_changes:
            return True, False, "Uncommitted .py files found - increment only"
        
        # Check 2: Are there new commits since last tag?
        latest_tag = get_latest_tag(dry_run=dry_run)
        if not latest_tag:
            return True, False, "No tags found - increment only"
            
        tag_commit = get_commit_hash(latest_tag, dry_run=dry_run)
        head_commit = get_head_commit(dry_run=dry_run)
        
        if tag_commit == head_commit:
            return False, False, "No new commits since last tag"
        
        # Check 3: Are there non-[chore] commits?
        try:
            messages = git["log", f'{latest_tag}..HEAD', "--pretty=format:%s"]().strip().split('\n')
            messages = [msg.strip() for msg in messages if msg.strip()]
            
            non_chore_commits = [msg for msg in messages if not msg.lower().startswith('[chore]') or not msg.lower().startswith('chore:')]
            
            if not non_chore_commits:
                return False, False, "Only [chore] commits since last tag"
            
            return True, True, f"Found {len(non_chore_commits)} non-chore commits - increment and push"
            
        except ProcessExecutionError:
            return True, False, "Error checking commits - increment only"
            
    except ProcessExecutionError as e:
        print(f"Error in auto-detection: {e}")
        return True, False, "Error in detection - increment only"


def create_and_push_tag(version, is_test=False, push=False, dry_run=False):
    """
    Create a git tag and push it to the repository using Plumbum
    """
    try:
        # Use the version that was calculated by the increment functions
        tag_version = f"test-{version}" if is_test else version

        latest_tag = get_latest_tag(dry_run=dry_run)
        # Skip commit validations in dry-run mode
        if latest_tag and not dry_run:
            tag_commit = get_commit_hash(latest_tag, dry_run=dry_run)
            head_commit = get_head_commit(dry_run=dry_run)
            if tag_commit and head_commit and tag_commit == head_commit:
                print(f"[ABORT] No se crea el tag '{tag_version}' porque no hay commits nuevos desde el último tag ({latest_tag}).")
                return False
            
            # Check if only commit is a version bump (skip in dry-run mode)
            messages = git["log", f'{latest_tag}..HEAD', "--pretty=format:%s"]().strip().split('\n')
            messages = [msg.strip() for msg in messages if msg.strip()]
            if len(messages) == 1 and messages[0].lower().startswith('increment version to'):
                print(f"[ABORT] No se crea el tag '{tag_version}' porque el único commit nuevo desde el último tag es un bump de versión.")
                return False

        print(f"Creating tag: {tag_version}")
        run_command(git["tag", "-a", tag_version, "-m", f"Version {tag_version}"], 
                   dry_run=dry_run, description=f"Create tag {tag_version}")

        if push:
            print(f"Pushing tag {tag_version} to remote repository...")
            run_command(git["push", "origin", tag_version], 
                       dry_run=dry_run, description=f"Push tag {tag_version}")
        else:
            print(f"Tag {tag_version} created. Use --push to push it to the remote repository.")

        return True
    except ProcessExecutionError as e:
        print(f"Error creating/pushing tag: {e}")
        return False


def activate_venv():
    """
    Activate the virtual environment using Plumbum and update command references
    """
    global pip, pyinstaller, python
    
    venv_path = VENV_DIR
    activate_script = venv_path / "Scripts" / "activate.bat"
    if not activate_script.exists():
        print("Virtual environment not found. Creating...")
        try:
            python["-m", "venv", str(venv_path)]()
            print("Virtual environment created.")
        except ProcessExecutionError as e:
            print(f"Error creating virtual environment: {e}")
            return False
            
    print("Activating virtual environment...")
    os.environ['VIRTUAL_ENV'] = str(venv_path)
    os.environ['PATH'] = f"{venv_path / 'Scripts'}{os.pathsep}{os.environ['PATH']}"
    
    # Update Plumbum command references to use venv executables
    venv_python = venv_path / "Scripts" / "python.exe"
    venv_pip = venv_path / "Scripts" / "pip.exe"
    venv_pyinstaller = venv_path / "Scripts" / "pyinstaller.exe"
    
    if venv_python.exists():
        python = local[str(venv_python)]
        pip = local[str(venv_python)]["-m", "pip"]
        print(f"Using venv python: {venv_python}")
    
    if venv_pyinstaller.exists():
        pyinstaller = local[str(venv_pyinstaller)]
        print(f"Using venv pyinstaller: {venv_pyinstaller}")
    else:
        # PyInstaller might not be installed yet, use pip to install it first
        print(f"PyInstaller not found in {venv_pyinstaller}, will be installed with requirements")
    
    return True


def install_requirements(dry_run=False):
    """
    Install Python requirements from requirements.txt using Plumbum
    """
    global pyinstaller
    
    requirements_file = ROOT_DIR / "requirements.txt"
    if requirements_file.exists():
        try:
            print("Installing requirements...")
            run_command(pip["install", "-r", str(requirements_file)], 
                       dry_run=dry_run, description="Install Python requirements", stream_output=True)
            print("Requirements installed successfully")
            
            # Update PyInstaller reference after installation
            venv_pyinstaller = VENV_DIR / "Scripts" / "pyinstaller.exe"
            if not dry_run and venv_pyinstaller.exists():
                pyinstaller = local[str(venv_pyinstaller)]
                print(f"Updated to use venv pyinstaller: {venv_pyinstaller}")
            elif dry_run:
                # In dry-run, also update the reference for correct command display
                pyinstaller = local[str(venv_pyinstaller)]
                print(f"[DRY-RUN] Would update to use venv pyinstaller: {venv_pyinstaller}")
            
            return True
        except ProcessExecutionError as e:
            print(f"Error installing requirements: {e}")
            return False
    else:
        print("Requirements file not found")
        return False




def build_pyinstaller_command(target_file, name, windowed=True):
    """
    Build PyInstaller command using Plumbum's elegant syntax
    """
    cmd = pyinstaller["--onefile", "--clean"]
    
    # Add mode
    if windowed:
        cmd = cmd["--windowed"]
    else:
        cmd = cmd["--console"]
    
    # Add data files
    cmd = cmd["--add-data", f"{CONFIG_TEMPLATE};."]
    cmd = cmd["--add-data", f"{SRC_DIR / 'assets' / 'icon_connection_red.png'};assets"]
    cmd = cmd["--add-data", f"{SRC_DIR / 'assets' / 'icon_connection_green.png'};assets"]
    cmd = cmd["--add-data", f"{SRC_DIR / 'assets' / 'SCLogAnalyzer.ico'};assets"]
    
    # Add binaries
    cmd = cmd["--add-binary", f"{VENV_DIR / 'Lib' / 'site-packages' / 'pyzbar' / 'libiconv.dll'};."]
    cmd = cmd["--add-binary", f"{VENV_DIR / 'Lib' / 'site-packages' / 'pyzbar' / 'libzbar-64.dll'};."]
    
    # Add icon and name
    cmd = cmd["--icon", "src/assets/SCLogAnalyzer.ico"]
    cmd = cmd["--name", name, target_file]
    
    return cmd


def build_executables(windowed=True, dry_run=False):
    """
    Build executables using PyInstaller with Plumbum
    """
    if not DIST_DIR.exists():
        DIST_DIR.mkdir(parents=True)
    
    try:
        # Always build SCLogAnalyzer.exe
        print("Building SCLogAnalyzer GUI app...")
        cmd = build_pyinstaller_command(f"{SRC_DIR / 'gui.py'}", "SCLogAnalyzer", windowed=windowed)
        run_command(cmd, dry_run=dry_run, description="Build SCLogAnalyzer executable", stream_output=True)
               
        return True
    except ProcessExecutionError as e:
        print(f"Error building executables: {e}")
        return False


def build_nuitka_command(target_file, windowed=True):
    """
    Build Nuitka command using Plumbum's elegant syntax
    Equivalent to the command in build_nuitka.bat
    """
    cmd = nuitka["--standalone", "--follow-imports", "--onefile"]
    
    # Add mode
    if windowed:
        cmd = cmd["--windows-console-mode=disable"]
    
    # Add package includes (using = syntax)
    packages = ["wx", "pyzbar", "watchdog", "_distutils_hack", "setuptools"]
    for package in packages:
        cmd = cmd[f"--include-package={package}"]
    
    # Add data files (using = syntax)
    cmd = cmd[f"--include-data-files={CONFIG_TEMPLATE}=config.json.template"]
    
    # Add pyzbar data directory (using = syntax)
    pyzbar_path = VENV_DIR / "Lib" / "site-packages" / "pyzbar"
    cmd = cmd[f"--include-data-dir={pyzbar_path}=pyzbar"]
    
    # Add icon and output settings (using = syntax)
    cmd = cmd[f"--windows-icon-from-ico={SRC_DIR / 'assets' / 'SCLogAnalyzer.ico'}"]
    cmd = cmd[f"--output-dir={NUITKA_BUILD_DIR}"]
    cmd = cmd[target_file]
    
    return cmd


def build_nuitka_executable(windowed=True, dry_run=False):
    """
    Build executable using Nuitka with Plumbum
    Replicates the functionality of build_nuitka.bat
    """
    try:
        # Create nuitka-build directory
        if not NUITKA_BUILD_DIR.exists():
            NUITKA_BUILD_DIR.mkdir(parents=True)
            print(f"Created {NUITKA_BUILD_DIR} directory")
        
        if not DIST_DIR.exists():
            DIST_DIR.mkdir(parents=True)
            print(f"Created {DIST_DIR} directory")
        
        # Build with Nuitka
        print("Building SCLogAnalyzer with Nuitka...")
        cmd = build_nuitka_command(f"{SRC_DIR / 'gui.py'}", windowed=windowed)
        run_command(cmd, dry_run=dry_run, description="Build with Nuitka", stream_output=True)
        
        # Copy the final executable to dist folder with better name
        if not dry_run:
            source_exe = NUITKA_BUILD_DIR / "gui.exe"
            target_exe = DIST_DIR / "SCLogAnalyzer-nuitka.exe"
            
            if source_exe.exists():
                shutil.copy2(source_exe, target_exe)
                print(f"\nBuild successful! Executable is at {target_exe}")
            else:
                print("\nBuild failed. gui.exe not found in nuitka-build directory.")
                return False
        else:
            print(f"[DRY-RUN] Copy gui.exe to dist/SCLogAnalyzer-nuitka.exe")
        
        return True
        
    except ProcessExecutionError as e:
        print(f"Error building with Nuitka: {e}")
        return False


def main():
    """
    Main function to run the build process using Plumbum
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Build SC Log Analyzer with Plumbum')
    parser.add_argument('--push', '-p', action='store_true', help='Push changes to remote repository')
    parser.add_argument('--increment', '-i', action='store_true', help='Increment version')
    parser.add_argument('--minor', type=str, metavar='MATURITY', 
                       help='Increment minor version and set maturity (e.g., --minor alpha)')
    parser.add_argument('--major', type=str, metavar='MATURITY', 
                       help='Increment major version and set maturity (e.g., --major beta)')
    parser.add_argument('--build', '-b', action='store_true', help='Build executables with PyInstaller')
    parser.add_argument('--nuitka', '-n', action='store_true', help='Build executable with Nuitka')
    parser.add_argument('--test', '-t', action='store_true', help='Mark as test version')
    parser.add_argument('--skip-venv', action='store_true', help='Skip virtual environment activation')
    parser.add_argument('--skip-requirements', action='store_true', help='Skip installing requirements')
    parser.add_argument('--console', '-c', action='store_true', help='Build executable in console mode')
    parser.add_argument('--dry-run', '-d', action='store_true', 
                       help='Show commands that would be executed without running them')
    parser.add_argument('--venv-dir', default=DEFAULT_VENV_NAME,
                        help='Relative path/name of the virtual environment directory (default: .venv)')
    args = parser.parse_args()
    
    global VENV_DIR

    # Apply CLI venv selection
    VENV_DIR = ROOT_DIR / args.venv_dir

    # Add dry-run info
    if args.dry_run:
        print("[DRY-RUN MODE] Showing commands that would be executed")
        print("=" * 60)
    
    # Validar que solo se use una operación de versión a la vez
    version_ops = [args.increment, args.minor, args.major]
    version_ops_count = sum(1 for op in version_ops if op)
    if version_ops_count > 1:
        print("Error: Solo se puede usar una operación de versión a la vez (--increment, --minor, --major)")
        return 1
    
    # Smart default behavior: auto-increment and optionally auto-push
    if not (args.increment or args.minor or args.major or args.build or args.nuitka):
        should_increment, should_push, reason = should_auto_increment_and_push(dry_run=args.dry_run)
        print(f"Auto-detection: {reason}")
        
        if should_increment:
            args.increment = True
            if should_push and not args.push:  # Only set if not explicitly specified
                args.push = True
                print("Auto-enabling push due to non-chore commits and clean working directory")
        else:
            print("No action needed - no new non-chore commits found")
            return 0
    
        
    # Step 1: Version operations
    version = None
    if args.increment:
        print("=== Step 1: Incrementing version (RELEASE) ===")
        
        # Check for modified .py files (excluding build.py) - Skip in dry-run mode
        if not args.dry_run:
            try:
                status_output = git["status", "--porcelain"]()
                lines = status_output.strip().split('\n')
                py_changes = [line for line in lines if line and line[-3:] == '.py']
                py_changes = [line for line in py_changes if not line.endswith('src/build.py') and not line.endswith('src\\build.py') and not line.endswith('src/build_plumbum.py')]
                if py_changes:
                    print("[ABORT] No se incrementa la versión porque hay archivos .py con cambios sin commitear (excluyendo build.py).")
                    return 1
            except ProcessExecutionError as e:
                print(f"Error checking git status: {e}")
                return 1
        
        # Check for new commits since last tag - Skip in dry-run mode
        if not args.dry_run:
            latest_tag = get_latest_tag(dry_run=args.dry_run)
            if latest_tag:
                tag_commit = get_commit_hash(latest_tag, dry_run=args.dry_run)
                head_commit = get_head_commit(dry_run=args.dry_run)
                if tag_commit and head_commit and tag_commit == head_commit:
                    print(f"[ABORT] No se incrementa la versión porque no hay commits nuevos desde el último tag ({latest_tag}).")
                    return 1
        
        increment_version_unified('release', dry_run=args.dry_run)
        
        # Get the current version
        version = get_version()
        if not version:
            print("Error: Failed to get version. Exiting.")
            return 1
        
        print(f"Current version: {version}")
        
        # Commit and push changes
        if not commit_and_push_changes(version, args.push, dry_run=args.dry_run):
            print("Warning: Failed to commit/push changes")
        
        # Create and push tag if --push is specified
        if args.push:
            if not create_and_push_tag(version, args.test, args.push, dry_run=args.dry_run):
                print("Warning: Failed to create/push tag")
        else:
            print("Note: Tag is only created when --push is used.")
    
    elif args.minor:
        print(f"=== Step 1: Incrementing minor version (MATURITY: {args.minor}) ===")
        
        # Check for modified .py files (excluding build.py) - Skip in dry-run mode
        if not args.dry_run:
            try:
                status_output = git["status", "--porcelain"]()
                lines = status_output.strip().split('\n')
                py_changes = [line for line in lines if line and line[-3:] == '.py']
                py_changes = [line for line in py_changes if not line.endswith('src/build.py') and not line.endswith('src\\build.py') and not line.endswith('src/build_plumbum.py')]
                if py_changes:
                    print("[ABORT] No se incrementa la versión porque hay archivos .py con cambios sin commitear (excluyendo build.py).")
                    return 1
            except ProcessExecutionError as e:
                print(f"Error checking git status: {e}")
                return 1
        
        # Check for new commits since last tag - Skip in dry-run mode
        if not args.dry_run:
            latest_tag = get_latest_tag(dry_run=args.dry_run)
            if latest_tag:
                tag_commit = get_commit_hash(latest_tag, dry_run=args.dry_run)
                head_commit = get_head_commit(dry_run=args.dry_run)
                if tag_commit and head_commit and tag_commit == head_commit:
                    print(f"[ABORT] No se incrementa la versión porque no hay commits nuevos desde el último tag ({latest_tag}).")
                    return 1
        
        version = increment_version_unified('minor', maturity=args.minor, dry_run=args.dry_run)
        if not version:
            print("Error: Failed to increment minor version")
            return 1
        
        print(f"Current version: {version}")
        
        # Commit and push changes
        if not commit_and_push_changes(version, args.push, dry_run=args.dry_run):
            print("Warning: Failed to commit/push changes")
        
        # Create and push tag if --push is specified
        if args.push:
            if not create_and_push_tag(version, args.test, args.push, dry_run=args.dry_run):
                print("Warning: Failed to create/push tag")
        else:
            print("Note: Tag is only created when --push is used.")
    
    elif args.major:
        print(f"=== Step 1: Incrementing major version (MATURITY: {args.major}) ===")
        
        # Check for modified .py files (excluding build.py) - Skip in dry-run mode
        if not args.dry_run:
            try:
                status_output = git["status", "--porcelain"]()
                lines = status_output.strip().split('\n')
                py_changes = [line for line in lines if line and line[-3:] == '.py']
                py_changes = [line for line in py_changes if not line.endswith('src/build.py') and not line.endswith('src\\build.py') and not line.endswith('src/build_plumbum.py')]
                if py_changes:
                    print("[ABORT] No se incrementa la versión porque hay archivos .py con cambios sin commitear (excluyendo build.py).")
                    return 1
            except ProcessExecutionError as e:
                print(f"Error checking git status: {e}")
                return 1
        
        # Check for new commits since last tag - Skip in dry-run mode
        if not args.dry_run:
            latest_tag = get_latest_tag(dry_run=args.dry_run)
            if latest_tag:
                tag_commit = get_commit_hash(latest_tag, dry_run=args.dry_run)
                head_commit = get_head_commit(dry_run=args.dry_run)
                if tag_commit and head_commit and tag_commit == head_commit:
                    print(f"[ABORT] No se incrementa la versión porque no hay commits nuevos desde el último tag ({latest_tag}).")
                    return 1
        
        version = increment_version_unified('major', maturity=args.major, dry_run=args.dry_run)
        if not version:
            print("Error: Failed to increment major version")
            return 1
        
        print(f"Current version: {version}")
        
        # Commit and push changes
        if not commit_and_push_changes(version, args.push, dry_run=args.dry_run):
            print("Warning: Failed to commit/push changes")
        
        # Create and push tag if --push is specified
        if args.push:
            if not create_and_push_tag(version, args.test, args.push, dry_run=args.dry_run):
                print("Warning: Failed to create/push tag")
        else:
            print("Note: Tag is only created when --push is used.")
    
    # Step 2: Build executables if requested
    if args.build:
        print("\n=== Step 2: Building executables ===")
        
        # Activate virtual environment
        if not args.skip_venv:
            if not activate_venv():
                print("Error: Failed to activate virtual environment. Exiting.")
                return 1
        
        # Install requirements
        if not args.skip_requirements:
            if not install_requirements(dry_run=args.dry_run):
                print("Warning: Failed to install requirements")
            
        
        # Build executables
        if not build_executables(windowed=not args.console, dry_run=args.dry_run):
            print("Error: Failed to build executables")
            return 1
    
    # Step 3: Build with Nuitka if requested
    if args.nuitka:
        print("\n=== Step 3: Building with Nuitka ===")
        
        # Activate virtual environment
        if not args.skip_venv:
            if not activate_venv():
                print("Error: Failed to activate virtual environment. Exiting.")
                return 1
        
        # Install requirements
        if not args.skip_requirements:
            if not install_requirements(dry_run=args.dry_run):
                print("Warning: Failed to install requirements")
            
        
        # Build with Nuitka
        if not build_nuitka_executable(windowed=not args.console, dry_run=args.dry_run):
            print("Error: Failed to build with Nuitka")
            return 1
                
    print("\nBuild process completed successfully with Plumbum!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
