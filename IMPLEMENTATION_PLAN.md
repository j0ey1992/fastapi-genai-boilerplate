# RAG Policy Assistant - Implementation Plan

**Project:** Voyage AI Policy Assistant
**Stack:** FastAPI + Google Gemini + Qdrant + PostgreSQL
**Deployment:** Railway
**Timeline:** Follow phases sequentially

---

## Phase 0: Setup & Dependencies

### Step 1: Install Vector Database & AI Dependencies
- [ ] Add `google-genai>=1.0.0` to `pyproject.toml` dependencies
- [ ] Add `qdrant-client>=1.7.0` to `pyproject.toml` dependencies
- [ ] Run `poetry install` or `pip install -e .`
- [ ] Get Gemini API key from https://aistudio.google.com/apikey
- [ ] Sign up for Qdrant Cloud at https://cloud.qdrant.io/ (free tier)
- [ ] Create new cluster and get API URL + API key

**Environment Variables to Add:**
```bash
GEMINI_API_KEY=your_gemini_key_here
QDRANT_URL=https://xxx.qdrant.io
QDRANT_API_KEY=your_qdrant_key_here
```

---

### Step 2: Install PDF Processing Dependencies
- [ ] Add `pypdf>=4.0.0` to `pyproject.toml` dependencies
- [ ] Add `pdfplumber>=0.11.0` to `pyproject.toml` dependencies
- [ ] Add `python-multipart>=0.0.9` (for file uploads) to dependencies
- [ ] Run `poetry install` or `pip install -e .`

---

### Step 3: Install Database Dependencies
- [ ] Add `sqlalchemy>=2.0.0` to `pyproject.toml` dependencies
- [ ] Add `asyncpg>=0.29.0` to `pyproject.toml` dependencies
- [ ] Add `alembic>=1.13.0` to `pyproject.toml` dependencies
- [ ] Run `poetry install` or `pip install -e .`

**Environment Variables to Add:**
```bash
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/voyage_policies
```

---

## Phase 1: Core Infrastructure Setup

### Step 4: Configure Qdrant Client
- [ ] Open `app/core/config.py`
- [ ] Add Qdrant configuration fields:
  ```python
  QDRANT_URL: str = Field(default="http://localhost:6333")
  QDRANT_API_KEY: str | None = Field(default=None)
  QDRANT_COLLECTION_NAME: str = Field(default="voyage_policies")
  EMBEDDING_DIMENSION: int = Field(default=768)  # Gemini text-embedding-004
  ```
- [ ] Save file

---

### Step 5: Configure Gemini Client
- [ ] Open `app/core/config.py`
- [ ] Add Gemini configuration fields:
  ```python
  GEMINI_API_KEY: str
  GEMINI_CHAT_MODEL: str = Field(default="gemini-2.0-flash-exp")
  GEMINI_EMBEDDING_MODEL: str = Field(default="text-embedding-004")
  ```
- [ ] Remove or comment out `OPENAI_API_KEY` (transitioning from OpenAI)
- [ ] Save file

---

### Step 6: Create Database Models
- [ ] Create new directory: `app/models/`
- [ ] Create file: `app/models/__init__.py`
- [ ] Create file: `app/models/base.py` with SQLAlchemy base
- [ ] Create file: `app/models/policy.py` with:
  - `Policy` model (id, name, version, file_path, uploaded_at, uploaded_by, effective_from, effective_to, status, tags)
  - `PolicyChunk` model (id, policy_id, chunk_text, chunk_index, section_name, embedding_id, metadata)
- [ ] Create file: `app/models/audit.py` with:
  - `QueryLog` model (id, user_id, user_role, service_id, question, answer, retrieved_chunks, timestamp, helpful_feedback)
- [ ] Save all files

---

### Step 7: Initialize Alembic
- [ ] Run `alembic init alembic` in project root
- [ ] Edit `alembic.ini` - update `sqlalchemy.url` to use environment variable
- [ ] Edit `alembic/env.py`:
  - Import `AppConfig` and models
  - Set `target_metadata` to your Base.metadata
  - Configure async engine support
- [ ] Run `alembic revision --autogenerate -m "Initial schema"`
- [ ] Run `alembic upgrade head`
- [ ] Verify tables created in Postgres

---

## Phase 2: Vector Store & Embedding Services

