# ==
# Dockerfile (shopify_sync webhook listener)
# Same approach as api/Dockerfile and dashboard/Dockerfile: built from
# the project root, .env values come from real environment variables
# set on the host (Render), not copied into the image.
# ==

FROM python:3.12-slim

WORKDIR /app

COPY shopify_sync/requirements.txt shopify_sync-requirements.txt
RUN pip install --no-cache-dir -r shopify_sync-requirements.txt

COPY shopify_sync/ shopify_sync/

EXPOSE 5051

CMD ["python", "shopify_sync/webhook_listener.py"]
