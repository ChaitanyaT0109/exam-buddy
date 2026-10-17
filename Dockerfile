FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY exam_buddy ./exam_buddy
COPY web ./web
COPY notes ./notes

# Set SARVAM_API_KEY (and the optional INDUS_* values) in your host's settings, never in this file.
ENV PORT=8200
EXPOSE 8200
CMD ["sh", "-c", "uvicorn exam_buddy.server:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