### Step 8: Create Qdrant Vector Store Service
- [ ] Create new directory: `app/services/vector/`
- [ ] Create file: `app/services/vector/__init__.py`
- [ ] Create file: `app/services/vector/qdrant_service.py` with:
  - `QdrantService` class
  - `initialize_collection()` method (create collection with embedding dimension)
  - `upsert_vectors()` method (store policy chunks with embeddings)
  - `search_similar()` method (query by embedding, return top N chunks)
  - `delete_policy()` method (remove policy chunks by policy_id)
- [ ] Add initialization in `app/core/lifespan.py` startup event
- [ ] Test connection with health check

---

### Step 9: Create Gemini Embedding Service
- [ ] Create new directory: `app/services/llm/`
- [ ] Create file: `app/services/llm/__init__.py`
- [ ] Create file: `app/services/llm/gemini_service.py` with:
  - `GeminiService` class
  - `generate_embedding()` method (text → vector using Gemini)
  - `generate_embeddings_batch()` method (batch processing for efficiency)
  - `generate_chat_response()` method (RAG answer generation)
  - Error handling for rate limits and API errors
- [ ] Create singleton instance for reuse
- [ ] Test embedding generation with sample text

---

## Phase 3: Policy Ingestion Pipeline

### Step 10: Create PDF Text Extraction Service
- [ ] Create new directory: `app/services/ingestion/`
- [ ] Create file: `app/services/ingestion/__init__.py`
- [ ] Create file: `app/services/ingestion/pdf_parser.py` with:
  - `extract_text_from_pdf()` function (use pdfplumber)
  - `clean_text()` function (remove headers, footers, page numbers)
  - `detect_sections()` function (extract section headings)
  - `chunk_text()` function (split into 500-1000 token chunks with overlap)
  - `ChunkMetadata` model (section_name, page_number, chunk_index)
- [ ] Test with sample policy PDF
- [ ] Validate chunk quality and section detection

---

### Step 11: Create Policy Ingestion Service
- [ ] Create file: `app/services/ingestion/policy_ingestion.py` with:
  - `PolicyIngestionService` class
  - `ingest_policy()` method:
    1. Parse PDF → extract text + sections
    2. Chunk text with metadata
    3. Generate embeddings for each chunk (Gemini)
    4. Store in Qdrant with policy_id + metadata
    5. Save policy record to Postgres
  - `update_policy()` method (mark old version inactive, ingest new)
  - `delete_policy()` method (soft delete, remove from Qdrant)
- [ ] Add progress tracking for long uploads
- [ ] Test with 2-3 sample policies

---

### Step 12: Create Upload Policy Endpoint
- [ ] Create new directory: `app/apis/v1/policy/`
- [ ] Create file: `app/apis/v1/policy/__init__.py`
- [ ] Create file: `app/apis/v1/policy/models.py` with:
  - `PolicyUploadRequest` (file, name, version, tags, effective_from)
  - `PolicyUploadResponse` (policy_id, status, chunks_created)
- [ ] Create file: `app/apis/v1/policy/service.py` with:
  - `upload_policy_service()` function (orchestrates ingestion)
- [ ] Create file: `app/apis/v1/policy/controller.py` with:
  - `POST /policy/upload` endpoint (file upload + metadata)
  - Rate limit: 2 requests per 60 seconds (large files)
  - Auth check: admin role only (placeholder for now)
- [ ] Register router in `app/core/server.py`
- [ ] Test upload via Swagger UI or curl

---

## Phase 4: RAG Chat Endpoint

### Step 13: Create RAG Retrieval Service
- [ ] Create file: `app/services/rag/retrieval_service.py` with:
  - `RAGRetrievalService` class
  - `retrieve_relevant_chunks()` method:
    1. Embed user question (Gemini)
    2. Query Qdrant for top 5-10 chunks
    3. Filter by policy status (only active versions)
    4. Return chunks with metadata (policy_name, section, score)
  - `format_context()` method (chunk text → formatted prompt context)
- [ ] Add score threshold (e.g., only return chunks with similarity > 0.7)
- [ ] Test retrieval with sample questions

---

