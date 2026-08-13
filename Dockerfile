# Stage 1: Build the React frontend
FROM node:18-alpine AS frontend-builder
WORKDIR /frontend

# Copy package files and install dependencies
COPY frontend/package*.json ./
RUN npm ci

# Copy frontend source and build static assets
COPY frontend/ ./
RUN npm run build

# Stage 2: Serve the FastAPI backend and static frontend
FROM python:3.11-slim
WORKDIR /app

# Install backend dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend app
COPY backend/ ./backend

# Copy built frontend assets from Stage 1
COPY --from=frontend-builder /frontend/dist ./frontend/dist

# Expose port and start uvicorn
WORKDIR /app/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
