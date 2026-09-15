# Installation Guide

## Prerequisites

- **Python 3.11+** — [Download](https://www.python.org/downloads/)
- **Ollama** (optional) — [Install](https://ollama.ai)
- **8GB RAM** minimum
- **macOS/Linux** (Windows via WSL2)

## Quick Install

```bash
# 1. Clone the repository
git clone https://github.com/UnloosedApple50/mercatus-agent.git
cd mercatus-agent

# 2. Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# 3. Install Mercatus
pip install -e .

# 4. Configure environment
cp .env.example .env
# Edit .env with your settings

# 5. Initialize database
python -m mercatus db init

# 6. Start the server
python -m mercatus run
```

## Development Install

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=mercatus --cov-report=html
```

## Ollama Setup (Optional)

Ollama provides LLM capabilities. Without it, Mercatus uses rule-based fallback.

```bash
# Install Ollama (macOS)
brew install ollama

# Start Ollama service
ollama serve

# Pull a model (llama3.2 recommended for 8GB RAM)
ollama pull llama3.2

# Verify
ollama list
```

## Verifying Installation

```bash
# Check health
curl http://localhost:8585/api/v1/health

# Send test message
curl -X POST http://localhost:8585/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello Mercatus!", "module": "general"}'
```

## Docker (Optional)

```bash
docker build -t mercatus-agent .
docker run -p 8585:8585 -v mercatus-data:/app/data mercatus-agent
```

## Troubleshooting

### Port Already in Use
```bash
# Change port in .env
MERCATUS_PORT=8586
```

### Database Locked
```bash
# Remove stale lock files
rm -f data/mercatus.db-wal data/mercatus.db-shm
```

### Ollama Connection Failed
```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Or run without LLM (rule-based mode)
# Just don't start Ollama — Mercatus auto-detects
```

### Memory Issues on 8GB RAM
```bash
# Use a lighter model
MERCATUS_LLM_MODEL=phi3:mini

# Or disable LLM entirely (rule-based only)
# Don't start Ollama
```
