"""
Script to increment the minor version in version.py
Run this before building a new release
"""

import os
import re
import sys

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
        #content, old_minor, new_minor = increase_version(content,'MINOR',bool(increment))
        content, old_minor, new_minor = increase_version(content,'RELEASE',bool(increment))
        
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
            
            with open(version_file_path, 'w', encoding='utf-8') as file:
                file.write(content)
            
            print(f"Minor version incremented from {old_minor} to {new_minor}")
            return True
        else:
            print("Could not find MINOR version in version.py")
            return False
            
    except Exception as e:
        print(f"Error incrementing version: {e}")
        return False

def increase_version(content,key='MINOR',save=False,):
    minor_pattern = re.compile(key+r' = (\d+)')
    minor_match = minor_pattern.search(content)
        
    if minor_match :
        old_minor = int(minor_match.group(1))
        new_minor = old_minor + 1
        if increment is not None:
            content = content.replace(f"{key} = {old_minor}", f"{key} = {new_minor}")
    return content,old_minor,new_minor

if __name__ == "__main__":
    # Check if commit hash was provided as command line argument
    commit_hash = sys.argv[1] if len(sys.argv) > 1 else None
    increment = sys.argv[2] if len(sys.argv) > 2 else None
    increment_minor_version(commit_hash, increment)
