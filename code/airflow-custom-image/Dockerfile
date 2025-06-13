FROM apache/airflow:2.10.5-python3.10

USER root

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    build-essential \
    libffi-dev \
    libssl-dev \
    python3-dev \
    libpq-dev \
    git \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

USER airflow

COPY requirements.txt .

# Install required Python libraries
RUN pip install --no-cache-dir -r requirements.txt
