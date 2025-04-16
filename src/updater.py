#!/usr/bin/env python
import os
import sys
import time
import shutil
import tempfile
import requests
import zipfile
import subprocess
import wx

# Constants for the updater
GITHUB_API_URL = "https://api.github.com/repos/IJOL/SCLogAnalyzer/releases"
APP_EXECUTABLE = "SCLogAnalyzer.exe"  # The main application executable name
UPDATER_EXECUTABLE = "SCLogAnalyzer_updater.exe"  # The updater executable name

def check_for_updates(parent_frame, current_version):
    """
    Check for updates by querying the GitHub API.
    
    Args:
        parent_frame: The parent wx.Frame to show dialogs on
        current_version: The current version string to compare against
        
    Returns:
        bool: True if update check completed, False if error occurred
    """
    try:
        response = requests.get(GITHUB_API_URL)
        if response.status_code != 200:
            wx.MessageBox("Failed to check for updates.", "Error", wx.OK | wx.ICON_ERROR)
            return False

        releases = response.json()
        if not isinstance(releases, list) or not releases:
            wx.MessageBox("No releases found.", "Error", wx.OK | wx.ICON_ERROR)
            return False

        # Find the latest release named SCLogAnalyzer
        latest_release = max(
            (release for release in releases if release.get("name").startswith("SCLogAnalyzer")),
            key=lambda r: r.get("published_at", ""),
            default=None
        )

        if not latest_release:
            wx.MessageBox("No valid release named 'SCLogAnalyzer' found.", "Error", wx.OK | wx.ICON_ERROR)
            return False

        latest_version = latest_release.get("tag_name", "").split('-')[0].lstrip('v')
        download_url = latest_release.get("assets", [{}])[0].get("browser_download_url")

        if not latest_version or not download_url:
            wx.MessageBox("Invalid release information.", "Error", wx.OK | wx.ICON_ERROR)
            return False

        # Remove 'v' prefix and extract version
        clean_current_version = current_version.split('-')[0].lstrip('v')  

        # Compare versions numerically
        def version_to_tuple(version):
            return tuple(map(int, version.split('.')))

        if version_to_tuple(latest_version) > version_to_tuple(clean_current_version):
            if wx.MessageBox(f"A new version ({latest_version}) is available. Do you want to update?",
                            "Update Available", wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
                download_and_update(parent_frame, download_url)
        
        return True
    except Exception as e:
        wx.MessageBox(f"Error checking for updates: {e}", "Error", wx.OK | wx.ICON_ERROR)
        return False

def download_and_update(parent_frame, download_url):
    """
    Download the update and replace the running application.
    
    Args:
        parent_frame: The parent wx.Frame to show dialogs on
        download_url: URL to download the update from
    """
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create and configure the progress dialog - we'll reuse it for all steps
            progress_dialog = wx.ProgressDialog(
                "Updating SCLogAnalyzer",
                "Starting update process...",
                maximum=100,
                parent=parent_frame,
                style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_SMOOTH | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME | wx.PD_CAN_ABORT
            )
            progress_dialog.SetSize((500, -1))
            
            # Step 1: Download the update file (50% of overall progress)
            temp_file = os.path.join(temp_dir, "update.zip")
            continue_update, skip = True, False
            
            try:
                # Update progress dialog for download phase
                progress_dialog.Update(0, "Downloading update package...")
                
                # Start download with stream=True to get content length and update progress
                with requests.get(download_url, stream=True) as response:
                    response.raise_for_status()
                    
                    # Get total file size if available
                    total_size = int(response.headers.get('content-length', 0))
                    block_size = 8192  # 8KB blocks
                    downloaded = 0
                    
                    with open(temp_file, "wb") as f:
                        for chunk in response.iter_content(chunk_size=block_size):
                            if chunk:  # filter out keep-alive new chunks
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                # Update progress bar - download is 50% of overall process
                                if total_size > 0:
                                    progress = int((downloaded / total_size) * 50)  # 0-50% for download
                                    continue_update, skip = progress_dialog.Update(
                                        progress, 
                                        f"Downloading: {int((downloaded / total_size) * 100)}% complete"
                                    )
                                else:
                                    # If size unknown, just pulse
                                    continue_update, skip = progress_dialog.Pulse(
                                        f"Downloaded {downloaded/1024:.1f} KB"
                                    )
                                
                                # Check if user canceled
                                if not continue_update:
                                    progress_dialog.Destroy()
                                    return
                
                # Step 2: Extract the update (75% of overall progress)
                progress_dialog.Update(50, "Extracting update files...")
                update_dir = os.path.join(temp_dir, "update")
                os.makedirs(update_dir, exist_ok=True)
                
                # Unpack and track progress
                with zipfile.ZipFile(temp_file, 'r') as zip_ref:
                    file_list = zip_ref.namelist()
                    total_files = len(file_list)
                    
                    for i, file in enumerate(file_list):
                        zip_ref.extract(file, update_dir)
                        # Update progress - extraction is 25% of overall process (50-75%)
                        progress = 50 + int((i + 1) / total_files * 25)
                        continue_update, skip = progress_dialog.Update(
                            progress, 
                            f"Extracting: {i+1} of {total_files} files"
                        )
                        if not continue_update:
                            progress_dialog.Destroy()
                            return
                
                # Step 3: Prepare installation (75-90% of overall progress)
                progress_dialog.Update(75, "Preparing to install update...")
                
                # Create updater executable
                updated_exe = os.path.join(update_dir, APP_EXECUTABLE)
                persistent_updater_exe = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), UPDATER_EXECUTABLE)
                
                # Copy the updater executable with progress indication
                shutil.copyfile(updated_exe, persistent_updater_exe)
                progress_dialog.Update(90, "Installation files prepared")
                
                # Step 4: Finalize update (90-100% of overall progress)
                progress_dialog.Update(95, "Finalizing update, application will restart...")
                time.sleep(1)  # Short delay to show final message
                progress_dialog.Update(100, "Update complete!")
                progress_dialog.Destroy()
                
                # Launch the updater executable
                subprocess.Popen([persistent_updater_exe, os.path.dirname(os.path.abspath(sys.argv[0])), APP_EXECUTABLE])
                # Exit the current application
                parent_frame.Close()
                sys.exit(0)
                
            except Exception as e:
                if 'progress_dialog' in locals() and progress_dialog:
                    progress_dialog.Destroy()
                wx.MessageBox(f"Error during update process: {e}", "Update Error", wx.OK | wx.ICON_ERROR)
                
    except Exception as e:
        wx.MessageBox(f"Error initializing update process: {e}", "Update Error", wx.OK | wx.ICON_ERROR)

