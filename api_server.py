import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from system_manager import SystemManager

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = SystemManager(
    model_path="classification/models/rnn_model.joblib",
    device=0,
    mic_label="Main Mic",
    detection_threshold=0.5,
    localization_cycles=5,
    cycle_interval=4.0,
    cooldown_seconds=25.0,
)

@app.on_event("startup")
async def startup_event():
    manager.start()

@app.on_event("shutdown")
async def shutdown_event():
    manager.stop()

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    print("WebSocket client connected")
    
    try:
        async for msg in manager.event_stream():
            print(f"Sending to frontend: {msg['type']}")
            await ws.send_json(msg)
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        print("WebSocket client disconnected")
        try:
            await ws.close()
        except RuntimeError:
            pass

@app.post("/api/trigger-localization")
async def trigger_localization():
    manager.trigger_localization()
    return {"status": "ok", "message": "Localization triggered"}

@app.post("/api/pause-classification")
async def pause_classification():
    manager.pause_for_manual()
    return {"status": "ok", "message": "Classification pause requested"}

@app.get("/api/status")
async def get_status():
    return {
        "state": manager.state.value,
        "latest_localization": manager._latest_localization,
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
