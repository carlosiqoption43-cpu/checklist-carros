# Imagem base oficial do Python
FROM python:3.11-slim

# Definir diretório de trabalho
WORKDIR /app

# Copiar dependências e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o restante do código
COPY . .

# Comando para rodar a aplicação Flask com Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]