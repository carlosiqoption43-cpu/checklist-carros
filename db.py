import sqlite3
from config import DB_FILE

def get_conn():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS veiculos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        condutor TEXT,
        placa TEXT,
        modelo TEXT,
        data TEXT,
        quilometragem TEXT,
        observacoes TEXT,
        foto_carro TEXT,
        tipo TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS itens_checklist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        veiculo_id INTEGER,
        nome_item TEXT,
        status TEXT,
        comentario TEXT,
        caminho_foto TEXT,
        caminho_thumb TEXT,
        FOREIGN KEY (veiculo_id) REFERENCES veiculos(id)
    )
    """)
    # Índices para acelerar buscas e joins
    cur.execute("CREATE INDEX IF NOT EXISTS idx_veiculos_placa ON veiculos(placa)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_veiculos_condutor ON veiculos(condutor)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_veiculos_modelo ON veiculos(modelo)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_itens_veiculo ON itens_checklist(veiculo_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_itens_status ON itens_checklist(status)")
    conn.commit()
    conn.close()