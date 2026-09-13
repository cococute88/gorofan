# syntax=docker/dockerfile:1
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
ARG NEXT_PUBLIC_API_BASE=http://localhost:8000/api/v1
ARG BACKEND_INTERNAL_URL=http://localhost:8000
ARG NEXT_BUILD_CPUS=1
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE \
    BACKEND_INTERNAL_URL=$BACKEND_INTERNAL_URL \
    NEXT_BUILD_CPUS=$NEXT_BUILD_CPUS \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
