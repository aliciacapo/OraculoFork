from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from src.api.models import Question
from src.api.controller.AskController import AskController
from src.api.middleware.auth import validate_user_jwt
import os

router = APIRouter()

ask = AskController()

@router.post("/ask")
async def ask_question(question: Question, user_info: dict = Depends(validate_user_jwt)):
    """Ask a question to the LLM - requires valid JWT and AccessToken"""
    try:
        print(f"[ASK] Processing question for user {user_info.get('user_id')}: {question.question}")
        result = ask.ask(question)
        print(f"[ASK] Response generated successfully")
        return result
    except Exception as e:
        print(f"[ASK] Error processing question: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Endpoint para servir arquivos de gráficos
@router.get("/static/graficos/{filename}")
def serve_grafico(filename: str):
    path = os.path.join("src/api/static/graficos", filename)
    if os.path.exists(path):
        return FileResponse(path)
    else:
        raise HTTPException(status_code=404, detail="Gráfico não encontrado")