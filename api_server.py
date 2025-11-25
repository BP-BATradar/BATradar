import asyncio
from fastapi import FastAPI, WebSocket
import uvicorn

from classification.src.audio_server_rnn import stream_predict_websocket

app = FastAPI()

@app.websocket("/classification")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()

    async for msg in stream_predict_websocket(
        model_path="classification/models/rnn_model.joblib",
        device=0,
        mic_label="Main Mic",
        output_interval=5.0,
    ):
        await ws.send_json(msg)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)