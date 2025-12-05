from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_conn

class User(UserMixin):
    def __init__(self, id, username, password_hash, email=None, is_admin=False, reset_token=None, reset_token_expiration=None):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.email = email
        self.is_admin = is_admin
        self.reset_token = reset_token
        self.reset_token_expiration = reset_token_expiration

    @staticmethod
    def get(user_id):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username, password_hash, email, is_admin, 
                   reset_token, reset_token_expiration 
            FROM users WHERE id = ?
        """, (user_id,))
        user_data = cur.fetchone()
        if not user_data:
            return None
        return User(
            id=user_data[0],
            username=user_data[1],
            password_hash=user_data[2],
            email=user_data[3],
            is_admin=bool(user_data[4]),
            reset_token=user_data[5],
            reset_token_expiration=user_data[6]
        )

    @staticmethod
    def find_by_username(username):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username, password_hash, email, is_admin, 
                   reset_token, reset_token_expiration 
            FROM users WHERE username = ?
        """, (username,))
        user_data = cur.fetchone()
        if not user_data:
            return None
        return User(
            id=user_data[0],
            username=user_data[1],
            password_hash=user_data[2],
            email=user_data[3],
            is_admin=bool(user_data[4]),
            reset_token=user_data[5],
            reset_token_expiration=user_data[6]
        )

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def create(username, password, email=None, is_admin=False):
        conn = get_conn()
        cur = conn.cursor()
        password_hash = generate_password_hash(password)
        cur.execute(
            """
            INSERT INTO users (username, password_hash, email, is_admin) 
            VALUES (?, ?, ?, ?)
            """,
            (username, password_hash, email, 1 if is_admin else 0)
        )
        conn.commit()
        return User(cur.lastrowid, username, password_hash, email, is_admin)
        
    def update_profile(self, username=None, email=None, new_password=None):
        conn = get_conn()
        cur = conn.cursor()
        
        if new_password:
            self.password_hash = generate_password_hash(new_password)
            
        if username:
            self.username = username
            
        if email is not None:  # Permite definir email como vazio
            self.email = email
            
        cur.execute("""
            UPDATE users 
            SET username = ?, password_hash = ?, email = ?
            WHERE id = ?
        """, (self.username, self.password_hash, self.email, self.id))
        
        conn.commit()
        return True
        
    def set_reset_token(self, token, expiration):
        conn = get_conn()
        cur = conn.cursor()
        self.reset_token = token
        self.reset_token_expiration = expiration
        
        cur.execute("""
            UPDATE users 
            SET reset_token = ?, reset_token_expiration = ?
            WHERE id = ?
        """, (token, expiration, self.id))
        
        conn.commit()
        
    @staticmethod
    def verify_reset_token(token):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username, password_hash, email, is_admin,
                   reset_token, reset_token_expiration 
            FROM users 
            WHERE reset_token = ? AND reset_token_expiration > datetime('now')
        """, (token,))
        
        user_data = cur.fetchone()
        if not user_data:
            return None
            
        return User(
            id=user_data[0],
            username=user_data[1],
            password_hash=user_data[2],
            email=user_data[3],
            is_admin=bool(user_data[4]),
            reset_token=user_data[5],
            reset_token_expiration=user_data[6]
        )
        
    def set_password(self, new_password):
        self.password_hash = generate_password_hash(new_password)
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE users 
            SET password_hash = ?, reset_token = NULL, reset_token_expiration = NULL
            WHERE id = ?
        """, (self.password_hash, self.id))
        
        conn.commit()
        return True


