import base64
import io
import socket
from pathlib import Path

import qrcode
from fastapi import FastAPI
from fastapi.responses import FileResponse

from auth import Auth

STATIC = Path(__file__).parent / "static"


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no packet is actually sent
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def create_local_app(auth: Auth, lan_port: int) -> FastAPI:
    app = FastAPI()

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

    @app.get("/api/devices")
    def devices():
        return auth.devices()

    return app
