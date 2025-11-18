# Voyage AI Policy Assistant - Complete Setup Guide

**Production-ready RAG system for Voyage Care policy management**

---

## 🎯 What You've Built

A complete healthcare policy RAG (Retrieval-Augmented Generation) assistant with:

✅ **Core Features:**
- PDF policy ingestion with automatic chunking & embedding
- Semantic search across all active policies
- RAG-based question answering with Google Gemini
- Source citation with confidence scoring
- Complete audit trail for CQC compliance
- Rate limiting & caching for performance
- Safety mechanisms (hallucination prevention)

✅ **Tech Stack:**
- **Backend:** FastAPI + Python 3.10+
- **Vector DB:** Qdrant Cloud
- **LLM:** Google Gemini (chat + embeddings)
- **Database:** PostgreSQL (via Railway)
- **Cache:** Redis (via Railway)
- **Deployment:** Railway

---

## 📂 Project Structure

```
/project/workspace/
├── app/
│   ├── apis/v1/
│   │   ├── chat/          # RAG chat endpoints
│   │   ├── policy/        # Policy upload/management
│   │   └── logs/          # Audit log retrieval
│   ├── models/            # SQLAlchemy DB models
│   │   ├── policy.py      # Policy, PolicyChunk
│   │   └── audit.py       # QueryLog
│   ├── services/
│   │   ├── vector/        # Qdrant service
│   │   ├── llm/           # Gemini service
│   │   ├── ingestion/     # PDF parsing & policy ingestion
│   │   ├── rag/           # RAG retrieval service
│   │   └── audit/         # Audit logging
│   ├── prompts/           # RAG system prompts
│   └── core/              # Config, middleware, responses
├── alembic/               # Database migrations
├── tests/rag/             # RAG safety tests
├── railway.toml           # Railway deployment config
├── Procfile               # Alternative deployment config
├── RAILWAY_DEPLOYMENT.md  # Full deployment guide
└── pyproject.toml         # Dependencies

**Total Code:** ~2,500+ lines of production-ready Python
```

---

## 🚀 Quick Start (Local Development)

### 1. Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install project
pip install -e .
```

### 2. Set Up External Services

**A. Qdrant Cloud (Vector Database)**
1. Go to https://cloud.qdrant.io
2. Create free cluster
3. Copy URL and API key

**B. Google Gemini API**
1. Go to https://aistudio.google.com/apikey
2. Create API key
3. Copy key (starts with `AIza...`)

**C. PostgreSQL (Local)**
```bash
# Option 1: Docker
docker run --name voyage-postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres:15

# Option 2: Install locally
# macOS: brew install postgresql@15
# Ubuntu: sudo apt install postgresql-15
```

### 3. Configure Environment

Copy `.env.sample` to `.env` and update:

```bash
cp .env.sample .env
```

Edit `.env`:
```bash
# Core
ENVIRONMENT=development
LOG_LEVEL=DEBUG

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/voyage_policies

# Redis (local)
REDIS_HOST=localhost
REDIS_PORT=6379
CACHE_BACKEND=local  # Use 'redis' if Redis installed
RATE_LIMIT_BACKEND=local

# Gemini
GEMINI_API_KEY=your_key_here
GEMINI_CHAT_MODEL=gemini-2.0-flash-exp
GEMINI_EMBEDDING_MODEL=text-embedding-004

# Qdrant
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your_key_here
QDRANT_COLLECTION_NAME=voyage_policies
EMBEDDING_DIMENSION=768
```

### 4. Initialize Database

```bash
# Run migrations
alembic upgrade head

# Verify tables created
psql postgresql://postgres:postgres@localhost:5432/voyage_policies -c "\dt"
```

Expected tables: `policies`, `policy_chunks`, `query_logs`, `alembic_version`

### 5. Run Application

```bash
# Development mode (with auto-reload)
python main.py

# Or with uvicorn directly
uvicorn main:app --reload --host 0.0.0.0 --port 8002
```

Application will start at: `http://localhost:8002`

### 6. Verify Setup

**Check API docs:**
```bash
open http://localhost:8002/docs
```

**Test health endpoint:**
```bash
curl http://localhost:8002/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "0.0.1",
  "environment": "development"
}
```

