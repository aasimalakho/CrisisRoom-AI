FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# QWEN_API_KEY etc. are passed in at runtime via -e flags or docker-compose env_file,
# never baked into the image.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
