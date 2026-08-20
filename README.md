# AI Agent Builder Super-Skill

Comprehensive AI agent building skill merging **Perplexity Computer's skill creation and automation** with **Claude Code's agent orchestration, MCP servers, RAG, subagent coordination, and prompt optimization**, plus **Cursor IDE settings, project skills, rules, and MCP configuration**.

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
| Cursor IDE Settings | `settings.json` workflow, `.cursor/` layout, CLI vs IDE attribution |

## Cursor project extras

This repo also ships Cursor-native files so Agent can apply the skill in-product:

| Path | Purpose |
|------|---------|
| `.cursor/skills/update-cursor-settings/SKILL.md` | Slash workflow for editing user or workspace `settings.json` |
| `.cursor/rules/skill-authoring.mdc` | Conventions for editing this super-skill |
| `.vscode/settings.json` | Shared markdown/editor defaults for this repo |
| `AGENTS.md` | Short always-on instructions |

Type `/update-cursor-settings` in Cursor Agent chat to invoke the settings workflow.

## Sources Merged

**Perplexity Computer:** create-skill, webserver, website-building

**Claude Code:** Agent Orchestrator, MCP Server Builder, RAG System Builder, Subagent-Driven Dev, Dispatching Parallel Agents, Executing Plans, Prompt Engineer/Optimizer, ML Engineer, Using Superpowers

**Cursor:** update-cursor-settings, project skills, rules, MCP config, CLI `cli-config.json`

## Usage
Upload the root `SKILL.md` file to your Perplexity Computer user settings or Claude Code skills directory.

In Cursor, clone this repository (or copy `.cursor/skills/` into your project or `~/.cursor/skills/`). Agent discovers the nested skills automatically.

## License
MIT
