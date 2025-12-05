import sqlite3
import os
from config import DB_FILE

def migrate_manutencao():
    print(f"Conectando ao banco de dados: {DB_FILE}")
    
    # Verificar se o diretório do banco de dados existe
    db_dir = os.path.dirname(DB_FILE)
    if db_dir and not os.path.exists(db_dir):
        print(f"Criando diretório: {db_dir}")
        os.makedirs(db_dir, exist_ok=True)
    
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    
    # Verificar se a tabela manutencao existe
    cur.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='manutencao'
    """)
    
    if not cur.fetchone():
        print("Criando tabela 'manutencao'...")
        cur.execute("""
            CREATE TABLE manutencao (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                veiculo_id INTEGER NOT NULL,
                nome_peca TEXT NOT NULL,
                data_manutencao TEXT NOT NULL,
                quilometragem_atual TEXT NOT NULL,
                vida_util_km INTEGER,
                proxima_manutencao_km INTEGER,
                valor_peca REAL,
                mao_de_obra REAL,
                observacoes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (veiculo_id) REFERENCES veiculos(id)
            )
        """)
        print("Tabela 'manutencao' criada com sucesso!")
        
        # Criar índices para melhorar performance
        cur.execute("CREATE INDEX IF NOT EXISTS idx_manutencao_veiculo ON manutencao(veiculo_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_manutencao_data ON manutencao(data_manutencao)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_manutencao_peca ON manutencao(nome_peca)")
        print("Índices criados com sucesso!")
    else:
        print("Tabela 'manutencao' já existe.")
        
        # Verificar se as colunas necessárias existem
        cur.execute("PRAGMA table_info(manutencao)")
        columns = [column[1] for column in cur.fetchall()]
        
        # Lista de colunas necessárias e seus tipos
        required_columns = [
            ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
            ("veiculo_id", "INTEGER NOT NULL"),
            ("nome_peca", "TEXT NOT NULL"),
            ("data_manutencao", "TEXT NOT NULL"),
            ("quilometragem_atual", "TEXT NOT NULL"),
            ("vida_util_km", "INTEGER"),
            ("proxima_manutencao_km", "INTEGER"),
            ("valor_peca", "REAL"),
            ("mao_de_obra", "REAL"),
            ("observacoes", "TEXT"),
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        ]
        
        # Adicionar colunas ausentes se necessário
        for column, column_type in required_columns:
            if column not in columns:
                print(f"Adicionando coluna '{column}'...")
                try:
                    cur.execute(f"ALTER TABLE manutencao ADD COLUMN {column} {column_type}")
                    print(f"Coluna '{column}' adicionada com sucesso!")
                except sqlite3.OperationalError as e:
                    print(f"Erro ao adicionar coluna '{column}': {e}")
    
    conn.commit()
    conn.close()
    print("Migração da tabela de manutenção concluída com sucesso!")

if __name__ == "__main__":
    migrate_manutencao()
