#!/usr/bin/env python3
"""Neon Sales City – liten spelserver för samma nätverk.

Starta:  python3 server.py
Storskärm:  http://localhost:8765
Spelare:    http://<datorns-ip>:8765/play
Allt ligger i minnet och försvinner när servern stängs.
"""
import hmac
import json
import os
import re
import secrets
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "8765"))
COLORS = ["#ff3df2", "#22e6ff", "#ffd23d", "#7dff5a", "#ff7a3d", "#a78bff",
          "#ff5c8a", "#3dffd0", "#ffe14d", "#6fa8ff", "#ff9de2", "#b6ff3d"]
MAX_PLAYERS = 80
MAX_EVENTS = 20000
LOCAL = ("127.0.0.1", "::1", "::ffff:127.0.0.1")
# On a web host nobody is "local", so resetting the game needs this code (set it as an environment variable).
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")

lock = threading.Lock()
players = {}    # id -> player dict
by_name = {}    # lowercased name -> id
events = []     # append-only list the big screen reads from
state = {"epoch": int(time.time())}


def clean(value, limit):
    text = re.sub(r"[<>&\"'`\\\x00-\x1f]", "", str(value or "")).strip()
    return text[:limit]


def to_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def lan_ip():
    # Prefer the wifi/ethernet address on macOS; a VPN tunnel would otherwise win and phones cannot reach it.
    for iface in ("en0", "en1", "en2", "en3", "en4", "en5"):
        try:
            out = subprocess.run(["ipconfig", "getifaddr", iface], capture_output=True, text=True, timeout=2)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            break
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no packet is sent, only picks the outgoing interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def public(p):
    return {k: p[k] for k in ("id", "name", "color", "sum", "deals", "budget")}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send_json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_page(self, name):
        try:
            with open(os.path.join(ROOT, name), "rb") as f:
                body = f.read()
        except OSError:
            return self.send_json({"error": "Sidan saknas"}, 404)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        path = url.path
        if path in ("/", "/index.html"):
            return self.send_page("neon-sales-city-multi.html")
        if path in ("/play", "/play/"):
            return self.send_page("play.html")
        if path == "/api/info":
            with lock:
                return self.send_json({"ip": lan_ip(), "port": PORT, "count": len(events),
                                       "epoch": state["epoch"],
                                       "players": [public(p) for p in players.values()]})
        if path == "/api/events":
            since = to_int(parse_qs(url.query).get("since", ["0"])[0]) or 0
            with lock:
                return self.send_json({"events": events[max(0, since):], "next": len(events),
                                       "epoch": state["epoch"]})
        if path == "/api/state":
            with lock:
                ranked = sorted(players.values(), key=lambda p: -p["sum"])
                return self.send_json({"epoch": state["epoch"], "players": [public(p) for p in ranked]})
        return self.send_json({"error": "Finns inte"}, 404)

    def do_POST(self):
        length = to_int(self.headers.get("Content-Length")) or 0
        if length > 4096:
            return self.send_json({"error": "För mycket data"}, 413)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise ValueError
        except ValueError:
            return self.send_json({"error": "Ogiltig data"}, 400)
        path = urlparse(self.path).path

        if path == "/api/reset":
            direct_local = self.client_address[0] in LOCAL and not self.headers.get("X-Forwarded-For")
            has_key = bool(ADMIN_KEY) and hmac.compare_digest(str(body.get("key") or ""), ADMIN_KEY)
            if not (direct_local or has_key):
                return self.send_json({"error": "Fel adminkod"}, 403)
            with lock:
                players.clear()
                by_name.clear()
                events.clear()
                state["epoch"] = int(time.time() * 1000)
            return self.send_json({"ok": True})

        if path == "/api/join":
            name = clean(body.get("name"), 16)
            if len(name) < 2:
                return self.send_json({"error": "Skriv ett namn med minst två tecken"}, 400)
            with lock:
                pid = by_name.get(name.lower())
                if pid is None:
                    if len(players) >= MAX_PLAYERS:
                        return self.send_json({"error": "Spelet är fullt"}, 409)
                    pid = secrets.token_hex(4)
                    p = {"id": pid, "name": name, "color": COLORS[len(players) % len(COLORS)],
                         "sum": 0, "deals": 0, "budget": 0, "last": 0.0}
                    players[pid] = p
                    by_name[name.lower()] = pid
                    events.append({"type": "join", "id": pid, "name": name, "color": p["color"]})
                out = public(players[pid])
                out["epoch"] = state["epoch"]
                return self.send_json(out)

        with lock:
            p = players.get(str(body.get("id")))
            if p is None:
                return self.send_json({"error": "Gå med i spelet igen"}, 401)
            value = to_int(body.get("value"))

            if path == "/api/budget":
                if value is None or not 10_000 <= value <= 1_000_000_000:
                    return self.send_json({"error": "Budget ska vara mellan 10 000 och 1 000 000 000 kr"}, 400)
                p["budget"] = value
                events.append({"type": "budget", "id": p["id"], "value": value})
                return self.send_json(public(p))

            if path == "/api/deal":
                if value is None or not 1_000 <= value <= 50_000_000:
                    return self.send_json({"error": "Belopp ska vara mellan 1 000 och 50 000 000 kr"}, 400)
                if len(events) >= MAX_EVENTS:
                    return self.send_json({"error": "Spelet är fullt. Be värden nollställa det."}, 429)
                now = time.time()
                if now - p["last"] < 0.4:
                    return self.send_json({"error": "Lugn, en affär i taget"}, 429)
                p["last"] = now
                company = clean(body.get("company"), 30) or "Ny kund"
                p["sum"] += value
                p["deals"] += 1
                events.append({"type": "deal", "id": p["id"], "company": company, "value": value})
                return self.send_json(public(p))

        return self.send_json({"error": "Finns inte"}, 404)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Storskärm: http://localhost:{PORT}", flush=True)
    print(f"Spelare:   http://{lan_ip()}:{PORT}/play", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