### Step 14: Create RAG Prompt Templates
- [ ] Create new directory: `app/prompts/`
- [ ] Create file: `app/prompts/rag_system_prompt.txt` with:
  ```
  You are the Voyage Care Policy Assistant. Your role is to help support workers, team leaders, and on-call staff by answering questions using ONLY the Voyage Care policies provided below.

  CRITICAL RULES:
  1. ONLY use information from the policy chunks provided in this prompt
  2. ALWAYS cite the policy name and section for every answer
  3. If the policies do not contain the answer, say: "I cannot find this in our current policies. Please escalate to your manager or on-call coordinator."
  4. Use clear risk language: "Call 999 immediately if...", "Inform on-call immediately if..."
  5. Never make assumptions or add information not in the policies
  6. If there is any ambiguity, instruct the user to seek clarification from management

  POLICY CONTEXT:
  {context}

  USER QUESTION:
  {question}

  Provide a step-by-step answer with citations.
  ```
- [ ] Create file: `app/prompts/rag_user_prompt.txt` for question formatting
- [ ] Save files

---

### Step 15: Create RAG Chat Endpoint
- [ ] Create file: `app/apis/v1/chat/rag_service.py` with:
  - `rag_chat_service()` function:
    1. Retrieve relevant chunks (RAGRetrievalService)
    2. Format prompt with context + question
    3. Call Gemini with strict system prompt
    4. Parse response
    5. Return answer + sources
  - `RAGChatResponse` model:
    ```python
    {
      "answer": str,
      "sources": [
        {"policy": str, "section": str, "version": str, "relevance_score": float}
      ],
      "confidence": str  # "high", "medium", "low"
    }
    ```
- [ ] Update `app/apis/v1/chat/controller.py`:
  - Add `POST /chat/policy` endpoint
  - Input: `{ "question": str, "user_id": str, "user_role": str, "service_id": str }`
  - Rate limit: 10 requests per 60 seconds
  - Return streaming or JSON response
- [ ] Test with sample questions:
  - "Someone's had an unwitnessed fall with a head injury, what do I do?"
  - "How do I report a safeguarding concern out of hours?"
  - "What is the capital of France?" (should refuse to answer)

---

## Phase 5: Audit Logging & Compliance

### Step 16: Create Audit Logging Service
- [ ] Create new directory: `app/services/audit/`
- [ ] Create file: `app/services/audit/__init__.py`
- [ ] Create file: `app/services/audit/logging_service.py` with:
  - `AuditLoggingService` class
  - `log_query()` method (persist to Postgres QueryLog table)
  - `get_user_logs()` method (retrieve by user_id)
  - `get_service_logs()` method (retrieve by service_id)
  - `get_high_risk_queries()` method (filter by topic tags)
- [ ] Ensure all PII handling follows GDPR requirements
- [ ] Test log persistence

---

### Step 17: Integrate Audit Logging
- [ ] Open `app/apis/v1/chat/rag_service.py`
- [ ] Add audit logging after RAG response generation:
  ```python
  await audit_service.log_query(
      user_id=request.user_id,
      user_role=request.user_role,
      service_id=request.service_id,
      question=request.question,
      answer=response.answer,
      retrieved_chunks=[chunk.id for chunk in chunks],
      timestamp=datetime.utcnow()
  )
  ```
- [ ] Test end-to-end: question → answer → log entry in database
- [ ] Verify logs contain all required fields

---

### Step 18: Create Audit Log Retrieval Endpoint
- [ ] Create new directory: `app/apis/v1/logs/`
- [ ] Create file: `app/apis/v1/logs/__init__.py`
- [ ] Create file: `app/apis/v1/logs/controller.py` with:
  - `GET /logs` endpoint (query params: user_id, service_id, start_date, end_date)
  - Auth check: manager or ops role only (placeholder)
  - Pagination support (limit, offset)
  - CSV export option (query param: `format=csv`)
- [ ] Register router in `app/core/server.py`
- [ ] Test log retrieval via API

---

## Phase 6: Testing & Validation

### Step 19: Create RAG Safety Test Suite
- [ ] Create new directory: `tests/rag/`
- [ ] Create file: `tests/rag/test_hallucination_prevention.py` with tests:
  - Test: Question outside policy scope → refuses to answer
  - Test: Ambiguous question → asks for clarification
  - Test: High-risk scenario → provides clear escalation steps
  - Test: Citations present in all responses
  - Test: No fabricated policy names or sections
- [ ] Create file: `tests/rag/test_retrieval_quality.py` with tests:
  - Test: Relevant chunks retrieved for known questions
  - Test: Score threshold filtering works
  - Test: Policy versioning (only active policies returned)
