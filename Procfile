baileys: node services/whatsapp/baileys_service.js
web: uvicorn asgi:app --host 0.0.0.0 --port 5000 --ws websockets --lifespan off --workers 1 --timeout-keep-alive 75 --no-server-header