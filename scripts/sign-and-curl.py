#!/usr/bin/env python3
"""Sign and curl helper for /internal/* endpoints.

Usage:
  ./scripts/sign-and-curl.py <METHOD> <PATH> [body_json] [--host HOST:PORT]

Examples:
  # State service (default 8007)
  ./scripts/sign-and-curl.py GET /internal/state/<uuid>/truth/current_state

  # Pipeline orchestrator
  ./scripts/sign-and-curl.py GET /internal/orchestrator/agents --host :8002
  ./scripts/sign-and-curl.py POST /internal/pipeline/write/next '{"book_id":"...","chapter_number":1}' --host :8002
"""
import argparse
import hashlib
import hmac
import os
import subprocess
import sys
from pathlib import Path

# Read secret from .env
env_path = Path(__file__).resolve().parent.parent / ".env"
SECRET = None
for line in env_path.read_text().splitlines():
    if line.startswith("SERVICE_SECRET="):
        SECRET = line.split("=", 1)[1].strip()
        break
if not SECRET:
    sys.exit("SERVICE_SECRET not found in .env")

parser = argparse.ArgumentParser()
parser.add_argument("method", help="HTTP method")
parser.add_argument("path", help="URL path (e.g. /internal/...)")
parser.add_argument("body", nargs="?", default="", help="JSON body")
parser.add_argument("--host", default="127.0.0.1:8007", help="host:port (default 8007 state-service)")
parser.add_argument("--service", default="gateway", help="X-Service-Id (default gateway)")
args = parser.parse_args()

host = args.host.lstrip(":")
if not host.startswith("127.0.0.1") and not host.startswith("localhost"):
    full_host = host
else:
    full_host = host or "127.0.0.1:8007"

method = args.method.upper()
path = args.path
body = args.body.encode("utf-8") if args.body else b""

body_hash = hashlib.sha256(body).hexdigest()
msg = f"{method}:{path}:{body_hash}"
sig = hmac.new(SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()

cmd = [
    "curl", "--noproxy", "*", "-s", "-X", method,
    "-H", f"X-Service-Id: {args.service}",
    "-H", f"X-Service-Signature: {sig}",
    "-w", "\nHTTP_CODE=%{http_code}\n",
]
if body:
    cmd += ["-H", "Content-Type: application/json", "-d", args.body]
cmd.append(f"http://{full_host}{path}")

r = subprocess.run(cmd, capture_output=True, text=True)
print(r.stdout, end="")
if r.stderr:
    print("STDERR:", r.stderr, file=sys.stderr)
sys.exit(r.returncode)
