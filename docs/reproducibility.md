# reproducibility.md

To reproduce the benchmark results on any system, ensure that the Docker Desktop daemon is running and execute the following sequential commands in your terminal:

### **1. Check System Capabilities**
Confirm your host meets minimum hardware requirements (M1/x86 CPU, 8GB RAM).
```bash
docker --version
node --version
python3 --version
```

### **2. Build Docker Images**
Ensure you build the Docker images for all candidate frameworks:
```bash
docker build -t fastapi-bridge:latest candidates/python/fastapi-bridge/
docker build -t litestar-bridge:latest candidates/python/litestar-bridge/
docker build -t sanic-bridge:latest candidates/python/sanic-bridge/
docker build -t aiohttp-bridge:latest candidates/python/aiohttp-bridge/
docker build -t starlette-bridge:latest candidates/python/starlette-bridge/
docker build -t nethttp-bridge:latest candidates/go/nethttp-bridge/
docker build -t echo-bridge:latest candidates/go/echo-bridge/
docker build -t fiber-bridge:latest candidates/go/fiber-bridge/
docker build -t chi-bridge:latest candidates/go/chi-bridge/
docker build -t gin-bridge:latest candidates/go/gin-bridge/
docker build -t hono-gateway:latest candidates/typescript/hono-gateway/
docker build -t uwebsockets-bridge:latest candidates/typescript/uwebsockets-bridge/
docker build -t express-gateway:latest candidates/typescript/express-gateway/
```

### **3. Run Campaign Suite**
Run the raw benchmark runner python script:
```bash
python3 scratch/run_benchmarks.py
```
This script will sequentially test each candidate and write metrics files to:
`results/<framework>/run01.json` through `results/<framework>/run10.json`.