---

## 📝 API Endpoints Overview

### Policy Management

**Upload Policy**
```bash
POST /voyage/api/v1/policy/upload
Content-Type: multipart/form-data

Fields:
- file: PDF file
- policy_name: "Safeguarding Policy"
- version: "v5.0"
- effective_from: "2024-01-01"
- uploaded_by: "admin@voyagecare.com"
- tags: '{"topic": ["safeguarding"], "roles": ["all"]}'
```

**List Policies**
```bash
GET /voyage/api/v1/policy/list?page=1&page_size=20&status_filter=active
```

**Delete Policy**
```bash
DELETE /voyage/api/v1/policy/{policy_id}
```

### RAG Chat

**Ask Policy Question**
```bash
POST /voyage/api/v1/chat/policy
Content-Type: application/json

{
  "question": "What should I do if someone has a fall with a head injury?",
  "user_id": "user123",
  "user_role": "support_worker",
  "service_id": "care_home_london",
  "stream": false
}
```

Response:
```json
{
  "answer": "Call 999 immediately for emergency medical assistance...",
  "sources": [
    {
      "policy": "Falls Management Policy",
      "version": "v5.2",
      "section": "Head Injuries",
      "relevance_score": 0.92
    }
  ],
  "confidence": "high",
  "chunks_retrieved": 3
}
```

### Audit Logs

**Get Query Logs**
```bash
GET /voyage/api/v1/logs?page=1&page_size=50&high_risk_only=false
```

**Update Feedback**
```bash
POST /voyage/api/v1/logs/feedback
{
  "log_id": 123,
  "helpful": true
}
```

---

## 🧪 Testing

### Run All Tests

```bash
pytest tests/ -v
```

### Run RAG Safety Tests

```bash
pytest tests/rag/test_hallucination_prevention.py -v
```

### Test Policy Upload

```bash
# Create test PDF (or use real policy)
curl -X POST http://localhost:8002/voyage/api/v1/policy/upload \
  -F "file=@test_policy.pdf" \
  -F "policy_name=Test Policy" \
  -F "version=v1.0" \
  -F "effective_from=2024-01-01" \
  -F "uploaded_by=test_user"
```

### Test RAG Query

```bash
curl -X POST http://localhost:8002/voyage/api/v1/chat/policy \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the safeguarding procedure?",
    "user_id": "test_user",
    "user_role": "support_worker"
  }'
```

---

## 🔒 Security Best Practices

### Before Production

1. **Add Authentication**
   - Implement Auth0, Clerk, or custom JWT auth
   - Protect `/policy/upload` (admin only)
   - Protect `/logs` (manager/ops only)

2. **Environment Variables**
   - Never commit `.env` to git
   - Use Railway secrets for production
   - Rotate API keys regularly

3. **Rate Limiting**
   - Current: 10 req/min for chat, 2 req/min for upload
   - Adjust based on usage patterns
   - Monitor for abuse

4. **CORS Settings**
   - Update `app/core/server.py`
   - Restrict to your domain only
   - Remove `allow_origins=["*"]`

5. **HTTPS Only**
   - Railway provides HTTPS by default
   - Redirect HTTP → HTTPS

---

## 📊 Monitoring & Observability

### Logs

```bash
# View logs locally
tail -f logs/app.log  # If configured

# View logs on Railway
railway logs --service fastapi-app
```

### Metrics (Railway Dashboard)

- CPU usage
- Memory usage
- Request count
- Response times
- Error rates

### Langfuse (Optional - LLM Tracing)

1. Sign up at https://langfuse.com
2. Get API keys
3. Set in `.env`:
   ```bash
   LANGFUSE_HOST=https://cloud.langfuse.com
   LANGFUSE_PUBLIC_KEY=pk-xxx
   LANGFUSE_SECRET_KEY=sk-xxx
   ```
4. View LLM calls in Langfuse dashboard

---

## 🐛 Troubleshooting

### Common Issues

**1. "Database connection failed"**
- Check `DATABASE_URL` is correct
- Verify PostgreSQL is running
- Test connection: `psql $DATABASE_URL`

