from src.assets.pattern.singleton import SingletonMeta

from vanna.vannadb import VannaDB_VectorStore
from vanna.google import GoogleGeminiChat
from vanna.chromadb import ChromaDB_VectorStore
import psycopg2
import os

from src.assets.aux.env import env
# DB env vars
DB_HOST = env["DB_HOST"]
DB_PORT = env["DB_PORT"]
DB_NAME = env["DB_NAME"]
DB_USER = env["DB_USER"]
DB_PASSWORD = env["DB_PASSWORD"]
DB_URL = env["DB_URL"]

class ChromaDB_VectorStoreReset(ChromaDB_VectorStore):
    def __init__(self, config=None):
        if config is None:
            config = {}
        
        # Força o reset na inicialização
        config["reset_on_init"] = config.get("reset_on_init", True)
        
        super().__init__(config=config)
        
        # Limpa as coleções após a inicialização padrão
        if config["reset_on_init"]:
            self._reset_collections()
            
            # Recria as coleções vazias
            collection_metadata = config.get("collection_metadata", None)
            self.documentation_collection = self.chroma_client.get_or_create_collection(
                name="documentation",
                embedding_function=self.embedding_function,
                metadata=collection_metadata,
            )
            self.ddl_collection = self.chroma_client.get_or_create_collection(
                name="ddl",
                embedding_function=self.embedding_function,
                metadata=collection_metadata,
            )
            self.sql_collection = self.chroma_client.get_or_create_collection(
                name="sql",
                embedding_function=self.embedding_function,
                metadata=collection_metadata,
            )

    def _reset_collections(self):
        """Limpa todas as coleções existentes"""
        try:
            self.chroma_client.delete_collection("documentation")
        except Exception:
            pass
        
        try:
            self.chroma_client.delete_collection("ddl")
        except Exception:
            pass
        
        try:
            self.chroma_client.delete_collection("sql")
        except Exception:
            pass

class MyVanna(ChromaDB_VectorStoreReset, GoogleGeminiChat):
    def __init__(self, config=None):
        if config is None:
            config = {}
        
        ChromaDB_VectorStoreReset.__init__(self, config=config)
        
        GEMINI_API_KEY = config.get('api_key')
        GEMINI_MODEL_NAME = config.get('model_name')
        
        GoogleGeminiChat.__init__(self, config={
            'api_key': GEMINI_API_KEY, 
            'model_name': GEMINI_MODEL_NAME
        })
        
        self.print_prompt = config.get('print_prompt', False)
        self.print_sql = config.get('print_sql', False)
        self.db_url = DB_URL

    def get_schema(self):
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
            """)
            tables = cursor.fetchall()

            schema = []
            for table in tables:
                table_name = table[0]

                cursor.execute("""
                    SELECT 
                        column_name,
                        data_type,
                        is_nullable,
                        column_default
                    FROM information_schema.columns
                    WHERE table_name = %s AND table_schema = 'public';
                """, (table_name,))
                columns = cursor.fetchall()

                cursor.execute("""
                    SELECT kcu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu 
                        ON tc.constraint_name = kcu.constraint_name
                    WHERE tc.table_name = %s 
                    AND tc.constraint_type = 'PRIMARY KEY'
                    AND tc.table_schema = 'public';
                """, (table_name,))
                pk_columns = {row[0] for row in cursor.fetchall()}

                create_stmt = f"CREATE TABLE {table_name} (\n"
                for i, col in enumerate(columns):
                    col_name, col_type, is_nullable, default = col
                    not_null = "NOT NULL" if is_nullable == "NO" else ""
                    is_pk = "PRIMARY KEY" if col_name in pk_columns else ""
                    default_str = f"DEFAULT {default}" if default else ""

                    parts = [col_name, col_type, default_str, not_null, is_pk]
                    col_def = "    " + " ".join(p for p in parts if p)

                    if i < len(columns) - 1:
                        col_def += ",\n"
                    else:
                        col_def += "\n"

                    create_stmt += col_def
                create_stmt += ");"
                schema.append(create_stmt)

            conn.close()
            return "\n\n".join(schema)
        except Exception as e:
            print(f"Erro ao obter esquema: {e}")
            return ""

    def connect_to_postgres(self, host, dbname, user, password, port):
        self.db_url = f'postgresql://{user}:{password}@{host}:{port}/{dbname}'
        self.schema = self.get_schema()

    def run_sql(self, sql):
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()
            cursor.execute(sql)
            result = cursor.fetchall()
            conn.close()
            return result
        except Exception as e:
            print(f"Erro ao executar SQL: {e}")
            return []


    def prepare(self):
        """
        Prepara o Vanna com treinamento inicial CORRIGIDO
        
        Args:
            force_retrain: Se True, força o retreinamento mesmo se já existir cache
        """
        
        # Conectar ao banco
        self.connect_to_postgres(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )

        
        print("[Vanna] → Iniciando treinamento (isso consome API quota)...")
        
        # =========================================================================
        # ETAPA 1: Treinar com DDL (estrutura real do banco)
        # =========================================================================
        print("[Vanna] 1/2 Treinando DDL...")
        self.train(ddl=self.get_schema())

        print("[Vanna] 2/2 Treinando SQL Examples e documentação...")
        self.train(sql=open("src/api/database/sql_examples.sql").read())

        self.train(documentation="""
            O banco contempla atividades de GitHub:

            - user_info: usuários
            - repository: repositórios
            - branch: branches dos repositórios
            - issue: issues criadas
            - pull_requests: PRs
            - commits: commits de usuários, podendo referenciar PRs
            - issue_assignees / pull_request_assignees: responsáveis
            - milestone: grupo de issues e PRs

            Consultas esperadas: ranking, agregações, contagem de atividades, obtenção de repositórios mais ativos e etc.

            """)
        


        