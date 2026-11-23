FROM python:3.11-slim

# Install system dependencies: Chromium and fonts for headless image rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    fonts-dejavu-core \
    fonts-liberation \
    libgl1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Set default environment variables
ENV PORT=8080
ENV PYTHONUNBUFFERED=1
ENV CHROME_BIN=/usr/bin/chromium

EXPOSE 8080

CMD ["python", "app.py"]
