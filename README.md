# AI Agent Builder Super-Skill

Comprehensive AI agent building skill merging **Perplexity Computer's skill creation and automation** with **Claude Code's agent orchestration, MCP servers, RAG, subagent coordination, and prompt optimization**.

## What's Inside

| Section | Description |
|---------|-------------|
| Agent Architecture | ReAct, Plan-Execute, Reflexion patterns with Python implementations |
| MCP Server Dev | TypeScript + Python FastMCP templates, tool design checklist |
| RAG Construction | Chunkers, vector stores, rerankers, HyDE, evaluation metrics |
| Subagent Coordination | Implementer/Reviewer/Quality prompt templates |
| Execution Planning | Parallel dispatch, conflict detection, checkpoints |
| Prompt Engineering | CoT, structured output, meta-prompting, few-shot |
| ML Integration | Provider abstraction, FastAPI agent server, drift detection |
| Skill Creation | SKILL.md format, validation, packaging |
| Backend Infrastructure | SQLite memory, webhook receivers, pub/sub |
| Deployment & Monitoring | Production checklist, Prometheus metrics, scaling |

## Sources Merged

**Perplexity Computer:** create-skill, webserver, website-building

**Claude Code:** Agent Orchestrator, MCP Server Builder, RAG System Builder, Subagent-Driven Dev, Dispatching Parallel Agents, Executing Plans, Prompt Engineer/Optimizer, ML Engineer, Using Superpowers

## Usage
Upload the `SKILL.md` file to your Perplexity Computer user settings or Claude Code skills directory.

## Development

Several patterns documented in `SKILL.md` are extracted into runnable form under
`examples/` so they can be executed and tested directly.

Setup (Python 3.12+):

```bash
bash .cursor/install.sh   # pip install -r requirements.txt + byte-compile examples
```

Run the standalone examples:

```bash
python3 examples/rag_chunking.py      # §4.2 RAG chunking strategies
python3 examples/react_agent.py       # §2.2 ReAct loop (offline mock LLM)
python3 examples/drift_detection.py   # §8.3 input-drift detection (KS test)
```

Run the agent API server (§8.2) and call it:

```bash
python3 -m uvicorn agent_server:app --app-dir examples --host 0.0.0.0 --port 8080
curl -s localhost:8080/health
curl -s -X POST localhost:8080/agent/run \
  -H 'content-type: application/json' -d '{"query": "hello", "max_steps": 3}'
```

Run the test suite:

```bash
python3 -m pytest -q
```

| Path | Skill section |
|------|---------------|
| `examples/rag_chunking.py` | §4.2 RAG System Construction |
| `examples/react_agent.py` | §2.2 Agent Architecture (ReAct) |
| `examples/drift_detection.py` | §8.3 ML Integration (monitoring) |
| `examples/agent_server.py` | §8.2 Model Deployment (FastAPI) |
| `examples/agent_memory_cgi.py` | §10.1 Backend Infrastructure (SQLite) |

## License
MIT
