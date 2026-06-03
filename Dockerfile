FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY compiler/ compiler/
COPY frontend/ frontend/

EXPOSE 8000

CMD ["uvicorn", "compiler.main:app", "--host", "0.0.0.0", "--port", "8000"]
