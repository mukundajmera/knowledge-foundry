# ═══════════════════════════════════════════════════════════
# Knowledge Foundry — Frontend Dockerfile
# Multi-stage: build → nginx serve
# ═══════════════════════════════════════════════════════════

# ── Stage 1: Build ──
FROM node:20-alpine AS builder

WORKDIR /build

COPY package.json package-lock.json ./
RUN npm ci --production=false

COPY . .

ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ── Stage 2: Runtime ──
FROM node:20-alpine AS runtime

LABEL maintainer="Knowledge Foundry Team"
LABEL description="Knowledge Foundry Frontend"

WORKDIR /app

RUN addgroup -S kfgroup && adduser -S kfuser -G kfgroup

# Copy only the production build
COPY --from=builder /build/.next/standalone ./
COPY --from=builder /build/.next/static ./.next/static
COPY --from=builder /build/public ./public

ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0
ENV PORT=3000

USER kfuser

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget --spider -q http://localhost:3000 || exit 1

CMD ["node", "server.js"]
