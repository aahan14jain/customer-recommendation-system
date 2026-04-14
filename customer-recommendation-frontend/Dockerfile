# Next.js app — Node image, npm ci from lockfile, production `next start` on 0.0.0.0:3001
# (Port 3001 avoids clashes with Grafana / other apps on 3000; map host with -p 3001:3001.)
# NEXT_PUBLIC_API_URL is read at build time (inlined for client bundles). Default targets Dockerized
# backend on host port 8001 (override with: docker build --build-arg NEXT_PUBLIC_API_URL=...).
FROM node:22-bookworm-slim AS deps
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-bookworm-slim AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG NEXT_PUBLIC_API_URL=http://host.docker.internal:8001
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

FROM node:22-bookworm-slim AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.ts ./next.config.ts

EXPOSE 3001

CMD ["npx", "next", "start", "--hostname", "0.0.0.0", "--port", "3001"]
