from src.assets.pattern.singleton import SingletonMeta
from src.api.models import Question, Response

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import SystemMessage, HumanMessage, AIMessage
from langchain.memory import ConversationBufferWindowMemory
from google import genai
from src.api.database.MyVanna import MyVanna
import json
from typing import Dict, Optional
import pandas as pd
import matplotlib.pyplot as plt
import uuid
import os
import hashlib
import re

from src.assets.aux.env import env

# Gemini env vars
GEMINI_API_KEY = env["GEMINI_API_KEY"]
GEMINI_MODEL_NAME = env["GEMINI_MODEL_NAME"]


class AskController(metaclass=SingletonMeta):

    # Diretório estático para salvar gráficos
    STATIC_DIR = os.path.join(os.getcwd(), "static", "graficos")
        
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
            k=5,
            memory_key="chat_history",
            return_messages=True,
            input_key="question",
            output_key="answer"
        )

        # Instância do vanna
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
    
    def _generate_chart_if_requested(self, resultado, wants_chart: bool):
            """
            Gera um gráfico a partir do resultado se wants_chart for True.
            Salva o gráfico em arquivo e retorna o link, ou mensagem de erro se não houver dados.
            """
            if not wants_chart:
                return None
            # Garante que o diretório existe
            os.makedirs(self.STATIC_DIR, exist_ok=True)
            df = pd.DataFrame(resultado)
            if df.empty:
                return {"output": "Não há dados suficientes para gerar um gráfico."}

            plt.figure(figsize=(8, 5))
            if df.shape[1] >= 2:
                x = df.columns[0]
                y = df.columns[1]
                plt.bar(df[x], df[y])
                plt.xlabel(x)
                plt.ylabel(y)
                plt.title("Gráfico gerado a partir dos dados")
            else:
                plt.plot(df[df.columns[0]])
                plt.title("Gráfico gerado a partir dos dados")

            filename = f"{uuid.uuid4()}.png"
            filepath = os.path.join(self.STATIC_DIR, filename)
            plt.tight_layout()
            plt.savefig(filepath)
            plt.close()

            link = f"http://localhost:8000/static/graficos/{filename}"
            return {"output": f"Gráfico gerado: [Clique aqui para visualizar]({link})", "grafico_url": link}
    
    def _detect_chart_request(self, question: str) -> bool:
            """
            Detecta se a pergunta do usuário sugere a geração de um gráfico.
            """
            chart_keywords = [
                "gráfico", "grafico", "plot", "visualização", "visualizacao",
                "chart", "plotar", "desenhar gráfico", "desenhar grafico", "mostrar gráfico",
                "mostrar grafico", "visualize", "visualizar", "figure", "figura"
            ]
            question_lower = question.lower()
            return any(kw in question_lower for kw in chart_keywords)

    def _preprocess_question(self, question: str) -> str:
        """
        Pré-processa a pergunta usando LLM com contexto da memória
        Versão simplificada sem LLMChain para evitar problemas de parsing
        """
        try:
            # Recupera histórico da memória
            memory_vars = self.memory.load_memory_variables({})
            chat_history = memory_vars.get("chat_history", [])
            
            # Monta contexto do histórico
            history_text = ""
            if chat_history:
                history_text = "Histórico da conversa:\n"
                for msg in chat_history[-5:]:  # Últimas 5 mensagens
                    if isinstance(msg, HumanMessage):
                        history_text += f"Usuário: {msg.content}\n"
                    elif isinstance(msg, AIMessage):
                        history_text += f"Assistente: {msg.content}\n"
                history_text += "\n"

            # Monta o prompt
            system_prompt = """Você é um assistente especializado em processar perguntas sobre dados do GitHub.

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
        6. Desenvolver análises robustas dos dados extraídos para que insight valiosos sejam extraídos
        7. 

        REGRAS CRÍTICAS:
        - Se a pergunta fizer referência a algo anterior ("e aquele", "o outro", "também"), inclua o contexto explícito
        - Se não houver referência contextual, retorne a pergunta apenas normalizada
        """

            # Monta mensagens
            messages = [
                SystemMessage(content=system_prompt)
            ]
            
            # Adiciona histórico se existir
            if history_text:
                messages.append(HumanMessage(content=history_text))
            
            # Adiciona pergunta atual
            messages.append(HumanMessage(content=f"Pergunta a processar: {question}"))
            
            # Chama LLM
            response = self.llm.invoke(messages)
            
            # Extrai conteúdo da resposta
            if hasattr(response, 'content'):
                processed = response.content.strip()
            else:
                processed = str(response).strip()
            
            # Remove qualquer explicação extra (pega só a primeira linha)
            processed = processed.split('\n')[0].strip()
            
            return processed
            
        except Exception as e:
            print(f"[Warning] Erro no preprocessing: {e}. Usando pergunta original.")
            return question

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
        
        # Blacklist com word boundaries (evita falsos positivos)
        dangerous_patterns = [
            r'\bDELETE\b',
            r'\bDROP\b',
            r'\bTRUNCATE\b',
            r'\bINSERT\b',
            r'\bUPDATE\b',
            r'\bALTER\b',
            r'\bCREATE\s+TABLE\b', 
            r'\bCREATE\s+INDEX\b',
            r'\bCREATE\s+DATABASE\b',
            r'\bGRANT\b',
            r'\bREVOKE\b',
            r'\bEXEC\b',
            r'\bEXECUTE\b',
            r';\s*\w+',  # SQL injection
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, sql_upper):
                keyword = pattern.replace(r'\b', '').replace(r'\s+', ' ')
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
            print(f"[Error] Erro ao formatar resposta: {e}")
            # Fallback para resposta simples
            return f"Consulta executada com sucesso. Resultado: {result}"

    def ask(self, question: Question, session_id: Optional[str] = None) -> dict:
        """
        Processa pergunta com contexto conversacional
        
        Args:
            question: Objeto Question com a pergunta do usuário
            session_id: ID da sessão para memória multi-usuário (futuro)
        """
        
        try:
            original_question = question.question
            print(f"[Original] {original_question}")

            # Detectar intenção de gráfico
            wants_chart = self._detect_chart_request(original_question)

            # Etapa 1: Pré-processar com contexto
            processed_question = self._preprocess_question(original_question)
            print(f"[Preprocessed] {processed_question}")

            # Etapa 2: Verificar cache de SQL
            cache_key = self._get_cache_key(processed_question)
            
            if cache_key in self.sql_cache:
                print(f"[Cache Hit] SQL encontrado no cache")
                sql_gerado = self.sql_cache[cache_key]
            else:
                # Gerar SQL com Vanna
                sql_gerado = self.vn.generate_sql(processed_question)

                # Validar SQL
                is_valid, error_msg = self._validate_sql(sql_gerado)
                if not is_valid:
                    return {
                        "output": f"Query inválida: {error_msg}",
                        "error": True
                    }

                # Armazenar no cache
                self.sql_cache[cache_key] = sql_gerado
                print(f"[Cache Miss] SQL gerado e armazenado")

            print(f"[SQL] {sql_gerado}")

            # Etapa 3: Verificar cache de resultados
            result_cache_key = hashlib.md5(sql_gerado.encode()).hexdigest()

            if result_cache_key in self.result_cache:
                print(f"[Cache Hit] Resultado encontrado no cache")
                resultado = self.result_cache[result_cache_key]
            else:
                # Executar SQL
                resultado = self.vn.run_sql(sql_gerado)
                
                if not resultado:
                    # Salvar na memória mesmo sem resultado
                    self.memory.save_context(
                        inputs={"question": original_question},
                        outputs={"answer": "Não há dados correspondentes no banco."}
                    )
                    return {
                        "output": "A consulta foi executada, mas não há dados correspondentes.",
                        "sql": sql_gerado
                    }
                
                # Armazenar resultado no cache
                self.result_cache[result_cache_key] = resultado
                print(f"[Cache Miss] Resultado obtido e armazenado")

            # Etapa 4: Gerar gráfico se solicitado
            chart_result = self._generate_chart_if_requested(resultado, wants_chart)

            # Etapa 5: Formatar resposta com contexto
            resposta_formatada = self._format_response_with_context(
                question=original_question,
                sql=sql_gerado,
                result=resultado
            )

            # Etapa 6: Salvar na memória
            self.memory.save_context(
                inputs={"question": original_question},
                outputs={"answer": resposta_formatada}
            )

            response = {
                "output": resposta_formatada,
                "sql": sql_gerado,
                "cached": result_cache_key in self.result_cache,
                "wants_chart": wants_chart
            }
            if chart_result:
                response.update(chart_result)
            return response

        except Exception as e:
            import traceback
            error_msg = f"Erro ao processar pergunta: {str(e)}"
            print(f"[Error] {error_msg}")
            print(f"[Error] Traceback: {traceback.format_exc()}")

            # Salvar erro na memória
            try:
                self.memory.save_context(
                    inputs={"question": question.question},
                    outputs={"answer": error_msg}
                )
            except:
                pass

            return {
                "output": error_msg,
                "error": True,
                "wants_chart": False
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
