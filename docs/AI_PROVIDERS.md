# AI Providers

KUKANILEA nutzt einen Provider-Router, der mehrere LLM-Backends priorisiert ansteuern kann.

## Unterstützte Provider (Phase 6.1)

- `ollama` (lokal)
- `vllm` (lokal, OpenAI-kompatibel)
- `lmstudio` (lokal, OpenAI-kompatibel)
- `groq` (cloud, OpenAI-kompatibel)
- `anthropic` (cloud)
- `gemini` (cloud)
- `openai_compat` (generischer OpenAI-kompatibler Endpoint)
- `openai_compat_fallback` (sekundärer generischer Endpoint)

## Empfohlene Reihenfolge

```bash
export KUKANILEA_AI_PROVIDER_ORDER="vllm,lmstudio,ollama,groq,anthropic,gemini"
```

## Lokale Provider

### vLLM

```bash
export KUKANILEA_VLLM_BASE_URL="http://127.0.0.1:8000"
export KUKANILEA_VLLM_MODEL="meta-llama/Llama-3.1-8B-Instruct"
export KUKANILEA_VLLM_TIMEOUT=60
```

### LM Studio

```bash
export KUKANILEA_LMSTUDIO_BASE_URL="http://127.0.0.1:1234"
export KUKANILEA_LMSTUDIO_MODEL="local-model"
export KUKANILEA_LMSTUDIO_TIMEOUT=60
```

### Ollama

```bash
export OLLAMA_BASE_URL="http://127.0.0.1:11434"
export OLLAMA_MODEL="llama3.2:3b"
export KUKANILEA_OLLAMA_MODEL_FALLBACKS="llama3.1:8b,qwen2.5:3b"
export OLLAMA_TIMEOUT=300
```

Hinweis: Bei `OllamaProviderClient` wird lokal modellweise gefailovert (z. B. wenn ein Modell
nicht installiert ist), bevor auf den naechsten Provider gewechselt wird.
Ohne eigene Konfiguration nutzt KUKANILEA als Fallback standardmaessig:
`llama3.2:3b,qwen2.5:3b`.

Zusatz fuer Erstinstallation:
- `KUKANILEA_AI_BOOTSTRAP_ON_FIRST_RUN=1`
- `KUKANILEA_AI_BOOTSTRAP_PULL_MODELS=1`
- Optional feste Liste: `KUKANILEA_AI_BOOTSTRAP_MODEL_LIST="llama3.2:3b,llama3.1:8b"`

## Cloud-Fallback (Groq)

```bash
export KUKANILEA_GROQ_BASE_URL="https://api.groq.com/openai/v1"
export KUKANILEA_GROQ_MODEL="llama-3.3-70b-versatile"
export GROQ_API_KEY="..."
export KUKANILEA_GROQ_TIMEOUT=30
```

## Cloud-Provider: Anthropic

```bash
export KUKANILEA_ANTHROPIC_BASE_URL="https://api.anthropic.com"
export KUKANILEA_ANTHROPIC_MODEL="claude-3-5-sonnet-latest"
export ANTHROPIC_API_KEY="..."
export KUKANILEA_ANTHROPIC_TIMEOUT=60
```

## Cloud-Provider: Gemini

```bash
export KUKANILEA_GEMINI_BASE_URL="https://generativelanguage.googleapis.com"
export KUKANILEA_GEMINI_MODEL="gemini-1.5-flash"
export GEMINI_API_KEY="..."
export KUKANILEA_GEMINI_TIMEOUT=60
```

## Alternative: volle Liste als JSON

Wenn `KUKANILEA_AI_PROVIDERS_JSON` gesetzt ist, hat es Vorrang vor `KUKANILEA_AI_PROVIDER_ORDER`.

```bash
export KUKANILEA_AI_PROVIDERS_JSON='[
  {"type":"vllm","priority":1,"base_url":"http://127.0.0.1:8000","model":"meta-llama/Llama-3.1-8B-Instruct","timeout_s":60},
  {"type":"lmstudio","priority":2,"base_url":"http://127.0.0.1:1234","model":"local-model","timeout_s":60},
  {"type":"groq","priority":3,"base_url":"https://api.groq.com/openai/v1","model":"llama-3.3-70b-versatile","api_key":"${GROQ_API_KEY}","timeout_s":30}
]'
```

## Retry/Health-Cache

```bash
export KUKANILEA_AI_PROVIDER_RETRIES=1
export KUKANILEA_AI_HEALTH_TTL_SECONDS=30
```

## Policy pro Tenant/Rolle (serverseitig)

`KUKANILEA_AI_PROVIDER_POLICY_JSON` erlaubt Mandanten-/Rollensteuerung.

Beispiel: OFFICE darf nur lokale Provider, SUPPORT nur vLLM.

```bash
export KUKANILEA_AI_PROVIDER_POLICY_JSON='{
  "default": {
    "allow_local": true,
    "allow_cloud": true
  },
  "roles": {
    "OFFICE": { "allow_cloud": false },
    "SUPPORT": { "allow_providers": ["vllm"] }
  },
  "tenants": {
    "KUKANILEA": { "deny_providers": ["groq"] }
  }
}'
```

Unterstuetzte Rule-Keys:
- `allow_providers` (Liste)
- `deny_providers` (Liste)
- `allow_local` (bool)
- `allow_cloud` (bool)
- `allowed_roles` (Liste)
- `blocked_roles` (Liste)

## Hinweise

- Keine neuen Runtime-Dependencies in Phase 6.1.
- Anthropic/Gemini folgen als separate Adapter in einem Folgeschritt.
