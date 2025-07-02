FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install the dependencies
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

# Install necessary packages for downloading and extracting
RUN apt-get update && apt-get install -y \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Download kubectl binary
# Replace 'v1.27.0' with the desired kubectl version
ARG KUBECTL_VERSION="v1.27.0"
RUN curl -LO "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl"

# Download the checksum file for verification (optional but recommended)
RUN curl -LO "https://dl.k8s.io/${KUBECTL_VERSION}/bin/linux/amd64/kubectl.sha256"

# Verify the binary (optional but recommended)
RUN echo "$(cat kubectl.sha256) kubectl" | sha256sum --check

# Make the kubectl binary executable
RUN chmod +x kubectl

# Move kubectl to a directory in the PATH
RUN mv kubectl /usr/local/bin/kubectl

# Verify kubectl installation
RUN kubectl version --client

# Copy your application code (if applicable)
# Copy the requirements file into the container
COPY ./requirements.txt ./requirements.txt
COPY ./script /app/script

# Install Python dependencies (if applicable)
RUN pip install -r requirements.txt

# Define the command to run when the container starts
CMD ["python", "/app/trigger_orchestration_dag.py"]