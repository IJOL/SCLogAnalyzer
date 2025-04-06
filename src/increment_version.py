"""
Script to increment the minor version in version.py
Run this before building a new release
"""

import os
import re
import sys
import subprocess

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
    Get all commit messages since the last tag
    Returns a list of tuples containing (commit_hash, commit_message)
    """
    try:
        # Use git log to get commits since the last tag
        if since_tag:
            cmd = ['git', 'log', f'{since_tag}..HEAD', '--pretty=format:%h|||%s']
        else:
            # Fallback to last 5 commits if no tag is found
            cmd = ['git', 'log', '-5', '--pretty=format:%h|||%s']
            
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
    """
    # Format the commits as a Python list of strings
    commits_str = "[\n"
    for hash_val, message in commits:
        # Escape quotes in the message
        escaped_message = message.replace('"', '\\"')
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

def increment_minor_version(commit_hash=None, increment=None):
    """
    Increment the minor version in version.py
    If commit_hash is provided, set the patch version to this value
    """
    version_file_path = os.path.join(os.path.dirname(__file__), "version.py")
    
    try:
        with open(version_file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Find and increment the MINOR version
        content, old_minor, new_minor = increase_version(content, 'RELEASE', bool(increment))
        
        # If commit hash is provided, set the PATCH version
        if commit_hash is not None:
            patch_pattern = re.compile(r'PATCH = [\'"]?([^\'"]+)[\'"]?')
            patch_match = patch_pattern.search(content)
            
            if patch_match:
                old_patch = patch_match.group(1)
                # Use quotes around the commit hash as it's a string
                content = content.replace(f'PATCH = "{old_patch}"' if '"' in patch_match.group(0) else f"PATCH = '{old_patch}'", f'PATCH = "{commit_hash}"')
                print(f'Patch version set to commit hash: "{commit_hash}"')
            else:
                print("Could not find PATCH version in version.py")
        
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
    # Check if commit hash was provided as command line argument
    commit_hash = sys.argv[1] if len(sys.argv) > 1 else None
    increment = sys.argv[2] if len(sys.argv) > 2 else None
    increment_minor_version(commit_hash, increment)
