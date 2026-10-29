# lotr-player

Play movies on the host with VLC and control them from any device on the local network.
Anyone on the network can also read the current playback status through a public API.

- [For admins](#for-admins): run the script, pair phones, control movies
- [For users](#for-users): use the status API in your own projects

---

# For admins

## How it works

Two web servers run in one process:

| Server | Address | Purpose |
|---|---|---|
| Admin | `127.0.0.1:8001` | Host only. Creates one-time codes and QR codes, lists paired devices. |
| LAN | `0.0.0.0:8000` | Public status plus the JWT-protected controls. |

## Requirements

- Python 3.10+
- VLC / libvlc installed on the host
- `python3-venv` (on Debian/Ubuntu: `sudo apt install python3-venv`)

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Put one folder per movie in the `movies/` folder. The path is hardcoded as `MOVIE_DIR` at the top
of `main.py`. The folder name is the movie name.

```
movies/
  The Fellowship of the Ring/
    movie.mkv     required (mp4, mkv, avi, mov, webm, m4v, mpg, mpeg, wmv)
    sub.srt       optional subtitles (srt, sub, ass, ssa, vtt, smi), loaded into VLC
    image.jpg     cover shown in the selection screen (jpg, jpeg, png, webp, gif, bmp)
```

Folders without a `movie.<ext>` file are ignored.

## Run

```bash
.venv/bin/python main.py
```

Then open `http://127.0.0.1:8001` on the host.

## Pairing a device

1. On the admin page, click **Add new device**. A QR code and a one-time code appear.
2. Scan the QR code with the device. It opens the LAN site with the code prefilled.
3. Enter a name and press **Pair**. The server returns a JWT, which is stored in a cookie.

A code is valid for 5 minutes and can be used once. Tokens are kept in memory only, so
restarting the script invalidates all paired devices.

The QR code uses the first private IPv4 address of a physical interface. Tailscale, VM bridges,
docker and VPN interfaces are skipped (see `lan_ip()` in `local_app.py`).

## Controlling movies

Open `http://<host-LAN-IP>:8000` on a paired device. You can pick a movie, pause, resume, stop
and seek (+/-30 s). Unpaired devices only see the pairing form and the status.

Protected endpoints (cookie `token` or header `Authorization: Bearer <jwt>`):

- `GET /api/me`
- `GET /api/movies` returns `[{name, has_image, has_sub}]`
- `GET /api/movies/image?name=<name>`
- `POST /api/play` with `{name}`
- `POST /api/pause`
- `POST /api/resume`
- `POST /api/stop`
- `POST /api/seek` with `{seconds}`

## Files

- `main.py` starts both servers and holds the config (movie folder, ports).
- `player.py` is the VLC wrapper.
- `auth.py` handles one-time codes, JWTs and the device registry.
- `lan_app.py` is the LAN API and UI.
- `local_app.py` is the admin API and UI.
- `static/` holds the HTML pages and `theme.css`.

## Notes

- VLC starts fullscreen. Set `fullscreen=False` in `main.py` to change that.
- Traffic is plain HTTP, so only use it on a network you trust.

---

# For users

You don't need to pair or log in to read the status. Ask the admin for the host's address.
Below it is written as `http://<host>:8000`.

## Status endpoint

```
GET http://<host>:8000/api/status
```

Example response while a movie plays:

```json
{
  "movie": "The Fellowship of the Ring",
  "state": "playing",
  "position_s": 1234.5,
  "length_s": 10680.0,
  "lookup_time": 1761758400.123
}
```

| Field | Meaning |
|---|---|
| `movie` | Folder name of the current movie, or `null` if nothing is loaded. |
| `state` | `playing`, `paused`, `loading` or `stopped`. |
| `position_s` | Playback position in seconds, or `null` if nothing is playing. |
| `length_s` | Movie length in seconds, or `null` if unknown. |
| `lookup_time` | Unix time (seconds) at which the server read the position. |

The position is a snapshot. Between the read and when you receive it, a playing movie has moved
on. To estimate the position right now, add the time elapsed since `lookup_time`:

```
current = position_s + (now - lookup_time)    # only while state == "playing"
```

This assumes your clock and the host's clock are in sync. Otherwise poll again instead.

## Examples

curl:

```bash
curl http://<host>:8000/api/status
```

Python:

```python
import requests

s = requests.get("http://<host>:8000/api/status", timeout=3).json()
if s["state"] == "playing":
    print(f'{s["movie"]} at {s["position_s"]:.0f}s')
```

JavaScript:

```js
const s = await (await fetch("http://<host>:8000/api/status")).json();
console.log(s.movie, s.position_s);
```

## Notes

- The endpoint is read-only. Controlling playback needs a token from an admin.
- Poll at a reasonable rate, for example once per second.
- The server is plain HTTP and only reachable on the local network. If you call it from a web page
  served over HTTPS, the browser will block the request as mixed content.
- Browsers on other origins may also be blocked by CORS. Calls from scripts or servers are not
  affected.
