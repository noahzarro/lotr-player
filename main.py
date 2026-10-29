import asyncio
from pathlib import Path

import uvicorn

from auth import Auth
from lan_app import create_lan_app
from local_app import create_local_app
from player import Player

MOVIE_DIR = Path("/home/noah/private/lotr-player/movies")  # hardcoded movie folder
LAN_PORT = 8000
LOCAL_PORT = 8001


async def main():
    player = Player(MOVIE_DIR, fullscreen=True)
    auth = Auth()
    lan = uvicorn.Server(uvicorn.Config(create_lan_app(player, auth), host="0.0.0.0", port=LAN_PORT))
    local = uvicorn.Server(uvicorn.Config(create_local_app(auth, LAN_PORT), host="127.0.0.1", port=LOCAL_PORT))
    print(f"Admin page (host only): http://127.0.0.1:{LOCAL_PORT}")
    await asyncio.gather(lan.serve(), local.serve())


if __name__ == "__main__":
    asyncio.run(main())
