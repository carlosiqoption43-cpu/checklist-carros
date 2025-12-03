FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expor a porta 5000 (a mesma usada pelo Flask)
EXPOSE 5000

# Rodar a aplicação Flask com Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]