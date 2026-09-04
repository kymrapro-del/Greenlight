# GREENLIGHT — l'API de clearance.
#
# Cible : Cloud Run. L'image est mince parce que le service est mince : le
# pipeline est du Python et deux SDK, il n'y a ni base de données ni build
# frontend ici. L'interface est servie à part.
#
#   gcloud run deploy greenlight \
#     --source . --region europe-west1 --allow-unauthenticated \
#     --set-env-vars GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=$PROJECT,FIXTURE_MODE=live \
#     --set-secrets PARALLEL_API_KEY=parallel-api-key:latest
#
# `min-instances` reste à 0 : une instance allumée en permanence est facturée en
# continu et sort du free tier. À passer à 1 la veille du jugement seulement,
# pour épargner un démarrage à froid aux juges.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Les dépendances d'abord : elles changent rarement, et cette couche est
# réutilisée à chaque build tant que le fichier ne bouge pas.
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/greenlight ./backend/greenlight
COPY samples ./samples
COPY fixtures ./fixtures
COPY pyproject.toml ./

ENV PYTHONPATH=/app/backend \
    PORT=8080

EXPOSE 8080

# Un seul worker : les passes gardées en mémoire ne sont pas partagées entre
# processus, et le pipeline parallélise déjà ses propres appels. Plusieurs
# workers rendraient un `runId` introuvable une requête sur deux.
CMD exec uvicorn greenlight.api.server:app --host 0.0.0.0 --port ${PORT} --workers 1
