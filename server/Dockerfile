# Self-hosted inference fallback (our model, no third-party AI API).
#   docker build -f server/Dockerfile -t produce-scanner-api .
#   docker run -p 8080:8080 -v $PWD/exports/v1:/model produce-scanner-api
FROM python:3.11-slim
WORKDIR /srv
COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt
COPY ml/__init__.py ml/__init__.py
COPY ml/common ml/common
COPY ml/evaluation/__init__.py ml/evaluation/calibration.py ml/evaluation/ood.py ml/evaluation/
COPY ml/inference ml/inference
COPY data/label_mapping.json data/label_mapping.json
COPY server server
ENV PRODUCE_BUNDLE=/model PRODUCE_THREADS=2
USER nobody
EXPOSE 8080
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
