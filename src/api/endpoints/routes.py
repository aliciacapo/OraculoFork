from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from src.api.models import Question
from src.api.controller.AskController import AskController
import os

router = APIRouter()

ask = AskController()

@router.post("/ask")
async def ask_question(question: Question):
    try:
        return ask.ask(question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Endpoint para servir arquivos de gráficos
@router.get("/static/graficos/{filename}")
def serve_grafico(filename: str):
    path = os.path.join("src/api/static/graficos", filename)
    if os.path.exists(path):
        return FileResponse(path)
    else:
        raise HTTPException(status_code=404, detail="Gráfico não encontrado")