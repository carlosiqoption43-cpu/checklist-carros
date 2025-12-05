import sqlite3
import os
from config import DB_FILE

def migrate_database():
    print(f"Conectando ao banco de dados: {DB_FILE}")
    
    # Verificar se o diretório do banco de dados existe
    db_dir = os.path.dirname(DB_FILE)
    if db_dir and not os.path.exists(db_dir):
        print(f"Criando diretório: {db_dir}")
        os.makedirs(db_dir, exist_ok=True)
    
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    
    # Verificar se a tabela users existe
    cur.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='users'
    """)
    
    if not cur.fetchone():
        print("Criando tabela 'users'...")
        cur.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT,
                is_admin BOOLEAN DEFAULT 0,
                reset_token TEXT,
                reset_token_expiration TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("Tabela 'users' criada com sucesso!")
    else:
        print("Tabela 'users' já existe. Verificando colunas...")
        
        # Obter colunas existentes
        cur.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cur.fetchall()]
        
        # Lista de colunas necessárias e seus tipos
        required_columns = [
            ("email", "TEXT"),
            ("reset_token", "TEXT"),
            ("reset_token_expiration", "TIMESTAMP"),
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        ]
        
        # Adicionar colunas ausentes
        for column, column_type in required_columns:
            if column not in columns:
                print(f"Adicionando coluna '{column}'...")
                try:
                    cur.execute(f"ALTER TABLE users ADD COLUMN {column} {column_type}")
                    print(f"Coluna '{column}' adicionada com sucesso!")
                except sqlite3.OperationalError as e:
                    print(f"Erro ao adicionar coluna '{column}': {e}")
    
    conn.commit()
    conn.close()
    print("Migração concluída com sucesso!")

if __name__ == "__main__":
    migrate_database()
