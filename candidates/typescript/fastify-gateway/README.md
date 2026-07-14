# fastify-gateway

This project was created with [Better Fullstack](https://github.com/Marve10s/Better-Fullstack), a modern TypeScript stack that combines Fastify, and more.

## Features

- **TypeScript** - For type safety and improved developer experience
- **Fastify** - Fast, low-overhead web framework
- **Node.js** - Runtime environment
- **Turborepo** - Optimized monorepo build system

## Getting Started

First, install the dependencies:

```bash
pnpm install
```

Then, run the development server:

```bash
pnpm run dev
```

The API is running at [http://localhost:3000](http://localhost:3000).

## Project Structure

```
fastify-gateway/
├── apps/
│   └── server/      # Backend API (Fastify)
├── packages/
│   ├── api/         # API layer / business logic
```

## Available Scripts

- `pnpm run dev`: Start all applications in development mode
- `pnpm run build`: Build all applications
- `pnpm run dev:server`: Start only the server
- `pnpm run check-types`: Check TypeScript types across all apps
