# AI Chat Application

A full-stack AI chat application with LiteLLM gateway, response caching, automatic key failover, and multi-turn conversation support.

## 1. Live URLs

- **Frontend**: https://lyftrai-chat-frontend.onrender.com
- **Backend**: https://lyftrai-chat-backend.onrender.com
- **Health Check**: https://lyftrai-chat-backend.onrender.com/health

## 2. Run locally: with Docker and without

### With Docker (recommended)

Prerequisites: Docker, Docker Compose, make

1. Clone the repository
2. Copy `.env.example` to `.env` and fill in your Gemini API keys
3. Run:
```bash
make up
```
- Frontend: http://localhost:3000
- Backend: http://localhost:8000

To stop:
```bash
make down
```

### Without Docker

**Backend:**
```bash
cd backend
pip install -r requirements.txt
export LLM_API_KEYS=your_key1,your_key2
export DATABASE_URL=sqlite:///./app.db
export ALLOWED_ORIGINS=http://localhost:3000
export ENABLE_FAILURE_SIMULATION=true
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend:**
```bash
cd frontend
npm install
echo "VITE_API_URL=http://localhost:8000" > .env
npm run dev
```

## 3. Design decisions: key fallback, caching, SQLite session storage

### Key Fallback
The backend maintains a key pool loaded from `LLM_API_KEYS`. Each key gets an ID (`key_1`, `key_2`, ...) based on its position. When a request is made, keys are tried in order. If a key returns a 429 (rate limit), quota error, or 5xx server error, the system automatically tries the next key. The `fallback_attempts` field in the response shows how many keys failed before success.

This is implemented manually (not using LiteLLM's Router) to give precise control over which key succeeded and to properly report `key_id` and `fallback_attempts` in the response metadata. The service health check requires at least two configured keys.

### Caching
LiteLLM's built-in in-memory cache is used. The cache key is derived from the model name + the full message list (system prompt + conversation history + new message). This means:
- The same question asked with the same conversation context will return a cached response
- A cache hit is detected via `response._hidden_params.get('cache_hit')` 
- Cache hits report `resolution_source: "LLM_CACHE"`, `key_id: null`, and are significantly faster

The cache lives in-memory, so it resets on backend restart. For persistence, a disk cache under `/data/litellm_cache` could be used.

### SQLite Session Storage
Session history is stored in SQLite in a `messages` table. Each message records its `session_id`, `role`, `content`, optional `metadata` (JSON), and `created_at` timestamp. The database file is stored at `/data/app.db`. Docker Compose mounts a named volume locally so history survives container restarts. The selected Render free service has ephemeral storage, so hosted history resets when the service restarts or redeploys.

The schema is created automatically on startup. Using aiosqlite for async compatibility with FastAPI.

## 4. Verification: how to see failover, cache hits and per-message token usage

### Cache Hit
1. Send a message: "What is the capital of France?"
2. Open a new session and send the same first message again. The cache key includes the full message list, so reusing a session after its history changes is a different request.
3. The second response shows `resolution_source: LLM_CACHE` and much lower latency

### Failover with X-Simulate-Failure
Test key_1 failing over to key_2:
```bash
curl -X POST https://lyftrai-chat-backend.onrender.com/chat \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: key_1=429" \
  -d '{"session_id": "test-1", "message": "Hello"}'
# Response: key_id = "key_2", fallback_attempts = 1
```

Test all keys failing:
```bash
curl -X POST https://lyftrai-chat-backend.onrender.com/chat \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: *=429" \
  -d '{"session_id": "test-2", "message": "Hello"}'
# Response: 503 {"detail": "all providers unavailable"}
```

The supported simulated statuses are `429`, `500`, `502`, and `503`. A failed request is not written to session history.

### Per-Message Token Usage
Every response includes `input_tokens` and `output_tokens`. These are per-request values (not cumulative). Two identical first messages in separate sessions will report approximately the same token counts.

### Health Check
```bash
curl https://lyftrai-chat-backend.onrender.com/health
# {"status": "ok", "keys_configured": 2, "cache_enabled": true}
```

### Session history

```bash
curl https://lyftrai-chat-backend.onrender.com/sessions/test-1/messages
```

The endpoint returns user and assistant messages oldest first. Unknown sessions return `404` with a JSON `detail` field.

## 5. Setup Used: your editor and AI tools

- **Editor**: VS Code with GitHub Copilot
- **AI Tools**: Antigravity (Google DeepMind) for code generation and architecture guidance
- **LLM Integration**: LiteLLM for unified API access, caching, and fallback
- **Models**: Google Gemini 2.0 Flash

## 6. Bonus features

- **Failure simulation hook**: The `X-Simulate-Failure` header can be used from any API client to demonstrate failover without consuming provider quota.
- **Session persistence display**: Session ID shown in UI so users can share/restore conversations
- **Cache hit visual indicator**: Cache hits highlighted differently in the UI for clear visual feedback
- **System prompt override**: Per-session system prompt configuration
