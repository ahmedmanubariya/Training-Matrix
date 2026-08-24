FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV HOST=0.0.0.0
ENV PORT=5000
ENV FLASK_DEBUG=0
EXPOSE 5000
CMD ["gunicorn","--bind","0.0.0.0:5000","--workers","2","--timeout","60","app:app"]
