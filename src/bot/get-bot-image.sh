#!/bin/bash

# Replace with your GitHub repository details
REPO_OWNER="IJOL"
REPO_NAME="SCLogAnalyzer"

# Fetch the latest release information from GitHub API
LATEST_RELEASE=$(curl -s "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/releases/latest")

# Extract the tag name and Docker artifact URL
TAG_NAME=$(echo "$LATEST_RELEASE" | jq -r '.tag_name')
DOCKER_ARTIFACT_URL=$(echo "$LATEST_RELEASE" | jq -r '.assets[] | select(.name | endswith(".tar.gz")) | .browser_download_url')

# Check if the tag name and artifact URL were retrieved successfully
if [ -z "$TAG_NAME" ] || [ -z "$DOCKER_ARTIFACT_URL" ]; then
  echo "Failed to fetch the latest Docker image release for $REPO_OWNER/$REPO_NAME"
  exit 1
fi

echo "Latest release tag: $TAG_NAME"
echo "Downloading Docker image artifact from: $DOCKER_ARTIFACT_URL"

# Download the Docker image tar.gz file
curl -L -o "scloganalyzer-bot-${TAG_NAME}.tar.gz" "$DOCKER_ARTIFACT_URL"

if [ $? -ne 0 ]; then
  echo "Failed to download the Docker image artifact."
  exit 1
fi

echo "Docker image artifact downloaded successfully: scloganalyzer-bot-${TAG_NAME}.tar.gz"

# Load the Docker image into Docker
docker load < "scloganalyzer-bot-${TAG_NAME}.tar.gz"

if [ $? -eq 0 ]; then
  echo "Docker image loaded successfully."
else
  echo "Failed to load the Docker image."
  exit 1
fi