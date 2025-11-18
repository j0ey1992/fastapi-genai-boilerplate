# Railway Deployment Guide

Complete guide for deploying the Voyage AI Policy Assistant to Railway.

---

## Prerequisites

1. **Railway Account** - Sign up at https://railway.app
2. **GitHub Repository** - Code must be in a GitHub repo
3. **External Services:**
   - **Qdrant Cloud** account (free tier: https://cloud.qdrant.io)
   - **Google Gemini API key** (https://aistudio.google.com/apikey)

---

## Architecture Overview

```
Railway Services:
├── FastAPI App (Web)
├── Celery Worker (Background tasks)
├── PostgreSQL (Managed by Railway)
└── Redis (Managed by Railway)

External Services:
├── Qdrant Cloud (Vector database)
└── Google Gemini API (LLM & embeddings)
```

---

## Step-by-Step Deployment

### 1. Create Qdrant Cloud Instance

1. Go to https://cloud.qdrant.io
2. Create a free cluster
3. Note your:
   - Cluster URL (e.g., `https://xxx-yyy.qdrant.io`)
   - API Key
4. The collection will be auto-created on first run

### 2. Get Google Gemini API Key

1. Go to https://aistudio.google.com/apikey
2. Create a new API key
3. Copy the key (starts with `AIza...`)

### 3. Set Up Railway Project

1. Go to https://railway.app/new
2. Click "Deploy from GitHub repo"
3. Select your repository
4. Railway will auto-detect the Python project

### 4. Add PostgreSQL Database

1. In Railway dashboard, click "+ New"
2. Select "Database" → "PostgreSQL"
3. Railway will provision and link automatically
4. The `DATABASE_URL` environment variable is auto-set

### 5. Add Redis

1. Click "+ New"
2. Select "Database" → "Redis"
3. Railway will provision and link automatically
4. Note the connection details:
   - `REDIS_HOST`
   - `REDIS_PORT`
   - `REDIS_PASSWORD`

### 6. Configure Environment Variables

In Railway dashboard → Variables tab, add:

```bash
# Core
ENVIRONMENT=production
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000

# Database (auto-populated by Railway)
DATABASE_URL=${{Postgres.DATABASE_URL}}

# Redis (auto-populated by Railway)
REDIS_HOST=${{Redis.REDIS_HOST}}
REDIS_PORT=${{Redis.REDIS_PORT}}
REDIS_PASSWORD=${{Redis.REDIS_PASSWORD}}

# Google Gemini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_CHAT_MODEL=gemini-2.0-flash-exp
GEMINI_EMBEDDING_MODEL=text-embedding-004

# Qdrant Vector Database
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your_qdrant_api_key_here
QDRANT_COLLECTION_NAME=voyage_policies
EMBEDDING_DIMENSION=768

# Cache & Rate Limiting
CACHE_BACKEND=redis
RATE_LIMIT_BACKEND=redis

# API Configuration
API_PREFIX=voyage

# Optional: Observability
LANGFUSE_HOST=
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

### 7. Deploy FastAPI App

1. Railway will auto-deploy from your GitHub repo
2. Monitor build logs in Railway dashboard
3. First deployment runs: `alembic upgrade head` (creates DB tables)
4. Then starts: `gunicorn main:app`

### 8. Add Celery Worker (Optional)

1. Click "+ New" → "Empty Service"
2. Link to same GitHub repo
3. Set custom start command:
   ```bash
   celery -A app.tasks.celery_main worker --loglevel=info --concurrency=2
   ```
4. Use same environment variables as web service

### 9. Verify Deployment

1. **Check Health Endpoint:**
   ```bash
   curl https://your-app.railway.app/health
   ```
   Expected: `{"status": "healthy", "version": "0.0.1", "environment": "production"}`

2. **Check API Docs:**
   Visit: `https://your-app.railway.app/docs`

3. **Test Database Connection:**
   Check Railway logs for successful Alembic migration

4. **Test Qdrant Connection:**
   Logs should show: `Qdrant collection 'voyage_policies' created/exists`

---

## Post-Deployment Setup

### 1. Run Database Migrations

Migrations run automatically on deployment via `alembic upgrade head` in the start command.

To run manually:
```bash
railway run alembic upgrade head
```

### 2. Initialize Qdrant Collection

The collection is auto-created on first Qdrant service initialization. To verify:

```bash
railway run python -c "
import asyncio
from app.services.vector.qdrant_service import get_qdrant_service

async def test():
    service = await get_qdrant_service()
    print('Qdrant initialized successfully')

asyncio.run(test())
"
```

### 3. Upload First Policy

Use the `/policy/upload` endpoint:

```bash
curl -X POST https://your-app.railway.app/voyage/api/v1/policy/upload \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample_policy.pdf" \
  -F "policy_name=Safeguarding Policy" \
  -F "version=v5.0" \
  -F "effective_from=2024-01-01" \
  -F "uploaded_by=admin"
```

### 4. Test RAG Chat

```bash
curl -X POST https://your-app.railway.app/voyage/api/v1/chat/policy \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What should I do if someone has a fall?",
    "user_id": "test_user",
    "user_role": "support_worker",
    "stream": false
  }'
```

Expected response:
```json
{
  "answer": "According to the Falls Management Policy...",
  "sources": [
    {"policy": "Falls Management", "version": "v5.0", "section": "...", "relevance_score": 0.92}
  ],
  "confidence": "high",
  "chunks_retrieved": 3
}
```

---

## Railway-Specific Configuration

### Auto-Scaling

Railway auto-scales based on load. Configure in `railway.toml`:

```toml
[deploy]
replicas = 2  # Minimum replicas
maxReplicas = 10  # Maximum replicas
```

### Custom Domains

1. Go to Settings → Domains
2. Add custom domain (e.g., `policies.voyagecare.com`)
3. Update DNS records as shown
4. SSL certificate auto-provisioned

### Monitoring & Logs

1. **View Logs:** Railway dashboard → Deployments → View Logs
2. **Metrics:** Railway provides CPU, memory, network metrics
3. **Alerts:** Set up in Settings → Notifications

### Database Backups

Railway PostgreSQL includes automatic daily backups:
- Retention: 7 days
- Restore via Railway dashboard

---

## Production Checklist

### Before Go-Live

- [ ] All environment variables set correctly
- [ ] Database migrations run successfully
- [ ] Qdrant collection initialized
- [ ] At least 5 policies uploaded and indexed
- [ ] Health endpoint returns 200
- [ ] RAG chat endpoint tested with real questions
- [ ] Audit logs being written to PostgreSQL
- [ ] Rate limiting configured (check `.env`)
- [ ] CORS settings reviewed (`app/core/server.py`)
- [ ] Error tracking configured (Sentry recommended)

### Security

- [ ] Change default API keys/passwords
- [ ] Enable HTTPS only (Railway default)
- [ ] Implement authentication (TODO: Add Auth0/Clerk)
- [ ] Restrict `/policy/upload` to admin role
- [ ] Restrict `/logs` to manager/ops role
- [ ] Review GDPR compliance for query logs
- [ ] Set up log rotation/retention policy

### Performance

- [ ] Test with 100 concurrent users
- [ ] Verify p95 response time < 2 seconds
- [ ] Check Qdrant search performance
- [ ] Monitor Gemini API quota/costs
- [ ] Set up CDN for static assets (if needed)

### Compliance (CQC)

- [ ] All queries logged with user_id, timestamp
- [ ] Audit trail accessible via `/logs` endpoint
- [ ] Data retention policy documented
- [ ] DPIA (Data Protection Impact Assessment) completed
- [ ] Policy version history tracked
- [ ] High-risk queries flaggable for review

---

## Troubleshooting

### Issue: Database Connection Fails

**Symptoms:** `asyncpg.exceptions.InvalidCatalogNameError`

**Solution:**
1. Check `DATABASE_URL` environment variable is set
2. Ensure Railway Postgres service is running
3. Verify Alembic migrations ran: `railway run alembic current`

---

### Issue: Qdrant Connection Timeout

**Symptoms:** `Failed to initialize Qdrant client: timeout`

**Solution:**
1. Verify Qdrant Cloud cluster is running
2. Check `QDRANT_URL` and `QDRANT_API_KEY` are correct
3. Test connection: `curl -H "api-key: YOUR_KEY" https://your-cluster.qdrant.io/collections`

---

### Issue: Gemini API Rate Limit

**Symptoms:** `429 Too Many Requests`

**Solution:**
1. Check Gemini API quota: https://aistudio.google.com/
2. Implement request queuing in Celery
3. Upgrade to Gemini Pro tier if needed
4. Add retry logic with exponential backoff

---

### Issue: Migrations Fail on Deploy

**Symptoms:** `alembic.util.exc.CommandError`

**Solution:**
1. Check database is accessible
2. Run migrations manually: `railway run alembic upgrade head`
3. Review migration files in `alembic/versions/`
4. Check for SQL syntax errors in models

---

## Cost Estimates

| Service | Tier | Monthly Cost |
|---------|------|--------------|
| Railway Hobby | 512MB RAM, 1vCPU | $5 |
| Railway PostgreSQL | 256MB | $5 |
| Railway Redis | 25MB | Free (included) |
| Qdrant Cloud | Free tier | $0 (up to 1M vectors) |
| Google Gemini API | Pay-as-you-go | $10-100 (usage-based) |
| **Total (Pilot)** | | **$20-110/month** |

For production (100+ users):
- Railway Pro: $20/month
- Railway PostgreSQL: $10/month (1GB)
- Qdrant Standard: $95/month
- Gemini API: $100-500/month (high usage)
- **Total: $225-630/month**

---

## Next Steps

1. **Set up monitoring:** Integrate Sentry or Datadog
2. **Add authentication:** Implement user auth (Auth0, Clerk, or custom)
3. **Build admin dashboard:** React/Vue app for policy management
4. **Implement RBAC:** Role-based access control
5. **Add caching:** Redis caching for common queries
6. **Optimize embeddings:** Fine-tune chunk size/overlap
7. **A/B testing:** Test different prompt templates
8. **Feedback loop:** Use `helpful_feedback` to improve

---

## Support & Resources

- **Railway Docs:** https://docs.railway.app
- **Qdrant Docs:** https://qdrant.tech/documentation
- **Gemini API Docs:** https://ai.google.dev/docs
- **FastAPI Docs:** https://fastapi.tiangolo.com
- **Issue Tracker:** Your GitHub repo issues tab

---

## Emergency Rollback

If deployment fails or causes issues:

1. **Revert to previous deployment:**
   ```bash
   railway rollback
   ```

2. **Disable RAG endpoint temporarily:**
   - Set environment variable: `FEATURE_RAG_ENABLED=false`
   - Redeploy

3. **Fallback message:**
   - Update `/chat/policy` to return: "Policy assistant temporarily unavailable. Please contact your manager."

4. **Contact support:**
   - Railway: https://railway.app/help
   - Email: support@voyagecare.com (update with actual)

---

**Deployed Successfully?** ✅

Next: Upload your Voyage Care policies and start testing!
