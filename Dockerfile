FROM mcr.microsoft.com/playwright/python:v1.43.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

EXPOSE 8080

CMD gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 300
