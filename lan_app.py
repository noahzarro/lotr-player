from pathlib import Path

from fastapi.staticfiles import StaticFiles
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

from auth import Auth
from player import Player

STATIC = Path(__file__).parent / "static"


class PairReq(BaseModel):
    code: str
    name: str


class PlayReq(BaseModel):
    name: str


class SubReq(BaseModel):
    enabled: bool


class SeekReq(BaseModel):
    seconds: float


def create_lan_app(player: Player, auth: Auth) -> FastAPI:
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    protected = [Depends(auth.dependency())]

    @app.get("/")
    def index():
        return FileResponse(STATIC / "lan.html")

    @app.get("/api/status")
    def status():
        return player.status()

    @app.post("/api/pair")
    def pair(req: PairReq, response: Response):
        name = req.name.strip()[:50]
        if not name:
            raise HTTPException(400, "name required")
        token = auth.redeem(req.code, name)
        if token is None:
            raise HTTPException(400, "invalid, expired or already used code")
        response.set_cookie("token", token, httponly=True, samesite="strict",
                            max_age=10 * 365 * 24 * 3600)
        return {"token": token, "name": name}

    @app.get("/api/me", dependencies=protected)
    def me(claims: dict = Depends(auth.dependency())):
        return {"name": claims["name"]}

    @app.get("/api/movies", dependencies=protected)
    def movies():
        return player.list_movies()

    @app.get("/api/movies/image", dependencies=protected)
    def movie_image(name: str):
        p = player.image_path(name)
        if p is None:
            raise HTTPException(404, "no image")
        return FileResponse(p)

    @app.post("/api/play", dependencies=protected)
    def play(req: PlayReq):
        if not player.play(req.name):
            raise HTTPException(404, "unknown movie")
        return {"ok": True}

    @app.post("/api/pause", dependencies=protected)
    def pause():
        player.pause()
        return {"ok": True}

    @app.post("/api/resume", dependencies=protected)
    def resume():
        player.resume()
        return {"ok": True}

    @app.post("/api/stop", dependencies=protected)
    def stop():
        player.stop()
        return {"ok": True}

    @app.post("/api/subtitles", dependencies=protected)
    def subtitles(req: SubReq):
        if not player.set_subtitles(req.enabled):
            raise HTTPException(409, "no subtitle track available")
        return {"ok": True}

    @app.post("/api/seek", dependencies=protected)
    def seek(req: SeekReq):
        player.seek(req.seconds)
        return {"ok": True}

    return app
