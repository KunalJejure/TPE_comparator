# Use official Python 3.11 slim image for a small footprint
FROM python:3.11-slim

# Prevent Python from writing pyc files to disc
ENV PYTHONDONTWRITEBYTECODE=1
# Prevent Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1

# Install system dependencies required for OpenCV, PyMuPDF, OCR, and LibreOffice for DOCX conversion
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libreoffice \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create necessary directories
RUN mkdir -p /app/backend/uploads /app/backend/reports /app/history

# Copy application code
COPY backend /app/backend
COPY frontend /app/frontend
COPY main.py /app/main.py

# Expose port
EXPOSE 8080

# Command to run the application
CMD ["python", "main.py"]
