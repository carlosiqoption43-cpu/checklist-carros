import os, sys

APP_ROOT = os.path.abspath(os.path.dirname(__file__))
# Pasta de dados local (padrão: ./data)
DATA_DIR = os.path.join(APP_ROOT, "data")
APP_DIR = os.path.join(DATA_DIR, "ChecklistVeicular")
ANEXOS_DIR = os.path.join(APP_DIR, "anexos")
DB_FILE = os.path.join(APP_DIR, "checklist.db")

os.makedirs(APP_DIR, exist_ok=True)
os.makedirs(ANEXOS_DIR, exist_ok=True)