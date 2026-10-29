# Imagen para desplegar "Bazilio: palabras a música" en internet (Render, Railway, etc.)
FROM python:3.12-slim

# LilyPond (PDF y MIDI), ffmpeg (MP3) y Java (para ANTLR). El WAV lo genera Python.
RUN apt-get update && apt-get install -y --no-install-recommends \
        lilypond ffmpeg default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# genera BazilioLexer.py, BazilioParser.py y BazilioVisitor.py dentro de la imagen
RUN antlr4 -v 4.13.2 -Dlanguage=Python3 -visitor Bazilio.g4

ENV PORT=10000
EXPOSE 10000
CMD ["python", "servidor.py"]
