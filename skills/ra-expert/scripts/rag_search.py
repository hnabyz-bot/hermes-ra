#!/usr/bin/env python3
"""
RA Expert RAG Search — Qdrant vector search helper for Hermes RA skill.

CLI: python rag_search.py "<query>" [--top N] [--collection NAME]
Output: JSON {results: [{text, source_file, score, metadata}]}

Environment:
  QDRANT_URL   - Qdrant endpoint (default: http://localhost:6333)
  OLLAMA_URL   - Ollama endpoint for embeddings (default: http://192.168.100.1:11434)
  EMBED_MODEL  - Embedding model (default: qwen3-embedding:latest)
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error


QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://192.168.100.1:11434")
# qwen3-embedding uses /api/embed with "input" key and returns {"embeddings": [[...]]}
EMBED_MODEL = os.environ.get("EMBED_MODEL", "qwen3-embedding:latest")
DEFAULT_COLLECTION = "nas_ra_docs"


def embed_query(text: str) -> list[float]:
    payload = json.dumps({"model": EMBED_MODEL, "input": text}).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/embed",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    return data["embeddings"][0]


def search_qdrant(vector: list[float], collection: str, top: int) -> list[dict]:
    payload = json.dumps({
        "vector": vector,
        "limit": top,
        "with_payload": True,
        "with_vector": False,
    }).encode()
    req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{collection}/points/search",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data.get("result", [])


def format_results(raw: list[dict]) -> list[dict]:
    results = []
    for item in raw:
        payload = item.get("payload", {})
        results.append({
            "text": payload.get("text", payload.get("content", "")),
            "source_file": payload.get("source", payload.get("file_path", payload.get("filename", "unknown"))),
            "score": round(item.get("score", 0.0), 4),
            "metadata": {k: v for k, v in payload.items() if k not in ("text", "content", "source", "file_path")},
        })
    return results


def main():
    parser = argparse.ArgumentParser(description="Search NAS Qdrant for RA documents")
    parser.add_argument("query", help="Search query text")
    parser.add_argument("--top", type=int, default=5, help="Number of results (default: 5)")
    parser.add_argument("--collection", default=DEFAULT_COLLECTION, help=f"Qdrant collection (default: {DEFAULT_COLLECTION})")
    args = parser.parse_args()

    try:
        vector = embed_query(args.query)
    except Exception as e:
        print(json.dumps({"error": f"Embedding failed: {e}", "results": []}))
        sys.exit(1)

    try:
        raw = search_qdrant(vector, args.collection, args.top)
    except urllib.error.URLError as e:
        print(json.dumps({"error": f"Qdrant unreachable: {e}", "results": []}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"Search failed: {e}", "results": []}))
        sys.exit(1)

    output = {
        "query": args.query,
        "collection": args.collection,
        "results": format_results(raw),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
