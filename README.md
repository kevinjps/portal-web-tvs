# 📺 Signal — Local Signage (FastAPI + Docker)

Portal de exibição de vídeos em TVs via rede local.

## 🚀 Como usar

### Subir com Docker Compose
```bash
docker compose up --build
```

> Na primeira vez faz o build da imagem. Nas próximas, só `docker compose up`.

### Acessar

| Tela | URL |
|------|-----|
| **Painel Admin** | http://localhost:8000/admin |
| **Player da TV** | http://localhost:8000/tv |

### Na TV
Abra o navegador e acesse com o IP do computador host:
```
http://[SEU_IP]:8000/tv
```
> Windows: `ipconfig` — Mac/Linux: `ifconfig` ou `ip a`

---

## 📁 Estrutura

```
signage/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── uploads/              ← vídeos salvos aqui (persistente via volume)
└── app/
    ├── main.py           ← API FastAPI + WebSocket
    └── static/
        ├── admin.html    ← painel de administração
        └── tv.html       ← player para a TV
```

## 🔌 Endpoints da API

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/videos` | Lista vídeos |
| POST | `/api/upload` | Upload de vídeo |
| DELETE | `/api/videos/{filename}` | Remove vídeo |
| GET | `/api/state` | Estado atual da TV |
| POST | `/api/control` | Controla a TV |
| WS | `/ws` | WebSocket em tempo real |

## ⚙️ Desenvolvimento (hot reload)

```bash
docker compose up
```

O volume `./app:/app/app` no compose já monta o código ao vivo.
Para hot reload completo, altere o CMD do Dockerfile para:
```
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```