**2. "Qdrant timeout"**
- Check Qdrant Cloud cluster is active
- Verify `QDRANT_URL` and `QDRANT_API_KEY`
- Test: `curl -H "api-key: YOUR_KEY" $QDRANT_URL/collections`

**3. "Gemini API error"**
- Check `GEMINI_API_KEY` is valid
- Verify API quota at https://aistudio.google.com
- Check rate limits

**4. "No relevant policies found"**
- Ensure policies are uploaded
- Check policy status is "active"
- Verify embeddings created in Qdrant
- Lower `score_threshold` in code (default: 0.7)

**5. "Alembic migration failed"**
- Drop database and recreate: `dropdb voyage_policies && createdb voyage_policies`
- Run migrations: `alembic upgrade head`
- Check for duplicate migration files

---

## 📚 Additional Resources

### Documentation
- **FastAPI:** https://fastapi.tiangolo.com
- **Qdrant:** https://qdrant.tech/documentation
- **Gemini API:** https://ai.google.dev/docs
- **SQLAlchemy:** https://docs.sqlalchemy.org
- **Alembic:** https://alembic.sqlalchemy.org

### Plan Documents
- `Plan.md` - Original architecture plan
- `IMPLEMENTATION_PLAN.md` - Step-by-step implementation guide
- `RAILWAY_DEPLOYMENT.md` - Production deployment guide
- `PROGRESS.md` - Current implementation status

---

## 🎓 Training & Onboarding

### For Developers

1. Read `Plan.md` for architecture overview
2. Review `app/models/` for database schema
3. Understand RAG pipeline in `app/services/rag/`
4. Study safety prompts in `app/prompts/`
5. Run tests to see expected behavior

### For Admins

1. Learn policy upload process
2. Understand versioning system
3. Review audit log access
4. Practice emergency rollback

### For Support Staff

1. Test asking questions via API
2. Understand when to escalate
3. Provide feedback on answers
4. Report any hallucinations

---

## 🚦 Ready for Production?

### Pre-Deployment Checklist

- [ ] All tests passing (`pytest`)
- [ ] Railway project created
- [ ] PostgreSQL provisioned
- [ ] Redis provisioned
- [ ] Qdrant Cloud cluster active
- [ ] Gemini API key valid & funded
- [ ] Environment variables configured
- [ ] First migration successful
- [ ] 5+ policies uploaded & indexed
- [ ] RAG chat tested with 10+ questions
- [ ] Audit logs verified in database
- [ ] Authentication implemented
- [ ] CORS restricted to production domain
- [ ] Monitoring/alerts configured
- [ ] DPIA completed (GDPR compliance)
- [ ] CQC audit trail validated
- [ ] Emergency contact list prepared

### Launch Day

1. Deploy to Railway (see `RAILWAY_DEPLOYMENT.md`)
2. Run smoke tests on production URL
3. Upload all Voyage Care policies
4. Train support staff
5. Monitor logs for 24 hours
6. Collect feedback

### Post-Launch

1. Weekly audit log reviews
2. Monthly policy updates
3. Quarterly system performance review
4. Continuous prompt optimization
5. User feedback integration

---

## 💰 Cost Management

### Optimize Gemini API Costs

- Cache common queries (Redis)
- Batch embeddings where possible
- Use `gemini-2.0-flash-exp` (cheaper than Pro)
- Monitor usage in Google Cloud Console

### Optimize Qdrant Costs

- Free tier: 1M vectors
- Estimate: 1 policy (50 pages) ≈ 100-200 chunks
- 100 policies ≈ 15,000 vectors (well within free tier)

### Railway Costs

- Hobby plan: $5/month per service
- Consider annual plan for discount
- Monitor resource usage in dashboard

---

## 📞 Support

**Issues?** Create GitHub issue with:
- Error logs
- Steps to reproduce
- Expected vs actual behavior
- Environment details

**Emergency Contact:**
- Railway Support: https://railway.app/help
- Qdrant Support: support@qdrant.io

---

## 🎉 You're All Set!

Your Voyage AI Policy Assistant is ready for deployment.

**Next Steps:**
1. Follow `RAILWAY_DEPLOYMENT.md` for production deployment
2. Upload your Voyage Care policies
3. Test with real user questions
4. Monitor and iterate

**Good luck! 🚀**
