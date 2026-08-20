# AI Agent Builder Super-Skill

Comprehensive AI agent building skill merging **Perplexity Computer's skill creation and automation** with **Claude Code's agent orchestration, MCP servers, RAG, subagent coordination, and prompt optimization**.

This repo also ships **Grok Bot**, a production-quality local chat console for xAI's Grok API.

## Grok Bot

Polished web chat + FastAPI backend. Streaming replies, session history, and a Grok personality.

```bash
cd grok-bot
pip install -r requirements-dev.txt
cp .env.example .env   # set XAI_API_KEY
python -m app
```

Full setup, API, and tests: [grok-bot/README.md](grok-bot/README.md)

## What's Inside the skill

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

## License

MIT
