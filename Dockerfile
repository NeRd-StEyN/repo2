# --- Stage 1: Build Frontend ---
FROM node:20-slim AS build-frontend
WORKDIR /app/frontend
<<<<<<< HEAD
# Optimize by copying only package files first
=======
>>>>>>> origin/main
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Final Image ---
FROM python:3.11-slim
<<<<<<< HEAD
# Hugging Face Spaces runtime requirement: user 1000
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"
WORKDIR /app

# Install system dependencies
USER root
=======
WORKDIR /app

# Install system dependencies for PDF and ML
>>>>>>> origin/main
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*
<<<<<<< HEAD
USER user

# Install Python requirements
COPY --chown=user:user backend/requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn

# Copy backend code
COPY --chown=user:user backend/ ./

# Copy built frontend to backend's build folder
COPY --chown=user:user --from=build-frontend /app/frontend/dist ./build
=======

# Copy backend requirements and install
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn

# Copy backend code
COPY backend/ ./

# Copy built frontend from Stage 1 to backend's build folder
# Note: server.py expects the React app in a 'build' folder
COPY --from=build-frontend /app/frontend/dist ./build
>>>>>>> origin/main

# Set Environment Variables
ENV PORT=7860
ENV PYTHONUNBUFFERED=1

# Expose the port HF Spaces expects
EXPOSE 7860

# Run the server using gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "--timeout", "120", "--workers", "1", "server:server"]
