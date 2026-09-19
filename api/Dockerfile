# ==
# Dockerfile (api)
# Author: Sunday Emmanuel Azeez
# ==
# Same approach as dashboard/Dockerfile: built from the project root,
# data is mounted in at runtime rather than copied into the image.

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt requirements.txt
COPY api/requirements.txt api-requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r api-requirements.txt

COPY api/ api/

EXPOSE 5050

ENV API_HOST=0.0.0.0
ENV API_PORT=5050

CMD ["python", "api/main.py"]
