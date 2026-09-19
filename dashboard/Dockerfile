# ==
# Dockerfile (dashboard)
# Author: Sunday Emmanuel Azeez
# ==
# Built with the project root as the build context (see
# docker-compose.yml), so it can reach both the root requirements.txt
# and the dashboard's own. The actual data, cleaned_data/, outputs/,
# raw_data/, is not copied into the image, it's mounted in as a volume
# at runtime, so rebuilding the image is never needed just because the
# pipeline produced new numbers.

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt requirements.txt
COPY dashboard/requirements.txt dashboard-requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r dashboard-requirements.txt

COPY dashboard/ dashboard/

EXPOSE 8501

CMD ["streamlit", "run", "dashboard/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
