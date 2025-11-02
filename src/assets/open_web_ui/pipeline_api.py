from typing import Optional, Callable, Awaitable
import time
import requests
from pydantic import BaseModel, Field


class Pipe:

    class Valves(BaseModel):
        """Configurações editáveis no painel do OpenWebUI."""

        api_url: str = Field(
            default="http://back-end:8000/ask",
            description="Endpoint da API FastAPI que recebe a pergunta (POST).",
        )
        bearer_token: str = Field(
            default="",
            description="Token Bearer opcional para autenticação na API.",
        )
        emit_interval: float = Field(
            default=2.0,
            description="Intervalo, em segundos, entre atualizações de status no UI.",
        )
        enable_status_indicator: bool = Field(
            default=True,
            description="Ativa ou desativa a barra de progresso no chat.",
        )
        max_file_size: int = Field(
            default=1048576,
            description="Tamanho máximo (bytes) para arquivos recebidos — 1 MB por padrão.",
        )

    def __init__(self):
        self.type = "pipe"
        self.id = "fastapi_pipe"
        self.name = "FastAPI Pipe"
        self.valves = self.Valves()
        self.last_emit_time = 0.0  # controle de throttle dos status

    async def _emit_status(
        self,
        __event_emitter__: Callable[[dict], Awaitable[None]],
        level: str,
        message: str,
        done: bool = False,
    ) -> None:
        now = time.time()
        if (
            __event_emitter__
            and self.valves.enable_status_indicator
            and (now - self.last_emit_time >= self.valves.emit_interval or done)
        ):
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "status": "complete" if done else "in_progress",
                        "level": level,
                        "description": message,
                        "done": done,
                    },
                }
            )
            self.last_emit_time = now

    async def pipe(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__: Callable[[dict], Awaitable[None]] = None,
        __event_call__: Callable[[dict], Awaitable[dict]] = None,
    ) -> Optional[dict]:

        await self._emit_status(__event_emitter__, "info", "Processando entrada...", False)

        messages = body.get("messages", [])
        if not messages:
            await self._emit_status(__event_emitter__, "error", "Nenhuma mensagem encontrada", True)
            return {"error": "Nenhuma mensagem encontrada"}

        last_content = messages[-1]["content"]
        question = self._extract_text(last_content)

        headers = {"Content-Type": "application/json"}
        if self.valves.bearer_token:
            headers["Authorization"] = f"Bearer {self.valves.bearer_token}"

        payload = {"question": question}

        await self._emit_status(__event_emitter__, "info", "Chamando API FastAPI...", False)

        try:
            response = requests.post(
                self.valves.api_url,
                json=payload,
                headers=headers,
                timeout=120,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            await self._emit_status(__event_emitter__, "error", f"Erro: {exc}", True)
            return {"error": str(exc)}

        try:
            data = response.json()
        except ValueError:
            data = {"output": response.text}

        grafico_url = data.get("grafico_url")
        if grafico_url:
            # link já incluído no output, apenas mostra o texto
            answer = data.get("output")
        else:
            answer = data.get("output") or data

        body["messages"].append({"role": "assistant", "content": answer})

        await self._emit_status(__event_emitter__, "info", "Resposta entregue", True)
        return answer

    def _extract_text(self, content) -> str:
        if isinstance(content, str):
            return content.replace("Prompt: ", "", 1).strip()

        text_found = ""
        file_detected = False
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and item.get("text"):
                    text_found = item["text"].strip()
                elif item.get("type") == "file" and not text_found:
                    file_detected = True
                    size = item.get("size", 0)
                    name = item.get("name", "arquivo")
                    if size > self.valves.max_file_size:
                        text_found = f"Recebemos o arquivo {name}, mas ele é muito grande para ser processado."
                    else:
                        text_found = f"Recebemos o arquivo {name}. Ainda não processamos arquivos neste chat."
        return text_found or "Arquivo recebido."