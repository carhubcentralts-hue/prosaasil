baileys: node services/whatsapp/baileys_service.js
web: uvicorn asgi:asgi_app --host 0.0.0.0 --port 5000 --ws websockets --lifespan off --timeout-keep-alive 75