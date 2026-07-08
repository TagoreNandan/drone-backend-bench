FROM node:20-slim

WORKDIR /app

COPY package.json tsconfig.json ./
RUN npm install

COPY src ./src

ENV HOST=0.0.0.0 \
    PORT=8000 \
    NODE_ENV=production

EXPOSE 8000
EXPOSE 14550/udp

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD node -e "const http = require('http'); const port = process.env.PORT || '8000'; const req = http.request({ host: '127.0.0.1', port, path: '/api/v1/health', timeout: 3000 }, (res) => { process.exit(res.statusCode === 200 ? 0 : 1); }); req.on('error', () => process.exit(1)); req.end();"

CMD ["npx", "tsx", "src/index.ts"]
