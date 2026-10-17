FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# Tesseract with French, English and Arabic for OCR of scanned PDF pages; gettext for translations.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng tesseract-ocr-ara gettext \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Free offline translator (CPU-only PyTorch keeps the image small).
COPY requirements-translate.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements-translate.txt

COPY . .
RUN DJANGO_SECRET_KEY=build-only python manage.py compilemessages \
 && DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput

RUN useradd --create-home --uid 1000 app && mkdir -p /data/media && chown -R app /data /app
USER app
RUN DJANGO_SECRET_KEY=build-only python manage.py install_translation_models

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", "--access-logfile", "-"]
