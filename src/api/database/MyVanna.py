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
        self.connect_to_postgres(
            host = DB_HOST,
            port = DB_PORT,
            dbname = DB_NAME,
            user = DB_USER,
            password = DB_PASSWORD
        )

        self.train(ddl=self.get_schema())

        self.train(documentation="""
Table: user_info

    id: Bigint primary key with default value from sequence

    login: Required username field (character varying)

    html_url: Required profile URL field (text)

Table: milestone

    id: Bigint primary key with default value from sequence

    repository_id: Associated repository ID (integer, required)

    title: Milestone title (text, required)

    description: Milestone description (text, optional)

    number: Milestone number (integer, required)

    state: Milestone state (character varying, required)

    created_at: Creation timestamp with time zone

    updated_at: Update timestamp with time zone

    creator: Creator user ID (bigint, required)

Table: repository

    id: Integer primary key with default value from sequence

    name: Repository name (character varying, required)

Table: branch

    id: Bigint primary key with default value from sequence

    name: Branch name (character varying, required)

    repository_id: Associated repository ID (integer, required)

Table: issue

    id: Bigint primary key with default value from sequence

    title: Issue title (text, required)

    body: Issue body/description (text, optional)

    number: Issue number (integer, required)

    html_url: Issue URL (text, optional)

    created_at: Creation timestamp with time zone

    updated_at: Update timestamp with time zone

    created_by: Creator user ID (bigint, required)

    repository_id: Associated repository ID (bigint, required)

    milestone_id: Associated milestone ID (bigint, optional)

Table: pull_requests

    id: Bigint primary key with default value from sequence

    created_by: Creator user ID (bigint, required)

    repository_id: Associated repository ID (integer, required)

    number: Pull request number (integer, required)

    state: Pull request state (character varying, required)

    title: Pull request title (text, required)

    body: Pull request body/description (text, optional)

    html_url: Pull request URL (text, required)

    created_at: Creation timestamp with time zone

    updated_at: Update timestamp with time zone

    milestone_id: Associated milestone ID (bigint, optional)

Table: commits

    id: Bigint primary key with default value from sequence

    user_id: Author user ID (bigint, required)

    branch_id: Associated branch ID (integer, optional)

    pull_request_id: Associated pull request ID (bigint, optional)

    created_at: Creation timestamp with time zone

    message: Commit message (text, required)

    sha: Commit SHA hash (character varying, required)

    html_url: Commit URL (text, optional)

Table: parents_commits

    id: Integer primary key with default value from sequence

    parent_sha: Parent commit SHA hash (character varying, required)

    commit_id: Child commit ID (integer, required)

Table: issue_assignees

    issue_id: Issue ID (bigint, required, part of primary key)

    user_id: Assigned user ID (bigint, required, part of primary key)

Table: pull_request_assignees

    pull_request_id: Pull request ID (bigint, required, part of primary key)

    user_id: Assigned user ID (bigint, required, part of primary key)
        """)
        
        self.train(sql="""
        -- 1. Repositórios com mais issues abertas
        SELECT
            r.name AS repositorio,
            COUNT(*) AS total_issues_abertas,
            MAX(i.created_at) AS data_ultima_issue
        FROM
            issue i
        JOIN
            repository r ON i.repository_id = r.id
        WHERE
            i.state = 'open'
        GROUP BY
            r.name
        ORDER BY
            total_issues_abertas DESC
        LIMIT 10;
        """)

        self.train(sql="""
        -- 2. Top 5 usuários com mais commits registrados
        SELECT
            u.login,
            COUNT(*) AS total_commits
        FROM
            commits c
        JOIN
            user_info u ON c.user_id = u.id
        GROUP BY
            u.login
        ORDER BY
            total_commits DESC
        LIMIT 5;
        """)

        self.train(sql="""
        -- 3. Total de pull requests abertos por repositório
        SELECT
            r.name AS repositorio,
            COUNT(*) AS total_pr_abertos
        FROM
            pull_requests pr
        JOIN
            repository r ON pr.repository_id = r.id
        WHERE
            pr.state = 'open'
        GROUP BY
            r.name
        ORDER BY
            total_pr_abertos DESC;
        """)

        self.train(sql="""
        -- 4. Número de issues por milestone
        SELECT
            m.title AS milestone,
            COUNT(*) AS total_issues
        FROM
            issue i
        JOIN
            milestone m ON i.milestone_id = m.id
        GROUP BY
            m.title
        ORDER BY
            total_issues DESC;
        """)

        self.train(sql="""
        -- 5. Commits feitos por branch
        SELECT
            b.name AS branch,
            COUNT(*) AS total_commits
        FROM
            commits c
        JOIN
            branch b ON c.branch_id = b.id
        GROUP BY
            b.name
        ORDER BY
            total_commits DESC;
        """)