- [ ] Run all tests: `pytest tests/rag/ -v`

---

### Step 20: Test with Real Voyage Policies
- [ ] Obtain 3-5 sample Voyage Care policy PDFs:
  - Safeguarding Policy
  - Falls Management Policy
  - Medication Administration Policy
  - MCA/DoLS Policy
  - Incident Reporting Policy
- [ ] Upload each via `POST /policy/upload`
- [ ] Verify chunks created in Qdrant (check dashboard or query API)
- [ ] Test realistic questions for each policy
- [ ] Document any issues with parsing, chunking, or retrieval
- [ ] Adjust chunk size, overlap, or embedding parameters if needed

---

## Phase 7: Railway Deployment

### Step 21: Configure Railway Infrastructure
- [ ] Sign up for Railway at https://railway.app
- [ ] Create new project: "voyage-policy-assistant"
- [ ] Add services:
  - [ ] PostgreSQL database (Railway template)
  - [ ] Redis (Railway template or Upstash)
  - [ ] FastAPI app (link GitHub repo)
  - [ ] Celery worker (separate service, same repo)
- [ ] Configure external services:
  - [ ] Qdrant Cloud cluster (already created in Step 1)
  - [ ] Google Gemini API key (already created in Step 1)

---

### Step 22: Create Railway Configuration
- [ ] Create file: `railway.toml` in project root:
  ```toml
  [build]
  builder = "nixpacks"
  buildCommand = "pip install -e ."

  [deploy]
  startCommand = "gunicorn main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT"
  healthcheckPath = "/health"
  healthcheckTimeout = 100
  restartPolicyType = "on-failure"
  restartPolicyMaxRetries = 3
  ```
- [ ] Create file: `Procfile` (alternative):
  ```
  web: gunicorn main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
  worker: celery -A app.tasks.celery_main worker --loglevel=info
  ```
- [ ] Commit and push to GitHub

---

### Step 23: Configure Environment Variables on Railway
- [ ] In Railway dashboard, add environment variables:
  ```bash
  # Core
  ENVIRONMENT=production
  LOG_LEVEL=INFO
  HOST=0.0.0.0
  PORT=8000

  # Database (auto-populated by Railway Postgres)
  DATABASE_URL=${{Postgres.DATABASE_URL}}

  # Redis (auto-populated by Railway Redis)
  REDIS_HOST=${{Redis.REDIS_HOST}}
  REDIS_PORT=${{Redis.REDIS_PORT}}
  REDIS_PASSWORD=${{Redis.REDIS_PASSWORD}}

  # Gemini
  GEMINI_API_KEY=your_gemini_key_here
  GEMINI_CHAT_MODEL=gemini-2.0-flash-exp
  GEMINI_EMBEDDING_MODEL=text-embedding-004

  # Qdrant
  QDRANT_URL=https://xxx.qdrant.io
  QDRANT_API_KEY=your_qdrant_key_here
  QDRANT_COLLECTION_NAME=voyage_policies

  # Cache & Rate Limiting
  CACHE_BACKEND=redis
  RATE_LIMIT_BACKEND=redis

  # Observability (optional)
  LANGFUSE_HOST=
  LANGFUSE_PUBLIC_KEY=
  LANGFUSE_SECRET_KEY=
  ```
- [ ] Save and redeploy

---

### Step 24: Deploy and Validate
- [ ] Push code to GitHub (triggers Railway auto-deploy)
- [ ] Monitor Railway build logs for errors
- [ ] Once deployed, check health endpoint: `https://your-app.railway.app/health`
- [ ] Run database migrations on Railway:
  ```bash
  railway run alembic upgrade head
  ```
- [ ] Initialize Qdrant collection (one-time):
  ```bash
  railway run python -m app.services.vector.initialize
  ```
- [ ] Upload test policy via Railway URL
- [ ] Test RAG chat endpoint with sample questions
- [ ] Check Postgres logs table for audit entries
- [ ] Verify Grafana metrics (if configured)
- [ ] Load test with realistic traffic (100 requests)

---

## Post-Deployment Checklist

### Governance & Compliance
- [ ] Document DPIA (Data Protection Impact Assessment)
- [ ] Define data retention policy for audit logs
- [ ] Get Voyage Care sign-off on cloud providers (Railway, Qdrant, Google)
- [ ] Review GDPR compliance for PII in logs
- [ ] Create incident response plan for AI failures

