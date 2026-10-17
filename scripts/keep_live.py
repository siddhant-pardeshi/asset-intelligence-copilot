"""Keeps the copilot live: supervises the API server and the Cloudflare
quick tunnel, restarts either if it dies, and prints the public URL.

    python scripts/keep_live.py

Run it from anywhere and leave the window open. When cloudflared rotates
the URL (every restart of the tunnel), the new one is printed loudly and
written to .live_url next to this script. Stop with Ctrl+C.
"""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
CLOUDFLARED = ROOT.parent / "cloudflared.exe"
URL_FILE = ROOT / ".live_url"

PORT = int(os.environ.get("COPILOT_PORT", "8000"))
API = f"http://127.0.0.1:{PORT}"

procs = {"api": None, "tunnel": None}
url = {"current": None}


def log(msg):
    print(f"[keep-live {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def alive(proc):
    return proc is not None and proc.poll() is None


def api_healthy():
    try:
        import urllib.request
        with urllib.request.urlopen(f"{API}/api/health", timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def start_api():
    log("starting API server on port %d" % PORT)
    procs["api"] = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0",
         "--port", str(PORT), "--log-level", "warning"],
        cwd=BACKEND)


def start_tunnel():
    exe = str(CLOUDFLARED if CLOUDFLARED.exists() else "cloudflared")
    log("starting cloudflared tunnel")
    procs["tunnel"] = subprocess.Popen(
        [exe, "tunnel", "--url", API, "--no-autoupdate"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace")


def read_tunnel_url():
    proc = procs["tunnel"]
    if not alive(proc):
        return None
    # cloudflared prints the URL on stderr(=stdout here); read what's buffered
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
        if m:
            return m.group(0)
    return None


def publish(new_url):
    url["current"] = new_url
    URL_FILE.write_text(new_url + "\n", encoding="utf-8")
    log("=" * 62)
    log("PUBLIC LINK:  " + new_url)
    log("saved to " + str(URL_FILE))
    log("=" * 62)


def main():
    log("supervising copilot at %s (Ctrl+C to stop)" % API)
    if URL_FILE.exists():
        url["current"] = URL_FILE.read_text().strip()
        log("last known public link: " + url["current"])
    start_api()
    start_tunnel()

    deadline = time.time() + 20
    while time.time() < deadline:
        found = read_tunnel_url()
        if found and found != url["current"]:
            publish(found)
            break
        time.sleep(0.5)

    while True:
        time.sleep(5)
        if not alive(procs["api"]) or not api_healthy():
            log("API down — restarting")
            start_api()
        if not alive(procs["tunnel"]):
            log("tunnel down — restarting (the URL WILL CHANGE)")
            start_tunnel()
            deadline = time.time() + 20
            while time.time() < deadline:
                found = read_tunnel_url()
                if found and found != url["current"]:
                    publish(found)
                    break
                time.sleep(0.5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("stopped by user — killing children")
        for p in procs.values():
            if alive(p):
                p.terminate()
