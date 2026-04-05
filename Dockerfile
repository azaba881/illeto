FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=core.settings

# GeoDjango (GDAL/GEOS/PROJ) + dépendances navigateur Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    binutils \
    libproj25 libproj-dev \
    gdal-bin libgdal-dev \
    libgeos-c1v5 libgeos-dev \
    wget gnupg \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxext6 libxfixes3 libxrandr2 libgbm1 libasound2 \
    libpango-1.0-0 libcairo2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install-deps chromium
RUN playwright install chromium

COPY . .

# Fichiers statiques (Atlas, admin CSS, etc.)
ARG SECRET_KEY_BUILD=collectstatic-build-only
RUN SECRET_KEY="${SECRET_KEY_BUILD}" python manage.py collectstatic --noinput

# Render injecte PORT ; 10000 reste le repli local / render.yaml
CMD ["sh", "-c", "gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-10000}"]