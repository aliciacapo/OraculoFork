from src.assets.pattern.singleton import SingletonMeta
from src.api.models import Question, Response

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import SystemMessage, HumanMessage, AIMessage
from langchain.memory import ConversationBufferWindowMemory
from langchain.chains import LLMChain
from langchain.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from google import genai
from src.api.database.MyVanna import MyVanna
import json
from typing import Dict, Optional
import hashlib

from src.assets.aux.env import env

# Gemini env vars
GEMINI_API_KEY = env["GEMINI_API_KEY"]
GEMINI_MODEL_NAME = env["GEMINI_MODEL_NAME"]


class AskController(metaclass=SingletonMeta):
    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY)

        # LLM principal para geração de respostas
        self.llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL_NAME,
            google_api_key=GEMINI_API_KEY,
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2,
            convert_system_message_to_human=True
        )

        # Memória conversacional (mantém últimas 5 interações)
        self.memory = ConversationBufferWindowMemory(
            k=5,  # Número de interações a manter
            memory_key="chat_history",
            return_messages=True,
            input_key="question",
            output_key="answer"
        )

        # Chain para pré-processamento com contexto
        self.preprocessing_chain = self._create_preprocessing_chain()

        # instancia do vanna
        self.vn = MyVanna(config={
            'print_prompt': False,
            'print_sql': False,
            'api_key': GEMINI_API_KEY,
            'model_name': GEMINI_MODEL_NAME
        })
        self.vn.prepare()

        # Cache simples para queries SQL (em memória)
        self.sql_cache: Dict[str, str] = {}
        self.result_cache: Dict[str, any] = {}

    def _create_preprocessing_chain(self) -> LLMChain:
        """Cria chain para pré-processar perguntas com contexto da conversa"""
        
        system_template = """Você é um assistente especializado em processar perguntas sobre dados do GitHub.

Sua função é:
1. Analisar o histórico da conversa para entender o contexto
2. Resolver referências contextuais (ex: "e no mês passado?", "mostre mais detalhes", "e o outro repositório?")
3. Normalizar expressões temporais:
   - "3 meses" → "90 dias"
   - "1 ano e 2 meses" → "425 dias"
   - Meses separados = 30 dias cada
4. Normalizar terminologia:
   - "mudança" → "commit"
   - "alteração" → "commit"
5. Expandir a pergunta com contexto necessário do histórico

REGRAS CRÍTICAS:
- Se a pergunta fizer referência a algo anterior ("e aquele", "o outro", "também"), inclua o contexto explícito
- Se não houver referência contextual, retorne a pergunta apenas normalizada
- NÃO explique, NÃO confirme, NÃO dê exemplos
- Retorne APENAS a pergunta processada e expandida

Histórico da conversa está disponível abaixo."""

        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_template),
            MessagesPlaceholder(variable_name="chat_history"),
            HumanMessagePromptTemplate.from_template("{question}")
        ])

        return LLMChain(
            llm=self.llm,
            prompt=prompt,
            memory=self.memory,
            verbose=False
        )

    def _get_cache_key(self, text: str) -> str:
        """Gera chave de cache baseada no hash da pergunta normalizada"""
        normalized = text.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()

    def _validate_sql(self, sql: str) -> tuple[bool, Optional[str]]:
        """Valida SQL gerado para segurança"""
        sql_upper = sql.upper().strip()
        
        # Whitelist: apenas SELECT permitido
        if not sql_upper.startswith("SELECT"):
            return False, "Apenas queries SELECT são permitidas"
        
        # Blacklist: operações perigosas
        dangerous_keywords = [
            "DELETE", "DROP", "TRUNCATE", "INSERT", 
            "UPDATE", "ALTER", "CREATE", "GRANT", "REVOKE"
        ]
        
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                return False, f"Operação '{keyword}' não é permitida"
        
        # Limite de complexidade (número de JOINs)
        join_count = sql_upper.count("JOIN")
        if join_count > 10:
            return False, "Query muito complexa (máximo 10 JOINs)"
        
        return True, None

    def _format_response_with_context(self, question: str, sql: str, result: any) -> str:
        """Formata resposta final usando LLM com contexto conversacional"""
        
        # Recupera histórico da memória
        memory_vars = self.memory.load_memory_variables({})
        chat_history = memory_vars.get("chat_history", [])
        
        # Monta contexto do histórico
        history_context = ""
        if chat_history:
            history_context = "\n\nContexto da conversa anterior:\n"
            for msg in chat_history[-3:]:  # Últimas 3 mensagens
                if isinstance(msg, HumanMessage):
                    history_context += f"Usuário: {msg.content}\n"
                elif isinstance(msg, AIMessage):
                    history_context += f"Assistente: {msg.content}\n"

        prompt = f"""
Você é um assistente especializado em análise de dados do GitHub.

{history_context}

Pergunta atual: "{question}"

SQL gerado e executado:
```sql
{sql}
```

Resultado da consulta: {result}

Com base no contexto da conversa e nos resultados, gere uma resposta:
1. Clara e direta
2. Em linguagem natural
3. Destacando insights relevantes
4. Relacionando com perguntas anteriores se aplicável
5. Formato estruturado se houver múltiplos dados

Responda de forma conversacional e útil.
"""

        try:
            response = self.client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": list[Response],
                }
            )
            return response.parsed[0].texto
        except Exception as e:
            # Fallback para resposta simples
            return f"Resultado: {result}"

    def ask(self, question: Question, session_id: Optional[str] = None) -> dict:
        """
        Processa pergunta com contexto conversacional
        
        Args:
            question: Objeto Question com a pergunta do usuário
            session_id: ID da sessão para memória multi-usuário (futuro)
        """
        
        # --- Dentro de ask() ---
        try:
            original_question = question.question

            # Etapa 1: Pré-processar com contexto (usando chain)
            processed_question = self.preprocessing_chain.invoke({
                "question": original_question
            })
            if isinstance(processed_question, dict) and "text" in processed_question:
                processed_question = processed_question["text"]
            elif not isinstance(processed_question, str):
                processed_question = str(processed_question)

            print(f"[Preprocessed] {processed_question}")

            # Etapa 2: Verificar cache de SQL
            cache_key = self._get_cache_key(processed_question)
            
            if cache_key in self.sql_cache:
                print(f"[Cache Hit] SQL encontrado no cache")
                sql_gerado = self.sql_cache[cache_key]
            else:
                sql_gerado = self.vn.generate_sql(processed_question)

                is_valid, error_msg = self._validate_sql(sql_gerado)
                if not is_valid:
                    return {
                        "output": f"Query inválida: {error_msg}",
                        "error": True
                    }

                self.sql_cache[cache_key] = sql_gerado
                print(f"[Cache Miss] SQL gerado e armazenado")

            print(f"[SQL] {sql_gerado}")

            result_cache_key = hashlib.md5(sql_gerado.encode()).hexdigest()

            if result_cache_key in self.result_cache:
                print(f"[Cache Hit] Resultado encontrado no cache")
                resultado = self.result_cache[result_cache_key]
            else:
                resultado = self.vn.run_sql(sql_gerado)
                if not resultado:
                    self.memory.save_context(
                        inputs={"question": original_question},
                        outputs={"answer": "Não há dados correspondentes no banco."}
                    )
                    return {
                        "output": "A consulta foi executada, mas não há dados correspondentes.",
                        "sql": sql_gerado
                    }

                self.result_cache[result_cache_key] = resultado
                print(f"[Cache Miss] Resultado obtido e armazenado")

            resposta_formatada = self._format_response_with_context(
                question=original_question,
                sql=sql_gerado,
                result=resultado
            )

            self.memory.save_context(
                inputs={"question": original_question},
                outputs={"answer": resposta_formatada}
            )

            return {
                "output": resposta_formatada,
                "sql": sql_gerado,
                "cached": result_cache_key in self.result_cache
            }

        except Exception as e:
            error_msg = f"Erro ao processar pergunta: {str(e)}"
            print(f"[Error] {error_msg}")

            self.memory.save_context(
                inputs={"question": question.question},
                outputs={"answer": error_msg}
            )

            return {
                "output": error_msg,
                "error": True
            }


    def clear_memory(self):
        """Limpa o histórico da conversa"""
        self.memory.clear()
        print("[Memory] Histórico limpo")

    def get_conversation_history(self) -> list:
        """Retorna o histórico da conversa"""
        memory_vars = self.memory.load_memory_variables({})
        return memory_vars.get("chat_history", [])

    def clear_cache(self):
        """Limpa os caches de SQL e resultados"""
        self.sql_cache.clear()
        self.result_cache.clear()
        print("[Cache] Caches limpos")