FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend ./backend
COPY frontend ./frontend
EXPOSE 3001 3002 3003 3004 3005

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "3001"]
