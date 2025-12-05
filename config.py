import os
import sys
from datetime import timedelta

# Configurações do aplicativo
APP_ROOT = os.path.abspath(os.path.dirname(__file__))
SECRET_KEY = os.environ.get('SECRET_KEY') or 'sua-chave-secreta-aqui'

# Configurações do banco de dados
DATA_DIR = os.path.join(APP_ROOT, "data")
APP_DIR = os.path.join(DATA_DIR, "ChecklistVeicular")
ANEXOS_DIR = os.path.join(APP_DIR, "anexos")
DB_FILE = os.path.join(APP_DIR, "checklist.db")

# Configurações de e-mail (para recuperação de senha)
MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@checklistveicular.com')

# Configurações de segurança
PASSWORD_RESET_EXPIRATION = timedelta(hours=24)  # Tempo de expiração do token de redefinição

# Criar diretórios necessários
os.makedirs(APP_DIR, exist_ok=True)
os.makedirs(ANEXOS_DIR, exist_ok=True)