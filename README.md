# APolo FastAPI backend

## Setup

```bash
cd mcp-server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `OPENAI_API_KEY` in `.env`, then start the API:

```bash
uvicorn api:app --reload --host 127.0.0.1 --port 8000
```

The existing MCP server remains available with:

```bash
python3 server.py
```

Health check: `http://127.0.0.1:8000/api/health`
