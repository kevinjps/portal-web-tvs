import os
import json
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# ──────────────────────────────
# PATHS
# ──────────────────────────────

BASE_DIR = Path(__file__).parent

STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
UPLOADS_DIR = BASE_DIR / "uploads"

UPLOADS_DIR.mkdir(exist_ok=True)

# ──────────────────────────────
# APP
# ──────────────────────────────

app = FastAPI(title="Local Signage")

# ──────────────────────────────
# MOUNT STATIC FILES
# ──────────────────────────────

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

# ──────────────────────────────
# ESTADO GLOBAL
# ──────────────────────────────

class TVState:
    def __init__(self):
        self.video_url: Optional[str] = None
        self.video_name: Optional[str] = None
        self.playing: bool = False

    def to_dict(self):
        return {
            "video_url": self.video_url,
            "video_name": self.video_name,
            "playing": self.playing,
        }

state = TVState()

# ──────────────────────────────
# WEBSOCKET MANAGER
# ──────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.all: list[WebSocket] = []
        self.tvs: set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.all.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.all:
            self.all.remove(ws)
        self.tvs.discard(ws)

    async def register_tv(self, ws: WebSocket):
        self.tvs.add(ws)
        await self.broadcast({"type": "tv_count", "count": len(self.tvs)})

    async def unregister_tv(self, ws: WebSocket):
        self.tvs.discard(ws)
        await self.broadcast({"type": "tv_count", "count": len(self.tvs)})

    async def broadcast(self, message: dict):
        data = json.dumps(message)
        dead = []
        for ws in self.all:
            try:
                await ws.send_text(data)
            except:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

manager = ConnectionManager()

# ──────────────────────────────
# ROTAS HTML
# ──────────────────────────────

@app.get("/")
async def root():
    return FileResponse(TEMPLATES_DIR / "index.html")

@app.get("/admin")
async def admin():
    return FileResponse(TEMPLATES_DIR / "admin.html")

@app.get("/tv")
async def tv():
    return FileResponse(TEMPLATES_DIR / "tv.html")

# ──────────────────────────────
# API DE VÍDEOS
# ──────────────────────────────

@app.get("/api/videos")
async def list_videos():
    allowed = {".mp4", ".webm", ".ogg", ".avi", ".mov", ".mkv"}
    files = []

    for f in sorted(UPLOADS_DIR.iterdir(), key=lambda x: -x.stat().st_ctime):
        if f.suffix.lower() in allowed:
            stat = f.stat()
            original = "_".join(f.name.split("_")[1:]) if "_" in f.name else f.name
            files.append({
                "filename": f.name,
                "original_name": original,
                "url": f"/uploads/{f.name}",
                "size": stat.st_size,
                "created_at": stat.st_ctime,
            })

    return files


@app.post("/api/upload")
async def upload_video(video: UploadFile = File(...)):
    allowed = {".mp4", ".webm", ".ogg", ".avi", ".mov", ".mkv"}
    ext = Path(video.filename).suffix.lower()

    if ext not in allowed:
        raise HTTPException(status_code=400, detail="Formato não suportado")

    safe_name = "".join(c if c.isalnum() or c in ".-_" else "_" for c in video.filename)
    filename = f"{int(time.time() * 1000)}_{safe_name}"
    dest = UPLOADS_DIR / filename

    with open(dest, "wb") as f:
        while chunk := await video.read(1024 * 1024):
            f.write(chunk)

    return {
        "filename": filename,
        "original_name": video.filename,
        "url": f"/uploads/{filename}",
        "size": dest.stat().st_size,
    }


@app.delete("/api/videos/{filename}")
async def delete_video(filename: str):
    file_path = UPLOADS_DIR / Path(filename).name

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    file_path.unlink()

    if state.video_url and filename in state.video_url:
        state.video_url = None
        state.video_name = None
        state.playing = False
        await manager.broadcast({"type": "stop"})

    return {"success": True}

# ──────────────────────────────
# CONTROLE
# ──────────────────────────────

class ControlAction(BaseModel):
    action: str
    video_url: Optional[str] = None
    video_name: Optional[str] = None


@app.get("/api/state")
async def get_state():
    return {**state.to_dict(), "tv_count": len(manager.tvs)}


@app.post("/api/control")
async def control(body: ControlAction):

    if body.action == "play":
        state.video_url = body.video_url
        state.video_name = body.video_name
        state.playing = True
        await manager.broadcast({
            "type": "play",
            "video_url": body.video_url,
            "video_name": body.video_name
        })

    elif body.action == "stop":
        state.playing = False
        await manager.broadcast({"type": "stop"})

    elif body.action == "pause":
        state.playing = False
        await manager.broadcast({"type": "pause"})

    elif body.action == "resume":
        state.playing = True
        await manager.broadcast({"type": "resume"})

    return {"success": True, "state": state.to_dict()}

# ──────────────────────────────
# WEBSOCKET
# ──────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    is_tv = False

    await ws.send_text(json.dumps({
        "type": "state",
        "state": state.to_dict(),
        "tv_count": len(manager.tvs),
    }))

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)

            if msg.get("type") == "identify" and msg.get("role") == "tv":
                is_tv = True
                await manager.register_tv(ws)

    except WebSocketDisconnect:
        manager.disconnect(ws)
        if is_tv:
            await manager.unregister_tv(ws)

# ──────────────────────────────
# RUN
# ──────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)