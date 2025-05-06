"""
Script to increment the minor version in version.py
Run this before building a new release
"""

import os
import re
import sys
import subprocess

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
    Get all commit messages since the specified tag or from the beginning of current major.minor version
    Returns a list of tuples containing (commit_hash, commit_message)
    """
    try:
        current_version = None
        if since_tag:
            # Use the provided tag
            start_tag = since_tag
        else:
            # Try to determine the current major.minor version from version.py
            version_file_path = os.path.join(os.path.dirname(__file__), "version.py")
            try:
                with open(version_file_path, 'r', encoding='utf-8') as f:
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
            
            # Find the first tag with the current major.minor version
            try:
                # Get all tags
                result = subprocess.run(
                    ['git', 'tag', '-l'],
                    capture_output=True, text=True, check=True
                )
                all_tags = result.stdout.strip().split('\n')
                
                # Filter tags matching current version pattern
                if current_version:
                    version_pattern = re.compile(rf'^{re.escape(current_version)}\.(\d+)')
                    matching_tags = [tag for tag in all_tags if version_pattern.match(tag)]
                    
                    if matching_tags:
                        # Sort tags by version number
                        matching_tags.sort(key=lambda t: int(version_pattern.match(t).group(1)))
                        start_tag = matching_tags[0]  # First tag of current major.minor
                        print(f"Found starting tag for current version: {start_tag}")
                    else:
                        # If no matching tags found, fall back to last tag
                        start_tag = get_last_tag()
                        print(f"No tags found for current version, using last tag: {start_tag}")
                else:
                    # If version couldn't be determined, use last tag
                    start_tag = get_last_tag()
                    print(f"Could not determine current version, using last tag: {start_tag}")
            except subprocess.SubprocessError as e:
                print(f"Error getting tags: {e}")
                # Fallback to last tag
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
        version_file_path = os.path.join(os.path.dirname(__file__), "version.py")
        with open(version_file_path, 'r', encoding='utf-8') as f:
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

def increment_minor_version(increment=None):
    """
    Increment the minor version in version.py
    Uses the current commit hash for the patch version
    """
    version_file_path = os.path.join(os.path.dirname(__file__), "version.py")
    
    try:
        with open(version_file_path, 'r', encoding='utf-8') as file:
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
        
        # Get the last tag
        last_tag = get_last_tag()
        if last_tag:
            print(f"Getting commits since tag: {last_tag}")
        else:
            print("No tags found, getting recent commits")
            
        # Get and update commit messages since the last tag
        commits = get_recent_commits(last_tag)
        if commits:
            content = update_commit_messages(content, commits)
            
        with open(version_file_path, 'w', encoding='utf-8') as file:
            file.write(content)
        
        print(f"Minor version incremented from {old_minor} to {new_minor}")
        return True
            
    except Exception as e:
        print(f"Error incrementing version: {e}")
        return False

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

if __name__ == "__main__":
    # Check if increment parameter was provided
    increment = sys.argv[1] if len(sys.argv) > 1 else None
    increment_minor_version(increment)
