from typing import Optional, Callable, Awaitable
import time
import requests
import os
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
            description="REQUIRED: JWT token from Django auth service (http://localhost:8001). Get token via POST /api/token/ after registration.",
        )
        django_validate_url: str = Field(
            default="http://django-auth:8001/internal/validate-token/",
            description="Django endpoint for JWT validation (internal use).",
        )
        internal_auth_token: str = Field(
            default="",
            description="Internal authentication token for backend-to-backend communication. Leave empty to use INTERNAL_AUTH_TOKEN environment variable.",
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
            description="Tamanho máximo (bytes) para arquivos recebidos — 1 MB por padrão.",
        )

    def __init__(self):
        self.type = "pipe"
        self.id = "fastapi_pipe"
        self.name = "FastAPI Pipe"
        self.valves = self.Valves()
        self.last_emit_time = 0.0  # controle de throttle dos status
        
        # Load internal auth token from environment if not set in valves
        if not self.valves.internal_auth_token:
            env_token = os.getenv("INTERNAL_AUTH_TOKEN", "")
            if env_token:
                self.valves.internal_auth_token = env_token
                print(f"[PIPELINE] Loaded INTERNAL_AUTH_TOKEN from environment: {env_token[:20]}...")
            else:
                print("[PIPELINE] WARNING: INTERNAL_AUTH_TOKEN not found in environment variables")
                print(f"[PIPELINE] Available environment variables: {[k for k in os.environ.keys() if 'TOKEN' in k or 'AUTH' in k]}")
        else:
            print(f"[PIPELINE] Using INTERNAL_AUTH_TOKEN from valves: {self.valves.internal_auth_token[:20]}...")

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

    def _validate_jwt_format(self, jwt_token: str) -> bool:
        """Validate JWT token format (should have 3 parts separated by dots)"""
        if not isinstance(jwt_token, str):
            return False
        
        parts = jwt_token.strip().split('.')
        return len(parts) == 3 and all(part for part in parts)

    async def _validate_user_jwt(self, user_jwt: str, __event_emitter__: Callable[[dict], Awaitable[None]]) -> tuple[bool, Optional[dict]]:
        """
        Validate user JWT with Django auth service
        
        Returns:
            tuple[bool, Optional[dict]]: (is_valid, user_info)
        """
        # Check if internal auth token is configured
        if not self.valves.internal_auth_token or self.valves.internal_auth_token.strip() == "":
            # Try to reload from environment as a fallback
            env_token = os.getenv("INTERNAL_AUTH_TOKEN", "")
            if env_token and env_token.strip():
                self.valves.internal_auth_token = env_token.strip()
                print(f"[PIPELINE] Reloaded INTERNAL_AUTH_TOKEN from environment: {env_token[:20]}...")
            else:
                error_msg = f"Internal auth token not configured. Environment check: INTERNAL_AUTH_TOKEN={'present' if env_token else 'missing'}"
                await self._emit_status(__event_emitter__, "error", error_msg, True)
                print(f"[PIPELINE] ERROR: {error_msg}")
                print(f"[PIPELINE] Available env vars: {[k for k in os.environ.keys() if 'TOKEN' in k or 'AUTH' in k]}")
                return False, None

        # Validate JWT format before sending to Django
        if not self._validate_jwt_format(user_jwt):
            await self._emit_status(__event_emitter__, "error", "Invalid JWT format", True)
            return False, None

        headers = {
            "Authorization": f"Bearer {self.valves.internal_auth_token}",
            "Content-Type": "application/json"
        }
        
        payload = {"jwt": user_jwt}

        try:
            await self._emit_status(__event_emitter__, "info", "Validating authentication...", False)
            response = requests.post(
                self.valves.django_validate_url,
                json=payload,
                headers=headers,
                timeout=15,  # Increased timeout for better reliability
            )
            
            if response.status_code == 200:
                try:
                    user_info = response.json()
                    username = user_info.get('username', 'unknown')
                    await self._emit_status(__event_emitter__, "info", f"Authentication validated for {username}", False)
                    return True, user_info
                except ValueError:
                    await self._emit_status(__event_emitter__, "error", "Invalid response from auth service", True)
                    return False, None
            else:
                error_msg = "Authentication failed"
                try:
                    error_detail = response.json().get("detail", "Invalid token")
                    error_msg = f"Authentication failed: {error_detail}"
                except:
                    error_msg = f"Authentication failed (HTTP {response.status_code})"
                
                await self._emit_status(__event_emitter__, "error", error_msg, True)
                return False, None
                
        except requests.Timeout:
            await self._emit_status(__event_emitter__, "error", "Authentication service timeout", True)
            return False, None
        except requests.ConnectionError:
            await self._emit_status(__event_emitter__, "error", "Cannot connect to authentication service", True)
            return False, None
        except requests.RequestException as exc:
            await self._emit_status(__event_emitter__, "error", f"Auth validation error: {exc}", True)
            return False, None

    async def pipe(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__: Callable[[dict], Awaitable[None]] = None,
        __event_call__: Callable[[dict], Awaitable[dict]] = None,
    ) -> Optional[dict]:

        await self._emit_status(__event_emitter__, "info", "Processando entrada...", False)

        # Extract user JWT from OpenWebUI context or valves
        user_jwt = None
        jwt_source = "unknown"
        
        # First try to get JWT from OpenWebUI user context (preferred method)
        if __user__ and isinstance(__user__, dict):
            # Try multiple possible field names for JWT token
            for field_name in ["token", "jwt", "access_token", "bearer_token"]:
                token = __user__.get(field_name)
                if token and isinstance(token, str) and token.strip():
                    user_jwt = token.strip()
                    jwt_source = f"user_context.{field_name}"
                    break
        
        # Fallback to valves configuration
        if not user_jwt and self.valves.bearer_token:
            token = self.valves.bearer_token.strip()
            if token:
                user_jwt = token
                jwt_source = "valves.bearer_token"

        # Check if we have a JWT token
        if not user_jwt:
            await self._emit_status(__event_emitter__, "error", "Authentication required", True)
            return {"error": "Authentication required. Please log in at Django Auth (http://localhost:8001) and provide the JWT token in the pipeline settings."}

        # Log JWT source for debugging
        print(f"[PIPELINE] Using JWT from: {jwt_source}")

        # Validate the user JWT with Django
        is_valid, user_info = await self._validate_user_jwt(user_jwt, __event_emitter__)
        if not is_valid:
            return {"error": "Authentication failed. Please check your JWT token and try again."}

        messages = body.get("messages", [])
        if not messages:
            await self._emit_status(__event_emitter__, "error", "Nenhuma mensagem encontrada", True)
            return {"error": "Nenhuma mensagem encontrada"}

        last_content = messages[-1]["content"]
        question = self._extract_text(last_content)

        # Use the user's JWT for FastAPI call (FastAPI will validate it again with Django)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {user_jwt}"
        }

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