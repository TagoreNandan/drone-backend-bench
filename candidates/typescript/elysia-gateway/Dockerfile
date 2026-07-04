FROM oven/bun:1.2-slim AS builder
WORKDIR /app
COPY package.json bun.lock tsconfig.json ./
RUN bun install --frozen-lockfile
COPY src ./src

FROM oven/bun:1.2-slim AS runtime
WORKDIR /app
COPY --from=builder /app /app
EXPOSE 8000
EXPOSE 14550/udp
ENV HOST=0.0.0.0 \
    PORT=8000 \
    NODE_ENV=production
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD bun -e "fetch('http://127.0.0.1:8000/api/v1/health').then(r => process.exit(r.status === 200 ? 0 : 1)).catch(() => process.exit(1))"
CMD ["bun", "run", "src/index.ts"]
