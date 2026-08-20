"""End-to-end tests for the runnable examples extracted from SKILL.md.

Each test exercises a documented pattern with no external API keys required.
"""

import json
import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(REPO_ROOT, "examples")


# --- Section 4.2: RAG chunking -----------------------------------------------
def test_chunkers_produce_chunks_and_preserve_words():
    from rag_chunking import (
        Document,
        FixedSizeChunker,
        RecursiveChunker,
        SentenceChunker,
    )

    doc = Document(content=" ".join(f"word{i}" for i in range(120)))

    for chunker in (
        FixedSizeChunker(chunk_size=25, overlap=5),
        SentenceChunker(sentences_per_chunk=3, overlap_sentences=1),
        RecursiveChunker(max_chunk_size=20, min_chunk_size=3),
    ):
        chunks = chunker.chunk(doc)
        assert chunks, f"{chunker.__class__.__name__} produced no chunks"
        assert all(c.doc_id == doc.doc_id for c in chunks)
        assert all(c.content.strip() for c in chunks)

    # Fixed-size chunker with overlap should cover every original word.
    fixed = FixedSizeChunker(chunk_size=25, overlap=5).chunk(doc)
    covered = {w for c in fixed for w in c.content.split()}
    assert covered == set(doc.content.split())


# --- Section 2.2: ReAct agent loop -------------------------------------------
def test_react_agent_completes_a_tool_using_task():
    from react_agent import MockLLM, TOOLS, react_agent

    answer = react_agent("What is 12 plus 30?", TOOLS, MockLLM(12, 30, "add"))
    assert "42" in answer

    answer_mul = react_agent("product", TOOLS, MockLLM(6, 7, "mul"))
    assert "42" in answer_mul


def test_react_agent_handles_unknown_tool_gracefully():
    from react_agent import react_agent

    class BadLLM:
        def complete(self, messages):
            return 'Thought: go\nAction: nonexistent\nAction Input: {}'

    # The loop should not crash; the unknown tool yields an error observation
    # and the run terminates at max iterations.
    result = react_agent("q", {}, BadLLM(), max_iterations=2)
    assert "max iterations" in result


# --- Section 8.3: input drift detection --------------------------------------
def test_drift_detection_flags_shifted_distribution():
    from drift_detection import detect_input_drift

    reference = ["short q"] * 30
    drifted = ["a much longer query with clearly more tokens than the reference"] * 30
    result = detect_input_drift(reference, drifted)

    assert result["drift_detected"]
    assert 0.0 <= result["ks_statistic"] <= 1.0
    assert result["cur_mean_tokens"] > result["ref_mean_tokens"]


def test_drift_detection_no_false_positive_on_same_distribution():
    from drift_detection import detect_input_drift

    same = ["one two three four"] * 30
    result = detect_input_drift(same, same)
    assert not result["drift_detected"]


# --- Section 8.2: FastAPI agent server ---------------------------------------
@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    import agent_server

    return TestClient(agent_server.app)


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "version": "1.0.0"}


def test_agent_run_happy_path(client):
    resp = client.post("/agent/run", json={"query": "hello world", "max_steps": 3})
    assert resp.status_code == 200
    body = resp.json()
    assert "hello world" in body["result"]
    assert body["steps_used"] == 3
    assert body["session_id"]
    assert body["latency_ms"] >= 0.0


def test_agent_run_rejects_empty_query(client):
    resp = client.post("/agent/run", json={"query": "   "})
    assert resp.status_code == 422


def test_agent_async_run_and_status(client):
    resp = client.post("/agent/run-async", json={"query": "later"})
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    status = client.get(f"/agent/status/{job_id}")
    assert status.status_code == 200
    assert status.json()["status"] == "completed"


# --- Section 10.1: SQLite agent-memory CGI backend ---------------------------
def _cgi(method: str, path: str, tmp_db: str, body: str = "", query: str = ""):
    """Invoke the CGI backend the way a web server would and parse the response."""
    env = {
        **os.environ,
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "AGENT_MEMORY_DB": tmp_db,
    }
    proc = subprocess.run(
        [sys.executable, os.path.join(EXAMPLES, "agent_memory_cgi.py")],
        input=body,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    header, _, payload = proc.stdout.partition("\n\n")
    status = 200
    for line in header.splitlines():
        if line.lower().startswith("status:"):
            status = int(line.split(":", 1)[1].strip())
    return status, json.loads(payload)


def test_agent_memory_cgi_full_flow(tmp_path):
    db = str(tmp_path / "mem.db")

    status, data = _cgi("POST", "/sessions", db, body=json.dumps({"session_id": "s1"}))
    assert status == 201 and data["session_id"] == "s1"

    status, data = _cgi(
        "POST", "/messages", db,
        body=json.dumps({"session_id": "s1", "role": "user", "content": "hi"}),
    )
    assert status == 201 and isinstance(data["id"], int)

    status, msgs = _cgi("GET", "/messages", db, query="session_id=s1")
    assert status == 200
    assert len(msgs) == 1 and msgs[0]["content"] == "hi"

    status, data = _cgi(
        "PUT", "/facts", db,
        body=json.dumps({"session_id": "s1", "key": "color", "value": "blue"}),
    )
    assert status == 200 and data["status"] == "ok"

    status, facts = _cgi("GET", "/facts", db, query="session_id=s1")
    assert status == 200
    assert facts["color"]["value"] == "blue"
