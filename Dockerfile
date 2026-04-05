FROM python:3.11-slim

# Dépendances système pour Playwright
RUN apt-get update && apt-get install -y \
    wget gnupg libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxext6 libxfixes3 libxrandr2 libgbm1 libasound2 \
    libpango-1.0-0 libcairo2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

# Installation des libs Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Installation de Chromium pour les exports PDF
RUN playwright install chromium
RUN playwright install-deps chromium

COPY . .

# Port par défaut de Render
CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:10000"]