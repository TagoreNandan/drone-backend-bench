FROM node:20-slim AS builder

WORKDIR /app

RUN npm install -g pnpm@9

COPY pnpm-lock.yaml package.json pnpm-workspace.yaml tsconfig.json turbo.json ./
COPY packages/env ./packages/env
COPY packages/config ./packages/config
COPY apps/server ./apps/server

# Install dependencies
RUN pnpm install --frozen-lockfile

# Compile TypeScript
RUN pnpm exec tsc -b

FROM node:20-slim AS runtime

ENV HOST=0.0.0.0 \
    PORT=8000 \
    NODE_ENV=production

WORKDIR /app

RUN npm install -g pnpm@9

COPY --from=builder /app /app

EXPOSE 8000
EXPOSE 14550/udp

USER node

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD node -e "const http = require('http'); const port = process.env.PORT || '8000'; const req = http.request({ host: '127.0.0.1', port, path: '/api/v1/health', timeout: 3000 }, (res) => { process.exit(res.statusCode === 200 ? 0 : 1); }); req.on('error', () => process.exit(1)); req.end();"

CMD ["pnpm", "--filter", "server", "exec", "tsx", "src/index.ts"]