class Manutencao:
    def __init__(self, id, veiculo_id, nome_peca, data_manutencao, quilometragem_atual, 
                 vida_util_km=None, proxima_manutencao_km=None, valor_peca=None, 
                 mao_de_obra=None, observacoes=None, created_at=None):
        self.id = id
        self.veiculo_id = veiculo_id
        self.nome_peca = nome_peca
        self.data_manutencao = data_manutencao
        self.quilometragem_atual = quilometragem_atual
        self.vida_util_km = vida_util_km
        self.proxima_manutencao_km = proxima_manutencao_km
        self.valor_peca = valor_peca
        self.mao_de_obra = mao_de_obra
        self.observacoes = observacoes
        self.created_at = created_at

    @staticmethod
    def create(veiculo_id, nome_peca, data_manutencao, quilometragem_atual, 
               vida_util_km=None, proxima_manutencao_km=None, valor_peca=None, 
               mao_de_obra=None, observacoes=None):
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO manutencao 
            (veiculo_id, nome_peca, data_manutencao, quilometragem_atual, 
             vida_util_km, proxima_manutencao_km, valor_peca, mao_de_obra, observacoes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (veiculo_id, nome_peca, data_manutencao, quilometragem_atual, 
              vida_util_km, proxima_manutencao_km, valor_peca, mao_de_obra, observacoes))
        
        conn.commit()
        return Manutencao(cur.lastrowid, veiculo_id, nome_peca, data_manutencao, 
                         quilometragem_atual, vida_util_km, proxima_manutencao_km, 
                         valor_peca, mao_de_obra, observacoes)

    @staticmethod
    def get_by_veiculo(veiculo_id):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, veiculo_id, nome_peca, data_manutencao, quilometragem_atual,
                   vida_util_km, proxima_manutencao_km, valor_peca, mao_de_obra, 
                   observacoes, created_at
            FROM manutencao 
            WHERE veiculo_id = ?
            ORDER BY data_manutencao DESC
        """, (veiculo_id,))
        
        rows = cur.fetchall()
        manutencoes = []
        for row in rows:
            manutencoes.append(Manutencao(*row))
        
        return manutencoes

    @staticmethod
    def get_by_id(manutencao_id):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, veiculo_id, nome_peca, data_manutencao, quilometragem_atual,
                   vida_util_km, proxima_manutencao_km, valor_peca, mao_de_obra, 
                   observacoes, created_at
            FROM manutencao 
            WHERE id = ?
        """, (manutencao_id,))
        
        row = cur.fetchone()
        if row:
            return Manutencao(*row)
        return None

    def update(self):
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE manutencao 
            SET nome_peca = ?, data_manutencao = ?, quilometragem_atual = ?,
                vida_util_km = ?, proxima_manutencao_km = ?, valor_peca = ?,
                mao_de_obra = ?, observacoes = ?
            WHERE id = ?
        """, (self.nome_peca, self.data_manutencao, self.quilometragem_atual,
              self.vida_util_km, self.proxima_manutencao_km, self.valor_peca,
              self.mao_de_obra, self.observacoes, self.id))
        
        conn.commit()
        return True

    def delete(self):
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("DELETE FROM manutencao WHERE id = ?", (self.id,))
        conn.commit()
        return True

    @staticmethod
    def get_all():
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT m.id, m.veiculo_id, m.nome_peca, m.data_manutencao, m.quilometragem_atual,
                   m.vida_util_km, m.proxima_manutencao_km, m.valor_peca, m.mao_de_obra, 
                   m.observacoes, m.created_at, v.placa, v.modelo, v.condutor
            FROM manutencao m
            JOIN veiculos v ON m.veiculo_id = v.id
            ORDER BY m.data_manutencao DESC
        """)
        
        rows = cur.fetchall()
        manutencoes = []
        for row in rows:
            manutencao = Manutencao(row[0], row[1], row[2], row[3], row[4], 
                                   row[5], row[6], row[7], row[8], row[9], row[10])
            manutencao.veiculo_placa = row[11]
            manutencao.veiculo_modelo = row[12]
            manutencao.veiculo_condutor = row[13]
            manutencoes.append(manutencao)
        
        return manutencoes

    @property
    def custo_total(self):
        if self.valor_peca and self.mao_de_obra:
            return self.valor_peca + self.mao_de_obra
        elif self.valor_peca:
            return self.valor_peca
        elif self.mao_de_obra:
            return self.mao_de_obra
        return 0.0
