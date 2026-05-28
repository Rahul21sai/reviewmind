# Use official Python slim base image for a lightweight container
FROM python:3.11-slim

# Set build-time and runtime environment flags
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000

# Set workspace directory
WORKDIR /app

# Install system dependencies (if any are ever needed for compiling)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file first for layer caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the Flask server port
EXPOSE 5000

# Run the Flask app module
CMD ["python", "-m", "reviewmind.app"]
