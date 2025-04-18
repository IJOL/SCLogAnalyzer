# Use an official Python image as the base
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Copy the project files into the container
COPY src .

# Install Python dependencies
RUN pip install --no-cache-dir -r bot/requirements.txt

# Set the default command to run bot.py
CMD ["python", "bot/bot.py"]
