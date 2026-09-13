FROM python:3.11-slim

# ffmpeg: dựng video/âm thanh. fonts-dejavu-core: font chữ cho thumbnail nháp.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

RUN mkdir -p jobs

ENV PORT=8000
EXPOSE 8000

CMD ["python", "app.py"]
