import base64
import io
import ipaddress
import subprocess
from pathlib import Path

import qrcode
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI
from fastapi.responses import FileResponse

from auth import Auth

STATIC = Path(__file__).parent / "static"


SKIP_IFACES = ("lo", "tailscale", "virbr", "docker", "br-", "veth", "zt", "wg", "tun")


def lan_ip() -> str:
    """Return the IPv4 address of a physical LAN interface (RFC1918),
    ignoring Tailscale (100.64/10), VM bridges, docker, VPNs, etc."""
    try:
        out = subprocess.run(["ip", "-o", "-4", "addr", "show"], capture_output=True,
                             text=True, timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        out = ""
    candidates = []
    for line in out.splitlines():
        parts = line.split()
        iface, addr = parts[1], parts[3].split("/")[0]
        if iface.startswith(SKIP_IFACES):
            continue
        ip = ipaddress.ip_address(addr)
        if ip.is_private and not ip.is_loopback and not ip.is_link_local:
            candidates.append(addr)
    return candidates[0] if candidates else "127.0.0.1"


def create_local_app(auth: Auth, lan_port: int) -> FastAPI:
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/")
    def index():
        return FileResponse(STATIC / "local.html")

    @app.post("/api/code")
    def new_code():
        code = auth.create_code()
        url = f"http://{lan_ip()}:{lan_port}/?code={code}"
        buf = io.BytesIO()
        qrcode.make(url).save(buf, format="PNG")
        png = base64.b64encode(buf.getvalue()).decode()
        return {"code": code, "url": url, "qr": f"data:image/png;base64,{png}", "expires_in": 300}

    @app.post("/api/clear")
    def clear():
        auth.clear()
        return {"ok": True}

    @app.get("/api/devices")
    def devices():
        return auth.devices()

    return app
