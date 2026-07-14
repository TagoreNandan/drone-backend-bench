# litestar-bridge

This project was created with [Better Fullstack](https://github.com/Marve10s/Better-Fullstack), a high-performance Python stack.

## Features

- **Python** - Modern, readable programming language

## Prerequisites

- [Python](https://www.python.org/) 3.11 or higher
- [uv](https://docs.astral.sh/uv/) (Recommended package manager)

## Getting Started

First, copy the environment file:

```bash
cp .env.example .env
```

Then, install dependencies using uv:

```bash
uv sync --extra dev
```

Start the Litestar development server:

```bash
litestar --app src.app.main:app run --reload --port 3001
```

The API will be running at [http://localhost:3001](http://localhost:3001).

## Project Structure

```
litestar-bridge/
├── pyproject.toml        # Project configuration and dependencies
├── src/
│   └── app/
│       ├── __init__.py
│       └── main.py       # Application entry point
├── tests/
│   ├── __init__.py
│   └── test_main.py      # Test suite
├── .env.example          # Environment variables template
└── .gitignore
```

## Available Commands

- `uv run python -m app.main`: Run the application
- `uv run --extra dev pytest`: Run tests
