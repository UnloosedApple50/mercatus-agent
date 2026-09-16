# Mercatus Agent

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://docker.com)

> A Specialized Language Memory Agent for Sales & Trading.

Mercatus is a production-ready AI agent that combines persistent memory, local LLM reasoning, and a real-time web dashboard. Runs entirely on your machine — no cloud, no GPU required.

## Quick Start

### Option 1: One-Line Install (Recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/UnloosedApple50/mercatus-agent/main/install.sh | bash
```

### Option 2: Docker

```bash
git clone https://github.com/UnloosedApple50/mercatus-agent.git
cd mercatus-agent
docker-compose up -d
```

### Option 3: Manual Install

```bash
git clone https://github.com/UnloosedApple50/mercatus-agent.git
cd mercatus-agent
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .
python -m mercatus run
```

## Usage

1. Open **http://localhost:8585** in your browser
2. Start chatting with the agent
3. Browse memory, decisions, and knowledge
4. Export to Obsidian with one click
5. Configure integrations (Slack, Discord, Telegram)

## Troubleshooting

### Can't access http://localhost:8585?

1. **Check if server is running:**
   ```bash
   curl http://localhost:8585/api/v1/health
   ```

2. **Try your machine's IP:**
   ```bash
   # Get your IP
   ipconfig getifaddr en0  # macOS
   # Then access: http://YOUR_IP:8585
   ```

3. **Check firewall:**
   - macOS: System Preferences → Security & Privacy → Firewall
   - Windows: Allow Python through Windows Defender Firewall

4. **Try different browser** (Chrome, Firefox, Safari)

5. **Check terminal for errors** — the server will show error messages

### Common Errors

| Error | Solution |
|-------|----------|
| `Connection refused` | Server not running — start with `python -m mercatus run` |
| `Address already in use` | Port 8585 occupied — change with `MERCATUS_PORT=9000 python -m mercatus run` |
| `ModuleNotFoundError` | Run `pip install -e .` in the project directory |
| LLM errors | Ollama not running — install from [ollama.ai](https://ollama.ai) or use rule-based fallback |

## System Requirements

- Python 3.8 or higher
- 4GB RAM minimum (8GB recommended)
- 500MB disk space
- Optional: Ollama for local LLM (recommended)

## Documentation

- [Installation Guide](docs/INSTALLATION.md)
- [API Reference](docs/API.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Security](docs/SECURITY.md)

## License

MIT License - see [LICENSE](LICENSE) for details.
