"""
Quick manual test client for the running API.

Usage:
    # terminal 1
    uvicorn app:app --reload --port 8000

    # terminal 2
    python test_client.py /path/to/report1.pdf /path/to/report2.pdf
"""
import sys
import json
import requests  # pip install requests

BASE_URL = "http://127.0.0.1:8000"


def test_single(path: str):
    with open(path, "rb") as f:
        resp = requests.post(f"{BASE_URL}/extract", files={"file": (path, f, "application/pdf")})
    print(f"\n=== /extract  {path}  [{resp.status_code}] ===")
    print(json.dumps(resp.json(), indent=2)[:2000])


def test_batch(paths: list[str]):
    files = [("files", (p, open(p, "rb"), "application/pdf")) for p in paths]
    resp = requests.post(f"{BASE_URL}/extract/batch", files=files)
    print(f"\n=== /extract/batch [{resp.status_code}] ===")
    data = resp.json()
    print("files processed:", [r["filename"] for r in data.get("results", [])])
    print("row counts:", [r["row_count"] for r in data.get("results", [])])
    if data.get("errors"):
        print("errors:", data["errors"])


if __name__ == "__main__":
    paths = sys.argv[1:]
    if not paths:
        print("Usage: python test_client.py file1.pdf [file2.pdf ...]")
        sys.exit(1)

    print("Health check:", requests.get(f"{BASE_URL}/health").json())
    for p in paths:
        test_single(p)
    if len(paths) > 1:
        test_batch(paths)
