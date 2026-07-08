# echo-bridge

This project was created with [Better Fullstack](https://github.com/Marve10s/Better-Fullstack), a high-performance Go stack.

## Features

- **Go** - Fast, reliable, and efficient programming language
- **Echo** - High performance, minimalist Go web framework

## Prerequisites

- [Go](https://go.dev/) 1.22 or higher

## Getting Started

First, copy the environment file:

```bash
cp .env.example .env
```

Then, install dependencies and run the server:

```bash
go mod tidy
go run cmd/server/main.go
```

The server will be running at [http://localhost:8080](http://localhost:8080).

## Project Structure

```
echo-bridge/
├── go.mod                # Module definition
├── cmd/
│   └── server/           # HTTP server entry point
│       └── main.go
├── .env.example          # Environment variables template
└── .gitignore
```

## Available Commands

- `go build ./...`: Build all packages
- `go run cmd/server/main.go`: Run the server
- `go test ./...`: Run all tests
- `go fmt ./...`: Format code
- `go vet ./...`: Run static analysis