def cleanup_updater_script():
    """Remove the updater executable after an update is complete"""
    updater_exe = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), UPDATER_EXECUTABLE)
    if os.path.exists(updater_exe):
        try:
            os.remove(updater_exe)
            print(f"Cleaned up {UPDATER_EXECUTABLE}.")
        except Exception as e:
            print(f"Failed to clean up {UPDATER_EXECUTABLE}: {e}")

def update_application():
    """Handle the actual update process after the updater has been launched"""
    if len(sys.argv) < 3:
        print(f"Usage: {UPDATER_EXECUTABLE} <target_dir> <app_executable>")
        sys.exit(1)

    target_dir = sys.argv[1]
    app_executable = sys.argv[2]

    # Wait for the main application to exit
    print("Waiting for the main application to exit...")
    time.sleep(5)

    # Replace the original executable with the updated one
    src_file = os.path.abspath(sys.argv[0])  # This script itself (SCLogAnalyzer_updater.exe)
    dest_file = os.path.join(target_dir, app_executable)

    # Retry parameters
    max_attempts = 5
    retry_delay = 2  # seconds
    attempt = 0
    
    while attempt < max_attempts:
        attempt += 1
        try:
            print(f"Attempt {attempt}/{max_attempts} to replace the executable...")
            
            # Try to check if the file is still in use
            try:
                # Try to open the destination file with exclusive access
                with open(dest_file, 'a+b') as test_file:
                    # If we get here, the file is not locked
                    pass
            except PermissionError:
                if attempt < max_attempts:
                    print(f"File {dest_file} is still in use. Waiting {retry_delay} seconds before retry...")
                    time.sleep(retry_delay)
                    # Increase the delay for next attempt with a backoff strategy
                    retry_delay *= 1.5
                    continue
                else:
                    raise Exception("File is still in use after maximum retries")
            
            # Try to replace the file
            if os.path.exists(dest_file):
                os.unlink(dest_file)  # Force delete if exists
                print(f"Removed old executable: {dest_file}")
            
            shutil.copy2(src_file, dest_file)  # Use copy2 to preserve metadata
            print(f"Replaced {dest_file} successfully.")
            break  # Success, exit the retry loop
            
        except Exception as e:
            print(f"Attempt {attempt} failed: {e}")
            if attempt < max_attempts:
                wait_time = retry_delay
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                # Increase the delay for next attempt with a backoff strategy
                retry_delay *= 1.5
            else:
                print(f"Failed to replace {dest_file} after {max_attempts} attempts: {e}")
                sys.exit(1)
    
    # Cleanup the updater file
    try:
        # Small delay to ensure the copy operation is complete
        time.sleep(1)
        os.remove(src_file)
        print(f"Removed updater file: {src_file}")
    except Exception as e:
        print(f"Note: Could not remove updater file: {e}")
        # Continue anyway as this is not critical

    # Restart the application using subprocess instead of execv for better Windows compatibility
    try:
        # Start the application as a new process
        subprocess.Popen([dest_file])
        print(f"Successfully started {dest_file}")
        # Exit the updater process
        sys.exit(0)
    except Exception as e:
        print(f"Failed to restart the application: {e}")
        sys.exit(1)