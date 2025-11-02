from src.assets.pattern.singleton import SingletonMeta
from src.api.models import Question, Response

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import SystemMessage, HumanMessage
from google import genai
from src.api.database.MyVanna import MyVanna

from src.assets.aux.env import env
# Gemini env vars
GEMINI_API_KEY = env["GEMINI_API_KEY"]
GEMINI_MODEL_NAME = env["GEMINI_MODEL_NAME"]

class AskController(metaclass=SingletonMeta):
    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY)

        self.gen = ChatGoogleGenerativeAI(model=GEMINI_MODEL_NAME,
            google_api_key=GEMINI_API_KEY,
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2,
            convert_system_message_to_human=True
            )

        self.vn = MyVanna(config={
            'print_prompt': False, 
            'print_sql': False,
            'api_key': GEMINI_API_KEY,
            'model_name': GEMINI_MODEL_NAME
        })

        self.vn.prepare()

    def ask(self, question: Question):

        try:

            mensagem = [SystemMessage(content="""Você é um assistente em um sistema que de chat AI,
                         seu trabalho é receber uma mensagem de um humano e tratar ela para ser processada
                         por outra IA que possui falhas. Dentro dos tratamentos necessários estão:
                         -Trocar datas que são dadas em formato que não sejam dias, por exemplo 3 mêses,
                         e transformar em dias, 90 dias. Outro exemplo, 1 ano e 2 meses, trocar por 425 dias
                         (serão considerados que os mêses separados terão 30 dias)
                         -Quando usada a expressão "mudança" referente ao repositório, você trocara por "commit",
                         por exemplo, "qual foi a ultima mudança feita no repositório?" será trocado por
                         "qual foi o ultimo commit feito no repositório?)
                         NÃO explique, NÃO confirme, NÃO dê exemplos. Apenas RETORNE a mensagem tratada.
                         Mensagem a ser processada:"""),HumanMessage(content=question.question)]

            ai_mensagem = self.gen.invoke(mensagem)

            print(ai_mensagem.content)

            sql_gerado = self.vn.generate_sql(ai_mensagem.content)

            if "SELECT" not in sql_gerado.upper():
                return {"output": "Não consegui entender sua pergunta bem o suficiente para gerar uma resposta SQL válida."}

            resultado = self.vn.run_sql(sql_gerado)

            if not resultado:
                return {"output": "A consulta foi feita, mas não há dados correspondentes no banco."}

            # Prompt mais informativo
            prompt = f"""
            Você é um assistente que responde perguntas sobre dados extraídos do GitHub.

            Pergunta do usuário: "{question.question}"

            Resultado da consulta SQL: {resultado}

            Gere uma resposta clara e útil para o usuário, explicando o que o resultado significa.
            """


            response = self.client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": list[Response],
                }
            )

            texto = response.parsed[0].texto
            return {"output": texto}

        except Exception as e:
            return {"output": f"Ocorreu um erro ao processar sua pergunta: {str(e)}"}