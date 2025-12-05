from models import User
from db import get_conn
import sys

def create_admin_user():
    # Verificar se o usuário já existe
    admin = User.find_by_username("vip")
    
    if admin:
        print("Usuário 'vip' já existe no banco de dados.")
        sys.exit(0)
    
    # Criar o usuário administrador
    try:
        admin = User.create(
            username="vip",
            password="vip123",
            email="vip@example.com",
            is_admin=True
        )
        print("Usuário administrador criado com sucesso!")
        print(f"Usuário: vip")
        print(f"Senha: vip123")
        print("\nPor favor, altere a senha após o primeiro login!")
    except Exception as e:
        print(f"Erro ao criar usuário administrador: {e}")
        sys.exit(1)

if __name__ == "__main__":
    create_admin_user()