### Auth & RBAC (Phase 2 - Future)
- [ ] Integrate Auth0, Clerk, or Azure AD SSO
- [ ] Implement role-based access control:
  - `support_worker` → ask questions only
  - `team_leader` → ask + view local logs
  - `ops` → global logs, policy management
- [ ] Add JWT token validation middleware
- [ ] Test RBAC rules with different user roles

### Monitoring & Alerts
- [ ] Set up Railway alerts for:
  - API response time > 2 seconds
  - Error rate > 1%
  - Database connection failures
- [ ] Configure Langfuse for LLM call tracing
- [ ] Set up Sentry or similar for error tracking
- [ ] Create Grafana dashboard for:
  - Questions per hour
  - Top policy topics
  - Low confidence answers (policy gaps)

### Documentation
- [ ] Write API documentation (Swagger already auto-generated)
- [ ] Create user guide for support workers
- [ ] Document policy upload process for admins
- [ ] Write runbook for common issues (Gemini rate limits, Qdrant downtime)
- [ ] Create video tutorial for web interface (once built)

---

## Phase 2 & 3 (Future Roadmap)

### Phase 2: Multi-Policy & Governance Features
- [ ] Policy versioning UI
- [ ] Manager dashboard with analytics
- [ ] Policy gap detection (low confidence queries)
- [ ] Multi-service support (filter policies by location)
- [ ] Bulk policy upload

### Phase 3: React Native Mobile App
- [ ] Set up React Native project (Expo)
- [ ] Design mobile UI (search bar, quick actions, citations)
- [ ] Integrate with FastAPI backend
- [ ] Add biometric authentication
- [ ] Push notifications for policy updates
- [ ] Offline mode (cache recent policies)
- [ ] Submit to App Store & Google Play

---

## Success Metrics

### Technical Metrics
- [ ] API response time < 2 seconds (p95)
- [ ] Uptime > 99.5%
- [ ] Zero hallucinations in testing (100 question test set)
- [ ] All answers include citations
- [ ] Audit logs captured for 100% of queries

### Business Metrics
- [ ] 80% of support workers use the assistant weekly
- [ ] 50% reduction in "policy clarification" calls to managers
- [ ] CQC audit shows evidence of policy compliance
- [ ] 90% of users rate answers as "helpful"
- [ ] Zero incidents of incorrect advice leading to harm

---

## Emergency Rollback Plan

If issues arise in production:

1. **Disable RAG endpoint:**
   ```bash
   railway env set FEATURE_RAG_ENABLED=false
   railway redeploy
   ```

2. **Roll back to previous version:**
   ```bash
   railway rollback
   ```

3. **Fallback to manual policy lookup:**
   - Update `/chat/policy` to return: "Policy assistant temporarily unavailable. Please refer to SharePoint or contact your manager."

4. **Check logs for root cause:**
   ```bash
   railway logs --service fastapi-app
   railway logs --service postgres
   ```

5. **Contact support:**
   - Railway: https://railway.app/help
   - Qdrant: support@qdrant.io
   - Google Cloud: Gemini API support

---

## Cost Estimates (Monthly)

| Service | Tier | Cost |
|---------|------|------|
| Railway (Hobby) | 512MB RAM, 1vCPU | $5 |
| Railway Postgres | 256MB | $5 |
| Railway Redis | 25MB | $0 (included) |
| Qdrant Cloud | Free tier | $0 (up to 1M vectors) |
| Google Gemini API | Pay-as-you-go | ~$10-50 (depends on usage) |
| **Total** | | **$20-60/month** |

For production scale (100+ users):
- Railway Pro: $20/month
- Qdrant Standard: $95/month
- Gemini API: $100-500/month
- **Total: $215-620/month**

---

## Next Steps

Start with **Phase 0, Step 1** and work sequentially. Each step builds on the previous one.

**Estimated Timeline:**
- Phase 0-2: 2-3 days (core infrastructure)
- Phase 3-4: 2-3 days (RAG implementation)
- Phase 5-6: 1-2 days (logging & testing)
- Phase 7: 1 day (Railway deployment)
- **Total: 6-9 days for MVP**

**Ready to start? Begin with Step 1: Install Vector Database & AI Dependencies**
