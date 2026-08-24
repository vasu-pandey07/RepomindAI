# =============================================================
# Stage 1: Build the Next.js Frontend
# =============================================================
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

# Install dependencies
COPY frontend/package*.json ./
RUN npm ci

# Copy frontend source code and build standalone bundle
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production
RUN npm run build

# =============================================================
# Stage 2: Final Monolithic Runner (FastAPI + Next.js)
# =============================================================
FROM python:3.11-slim AS runner

# Install system dependencies: git (required by RepoMind for repo indexing), curl, and Node.js
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1. Install Backend Dependencies & Source
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Constrain native thread pools (ONNXRuntime / OpenMP / BLAS) to a single
# thread. On Render's free tier (0.1 shared CPU, 512MB RAM) the default of
# "use all cores" causes large per-thread memory arenas and CPU thrashing
# during embedding, which OOM-kills the backend mid-indexing. One thread is
# both lighter on RAM and, on a fractional CPU, no slower in practice.
ENV OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    ONNXRUNTIME_INTRA_OP_NUM_THREADS=1 \
    TOKENIZERS_PARALLELISM=false

# Pre-download FastEmbed model during image build (0 runtime download delay)
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5')"

COPY backend/ ./

# 2. Setup Frontend Standalone Build
WORKDIR /app/frontend
COPY --from=frontend-builder /app/frontend/.next/standalone ./
COPY --from=frontend-builder /app/frontend/.next/static ./.next/static
COPY --from=frontend-builder /app/frontend/public ./public

# 3. Setup Monolithic Entrypoint
WORKDIR /app
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Render injects PORT (default 10000 on Render, 3000 default local)
ENV PORT=3000
ENV BACKEND_INTERNAL_PORT=8000
ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production

EXPOSE 3000

CMD ["/app/entrypoint.sh"]
