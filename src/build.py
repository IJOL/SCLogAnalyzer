#!/usr/bin/env python
"""
Build script for SC Log Analyzer
This replaces both the increment_version.py script and build.bat
Run this script to increment the version and build the application
"""

import os
import re
import sys
import subprocess
import argparse
import importlib.util
import shutil
from pathlib import Path

# Directory settings
ROOT_DIR = Path(__file__).parent.parent
SRC_DIR = ROOT_DIR / "src"
VERSION_FILE = SRC_DIR / "version.py"
DIST_DIR = ROOT_DIR / "dist"
CONFIG_TEMPLATE = SRC_DIR / "config.json.template"


def abort_if_uncommitted_py_changes():
    """
    Abort the process if there are uncommitted changes in any .py files
    """
    try:
        result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split('\n')
        py_changes = [line for line in lines if line and line[-3:] == '.py']
        if py_changes:
            print("ERROR: Hay archivos .py con cambios sin commitear. Por favor, commitea o descarta los cambios antes de continuar.")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR al comprobar cambios sin commitear: {e}")
        sys.exit(1)


def get_current_commit_hash():
    """
    Get the short hash of the current commit
    Returns the commit hash or None if there's an error
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.SubprocessError as e:
        print(f"Error getting current commit hash: {e}")
        return None


def get_last_tag():
    """
    Get the name of the last tag in the git repository
    Returns the tag name or None if no tags exist
    """
    try:
        result = subprocess.run(
            ['git', 'describe', '--tags', '--abbrev=0'],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.SubprocessError:
        # If there are no tags or error occurs
        print("No tags found or error getting tags")
        return None


def get_recent_commits(since_tag=None):
    """
    Get all commit messages since the specified tag or from the tag immediately before the first one in the current series
    Returns a list of tuples containing (commit_hash, commit_message)
    """
    try:
        if since_tag:
            # Use the provided tag
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
                        minor = minor_match.group(1)
                        current_version = f"v{major}.{minor}"
                        print(f"Current version detected as {current_version}.x")
            except Exception as e:
                print(f"Error reading version.py: {e}")
                
            # Get all tags in chronological order (oldest to newest)
            try:
                result = subprocess.run(
                    ['git', 'tag', '--sort=creatordate'],
                    capture_output=True, text=True, check=True
                )
                all_tags_unfiltered = result.stdout.strip().split('\n')
                
                # Filter out tags with -docker or -cli, and prioritize SCLogAnalyzer tags
                all_tags = [tag for tag in all_tags_unfiltered 
                           if tag and "-docker" not in tag and "-cli" not in tag]
                
                # Log how many tags were filtered
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
            except subprocess.SubprocessError as e:
                print(f"Error getting tags: {e}")
                start_tag = get_last_tag()
                
        # If we have a starting tag, get commits since that tag, otherwise fall back to last 5 commits
        if start_tag:
            cmd = ['git', 'log', f'{start_tag}..HEAD', '--pretty=format:%h|||%s']
            print(f"Getting commits from {start_tag} to HEAD")
        else:
            # Fallback to last 5 commits if no tag is found
            cmd = ['git', 'log', '-5', '--pretty=format:%h|||%s']
            print("No starting tag found, getting last 5 commits")
            
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True
        )
        commits = []
        for line in result.stdout.strip().split('\n'):
            if line and '|||' in line:
                hash_val, message = line.split('|||', 1)
                commits.append((hash_val.strip(), message.strip()))
        return commits
    except subprocess.SubprocessError as e:
        print(f"Error fetching git commits: {e}")
        return []


def update_commit_messages(content, commits):
    """
    Update the COMMIT_MESSAGES list in version.py
    Organizes commits by version tag to show all changes since major.minor.0
    """
    # Get all tags and their commit hashes to identify version boundaries
    try:
        result = subprocess.run(
            ['git', 'tag', '--format=%(refname:short)|||%(objectname:short)'],
            capture_output=True, text=True, check=True
        )
        tag_info = {}
        for line in result.stdout.strip().split('\n'):
            if line and '|||' in line:
                tag, hash_val = line.split('|||', 1)
                tag_info[hash_val.strip()] = tag.strip()
    except subprocess.SubprocessError:
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
    commits_str = "[\n"
    
    # Add a header comment for clarity
    if current_version:
        commits_str += f"    # Commits for {current_version}.x series\n"
    
    # Track what version we're currently adding commits for
    current_tag_section = None
    
    # Reverse commits to get them in chronological order (oldest first)
    commits_reversed = list(reversed(commits))
    
    for hash_val, message in commits_reversed:
        # Check if this commit has a tag to mark a version boundary
        if hash_val in tag_info:
            tag = tag_info[hash_val]
            # Add a section header for this version
            commits_str += f"\n    # Version {tag}\n"
            current_tag_section = tag
        
        # Escape quotes in the message
        escaped_message = message.replace('"', '\\"')
        
        # Add the commit with appropriate indentation
        commits_str += f'    "{hash_val}: {escaped_message}",\n'
    
    commits_str += "]"
    
    # Regular expression to find the COMMIT_MESSAGES declaration
    commit_pattern = re.compile(r'COMMIT_MESSAGES = \[.*?\]', re.DOTALL)
    commit_match = commit_pattern.search(content)
    
    if commit_match:
        # Replace existing COMMIT_MESSAGES
        content = content.replace(commit_match.group(0), f"COMMIT_MESSAGES = {commits_str}")
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


def increment_version(increment=None):
    """
    Increment the minor version in version.py
    Uses the current commit hash for the patch version
    """
    try:
        with open(VERSION_FILE, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Find and increment the MINOR version
        content, old_minor, new_minor = increase_version(content, 'RELEASE', bool(increment))
        
        # Get current commit hash
        commit_hash = get_current_commit_hash()
        
        # Update the PATCH version with current commit hash
        if commit_hash:
            patch_pattern = re.compile(r'PATCH = [\'"]?([^\'"]+)[\'"]?')
            patch_match = patch_pattern.search(content)
            
            if patch_match:
                old_patch = patch_match.group(1)
                # Use quotes around the commit hash as it's a string
                content = content.replace(f'PATCH = "{old_patch}"' if '"' in patch_match.group(0) else f"PATCH = '{old_patch}'", f'PATCH = "{commit_hash}"')
                print(f'Patch version set to commit hash: "{commit_hash}"')
            else:
                print("Could not find PATCH version in version.py")
        else:
            print("Warning: Unable to get current commit hash, PATCH version not updated")
        
        # Get and update commit messages starting from the first tag of the current major.minor version
        # Calling without parameters triggers automatic tag detection based on current version
        print("Getting commits from the first tag of the current major.minor version")
        commits = get_recent_commits()
        if commits:
            content = update_commit_messages(content, commits)
            
        with open(VERSION_FILE, 'w', encoding='utf-8') as file:
            file.write(content)
        
        print(f"Version incremented from {old_minor} to {new_minor}")
        return True
            
    except Exception as e:
        print(f"Error incrementing version: {e}")
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


def commit_and_push_changes(version, push=False):
    """
    Commit version.py changes and push to repository
    """
    try:
        subprocess.run(['git', 'add', str(VERSION_FILE)], check=True)
        subprocess.run(['git', 'commit', '-m', f"Increment version to {version}"], check=True)
        
        print(f"Changes committed for version {version}")
        
        if push:
            print("Pushing changes to remote repository...")
            subprocess.run(['git', 'push'], check=True)
        else:
            print("Skipping push to remote repository. Use --push to push changes.")
        
        return True
    except subprocess.SubprocessError as e:
        print(f"Error committing/pushing changes: {e}")
        return False


def create_and_push_tag(version, is_test=False, push=False):
    """
    Create a git tag and push it to the repository
    """
    try:
        # Prepend test- to version if this is not an official release
        tag_version = f"test-{version}" if is_test else version
        
        print(f"Creating tag: {tag_version}")
        subprocess.run(['git', 'tag', '-a', tag_version, '-m', f"Version {tag_version}"], check=True)
        
        if push:
            print(f"Pushing tag {tag_version} to remote repository...")
            subprocess.run(['git', 'push', 'origin', tag_version], check=True)
        else:
            print(f"Tag {tag_version} created. Use --push to push it to the remote repository.")
        
        return True
    except subprocess.SubprocessError as e:
        print(f"Error creating/pushing tag: {e}")
        return False


def activate_venv():
    """
    Activate the virtual environment
    """
    venv_path = ROOT_DIR / "venv"
    
    if os.name == 'nt':  # Windows
        activate_script = venv_path / "Scripts" / "activate.bat"
        if not activate_script.exists():
            print("Virtual environment not found. Creating...")
            try:
                subprocess.run(["python", "-m", "venv", str(venv_path)], check=True)
                print("Virtual environment created.")
            except subprocess.SubprocessError as e:
                print(f"Error creating virtual environment: {e}")
                return False
                
        print("Activating virtual environment...")
        os.environ['VIRTUAL_ENV'] = str(venv_path)
        os.environ['PATH'] = f"{venv_path / 'Scripts'}{os.pathsep}{os.environ['PATH']}"
    else:  # Unix/Linux/Mac
        activate_script = venv_path / "bin" / "activate"
        if not activate_script.exists():
            print("Virtual environment not found. Creating...")
            try:
                subprocess.run(["python", "-m", "venv", str(venv_path)], check=True)
                print("Virtual environment created.")
            except subprocess.SubprocessError as e:
                print(f"Error creating virtual environment: {e}")
                return False
                
        print("Activating virtual environment...")
        activate_cmd = f"source {activate_script}"
        subprocess.run(activate_cmd, shell=True, executable="/bin/bash")
    
    return True


def install_requirements():
    """
    Install Python requirements from requirements.txt
    """
    requirements_file = ROOT_DIR / "requirements.txt"
    if requirements_file.exists():
        try:
            print("Installing requirements...")
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(requirements_file)], check=True)
            print("Requirements installed successfully")
            return True
        except subprocess.SubprocessError as e:
            print(f"Error installing requirements: {e}")
            return False
    else:
        print("Requirements file not found")
        return False


def build_executables(build_all=False):
    """
    Build executables using PyInstaller
    """
    if not DIST_DIR.exists():
        DIST_DIR.mkdir(parents=True)
    
    try:
        if build_all or not (DIST_DIR / "log_analyzer.exe").exists():
            print("Building log_analyzer executable...")
            subprocess.run([
                "pyinstaller", "--onefile", "--console", "--clean", 
                "--add-data", f"{CONFIG_TEMPLATE};.", 
                "--name", "log_analyzer", f"{SRC_DIR / 'log_analyzer.py'}"
            ], check=True)
        
        if build_all or not (DIST_DIR / "StatusBoardBot.exe").exists():
            print("Building StatusBoardBot executable...")
            subprocess.run([
                "pyinstaller", "--onefile", "--console", "--clean", 
                "--add-data", f"{SRC_DIR / 'bot' / 'config.json.template'};.", 
                "--name", "StatusBoardBot", f"{SRC_DIR / 'bot' / 'bot.py'}"
            ], check=True)
        
        if build_all or not (DIST_DIR / "SCLogAnalyzer.exe").exists():
            print("Building SCLogAnalyzer GUI app...")
            subprocess.run([
                "pyinstaller", "--onefile", "--windowed", "--clean", 
                "--add-data", f"{CONFIG_TEMPLATE};.", 
                "--add-binary", f"{ROOT_DIR / 'venv' / 'Lib' / 'site-packages' / 'pyzbar' / 'libiconv.dll'};.", 
                "--add-binary", f"{ROOT_DIR / 'venv' / 'Lib' / 'site-packages' / 'pyzbar' / 'libzbar-64.dll'};.", 
                "--name", "SCLogAnalyzer", f"{SRC_DIR / 'gui.py'}"
            ], check=True)
            
        return True
    except subprocess.SubprocessError as e:
        print(f"Error building executables: {e}")
        return False


def create_zip_files():
    """
    Create ZIP files for distribution
    """
    try:
        readme_dir = ROOT_DIR / "dist" / "readme"
        
        # Create zip for log_analyzer
        if (DIST_DIR / "log_analyzer.exe").exists():
            print("Creating log_analyzer.zip...")
            subprocess.run([
                "powershell", "-Command",
                f"Compress-Archive -Path '{DIST_DIR / 'log_analyzer.exe'}', '{readme_dir}' " +
                f"-DestinationPath '{DIST_DIR / 'log_analyzer.zip'}' -Force"
            ], check=True)
        
        # Create zip for StatusBoardBot
        if (DIST_DIR / "StatusBoardBot.exe").exists():
            print("Creating StatusBoardBot.zip...")
            subprocess.run([
                "powershell", "-Command",
                f"Compress-Archive -Path '{DIST_DIR / 'StatusBoardBot.exe'}' " +
                f"-DestinationPath '{DIST_DIR / 'StatusBoardBot.zip'}' -Force"
            ], check=True)
        
        # Create zip for SCLogAnalyzer
        if (DIST_DIR / "SCLogAnalyzer.exe").exists():
            print("Creating SCLogAnalyzer.zip...")
            subprocess.run([
                "powershell", "-Command",
                f"Compress-Archive -Path '{DIST_DIR / 'SCLogAnalyzer.exe'}', '{readme_dir}' " +
                f"-DestinationPath '{DIST_DIR / 'SCLogAnalyzer.zip'}' -Force"
            ], check=True)
            
        return True
    except subprocess.SubprocessError as e:
        print(f"Error creating ZIP files: {e}")
        return False


def get_latest_tag():
    result = subprocess.run(["git", "describe", "--tags", "--abbrev=0"], capture_output=True, text=True)
    if result.returncode != 0:
        print("No tags found. Proceeding with build.")
        return None
    return result.stdout.strip()


def get_commit_hash(ref):
    result = subprocess.run(["git", "rev-list", "-n", "1", ref], capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def get_head_commit():
    result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


latest_tag = get_latest_tag()
if latest_tag:
    tag_commit = get_commit_hash(latest_tag)
    head_commit = get_head_commit()
    if tag_commit and head_commit and tag_commit == head_commit:
        print(f"No new commits since last tag ({latest_tag}). Build stopped.")
        sys.exit(0)


def main():
    """
    Main function to run the build process
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Build SC Log Analyzer')
    parser.add_argument('--push', '-p', action='store_true', help='Push changes to remote repository')
    parser.add_argument('--increment', '-i', action='store_true', help='Increment version')
    parser.add_argument('--build', '-b', action='store_true', help='Build executables')
    parser.add_argument('--all', '-a', action='store_true', help='Perform all steps')
    parser.add_argument('--test', '-t', action='store_true', help='Mark as test version')
    parser.add_argument('--skip-venv', action='store_true', help='Skip virtual environment activation')
    parser.add_argument('--skip-requirements', action='store_true', help='Skip installing requirements')
    parser.add_argument('--skip-zip', action='store_true', help='Skip creating ZIP files')
    
    args = parser.parse_args()
    
    # If no specific actions are specified, enable all
    if not (args.increment or args.build):
        args.increment = True
    
    if args.all:
        args.increment = True
        args.push = True
    
    # Step 1: Increment version if requested
    version = None
    if args.increment:
        print("=== Step 1: Incrementing version ===")
        increment_version(args.increment)
        
        # Get the current version
        version = get_version()
        if not version:
            print("Error: Failed to get version. Exiting.")
            return 1
        
        print(f"Current version: {version}")
        
        # Commit and push changes
        if not commit_and_push_changes(version, args.push):
            print("Warning: Failed to commit/push changes")
        
        # Only create and push tag if --push is specified
        if args.push:
            if not create_and_push_tag(version, args.test, args.push):
                print("Warning: Failed to create/push tag")
        else:
            print("Note: Tag is only created when --push is used. No tag will be created in this run.")
    
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
            if not install_requirements():
                print("Warning: Failed to install requirements")
        
        # Build executables
        if not build_executables(True):
            print("Error: Failed to build executables")
            return 1
        
        # Create ZIP files
        if not args.skip_zip:
            if not create_zip_files():
                print("Warning: Failed to create ZIP files")
    
    print("\nBuild process completed successfully!")
    return 0


if __name__ == "__main__":
    # Check for uncommitted .py changes before anything else
    abort_if_uncommitted_py_changes()
    
    sys.exit(main())