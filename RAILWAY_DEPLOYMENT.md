# Railway Deployment Guide for PrivateIV

## 🚀 Quick Setup

### Step 1: Create Services on Railway

You need **4 separate services**:

1. **PostgreSQL** (Database)
2. **Redis** (Celery broker)
3. **Django API** (Backend)
4. **Celery Worker** (Background tasks)

Optional:
5. **Celery Beat** (Scheduled tasks)
6. **Frontend** (React app)

---

## 📦 Service 1: PostgreSQL

1. In Railway dashboard, click **"+ New"**
2. Select **"Database" → "PostgreSQL"**
3. Railway will provision it automatically
4. **Copy the DATABASE_URL** from the PostgreSQL service variables

---

## 📦 Service 2: Redis

1. Click **"+ New"**
2. Select **"Database" → "Redis"**
3. Railway will provision it automatically
4. **Copy the REDIS_URL** from the Redis service variables

---

## 📦 Service 3: Django API (Backend)

### A. Create the Service

1. Click **"+ New"**
2. Select **"GitHub Repo"**
3. Choose your `privateiv` repository
4. Set **Root Directory**: `backend`

### B. Configure Environment Variables

Add these in the Django API service settings → Variables:

```env
# Django Settings
DJANGO_SETTINGS_MODULE=TradeSimulator.settings
SECRET_KEY=your-secret-key-here-generate-a-strong-one
DEBUG=False
ALLOWED_HOSTS=.railway.app,.up.railway.app
CSRF_TRUSTED_ORIGINS=https://*.railway.app,https://*.up.railway.app

# Database (use the DATABASE_URL from PostgreSQL service)
DATABASE_URL=${{Postgres.DATABASE_URL}}

# Celery/Redis (use the REDIS_URL from Redis service)
CELERY_BROKER_URL=${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}

# API Keys (replace with your actual keys)
BVL_API_KEY=your-key-here
FMP_API=your-key-here

# Datadog (optional)
DD_API_KEY=your-datadog-api-key
DD_SITE=datadoghq.com
DD_ENV=production
DD_SERVICE=privateiv-api

# CORS (for frontend)
CORS_ALLOWED_ORIGINS=https://your-frontend-url.railway.app
```

### C. Configure Start Command

Railway will auto-detect from `Procfile`, but you can also set it in Settings:

**Start Command**: `gunicorn TradeSimulator.wsgi:application --bind 0.0.0.0:$PORT --workers 3`

### D. Deploy

Click **"Deploy"** - Railway will:
1. Install Python 3.11
2. Install requirements.txt
3. Run collectstatic
4. Start gunicorn

---

## 📦 Service 4: Celery Worker

### A. Create the Service

1. Click **"+ New"**
2. Select **"GitHub Repo"** (same repo)
3. Choose your `privateiv` repository
4. Set **Root Directory**: `backend`

### B. Configure Environment Variables

**Copy ALL environment variables from Django API service**

OR use Railway's variable referencing:

```env
DATABASE_URL=${{Django.DATABASE_URL}}
CELERY_BROKER_URL=${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}
DJANGO_SETTINGS_MODULE=TradeSimulator.settings
SECRET_KEY=${{Django.SECRET_KEY}}
# ... copy all other vars
```

### C. Configure Start Command

In Settings → Start Command:

```bash
celery -A TradeSimulator worker --loglevel=info
```

### D. Deploy

Click **"Deploy"**

---

## 📦 Service 5: Celery Beat (Optional - for scheduled tasks)

### A. Create the Service

1. Click **"+ New"**
2. Select **"GitHub Repo"** (same repo)
3. Set **Root Directory**: `backend`

### B. Environment Variables

Same as Celery Worker (copy all from Django service)

### C. Start Command

```bash
celery -A TradeSimulator beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### D. Deploy

---

## 📦 Service 6: Frontend (React)

### A. Create the Service

1. Click **"+ New"**
2. Select **"GitHub Repo"**
3. Set **Root Directory**: `frontend`

### B. Environment Variables

```env
VITE_API_URL=https://your-django-service.up.railway.app
```

### C. Build & Start Commands

Railway should auto-detect Vite, but if not:

- **Build Command**: `npm run build`
- **Start Command**: `npm run preview` (or use a static server)

Better option - use a static server:

1. Add to `frontend/package.json`:
```json
{
  "scripts": {
    "start": "npx serve dist -s -p $PORT"
  }
}
```

2. Start Command: `npm start`

---

## 🔧 Post-Deployment Steps

### 1. Run Migrations

In Railway Django service → Settings → Deploy Logs, you can run:

```bash
python manage.py migrate
```

Or use Railway CLI:
```bash
railway run python manage.py migrate
```

### 2. Create Superuser

```bash
railway run python manage.py createsuperuser
```

### 3. Test the Services

- Django API: `https://your-django-service.up.railway.app/admin`
- Frontend: `https://your-frontend-service.up.railway.app`

### 4. Check Celery Workers

In Django service logs, you should see:
```
[INFO] celery@worker ready
```

---

## 🐛 Troubleshooting

### Build Failed - "No start command"

✅ **Fixed**: Added `Procfile` and `nixpacks.toml`

### Database Connection Error

Check:
1. `DATABASE_URL` is correctly set
2. PostgreSQL service is running
3. Django service can reach PostgreSQL (they should be in same project)

### Celery Not Picking Up Tasks

Check:
1. Redis is running
2. `CELERY_BROKER_URL` is set correctly in both Django and Worker services
3. Worker service logs show connection to broker

### Static Files Not Loading

Run in Django service:
```bash
railway run python manage.py collectstatic --noinput
```

Add to `nixpacks.toml` build phase.

---

## 💰 Estimated Costs

**Starter Plan** (what you'll likely use):

- PostgreSQL: $0 (500MB free)
- Redis: $0 (100MB free)
- Django API: ~$5/month (1 instance)
- Celery Worker: ~$5/month (1 instance)
- Celery Beat: ~$5/month (1 instance)
- Frontend: ~$0-5/month (static)

**Total**: ~$15-20/month

**Free Tier**: Railway gives $5 credit/month, so actual cost: ~$10-15/month

---

## 🎯 Quick Commands

### Deploy Specific Service
```bash
railway up
```

### View Logs
```bash
railway logs
```

### Run Commands
```bash
railway run python manage.py migrate
railway run python manage.py createsuperuser
railway run python manage.py shell
```

### Check Service Status
```bash
railway status
```

---

## 📋 Checklist Before Deploy

- [x] `Procfile` created
- [x] `nixpacks.toml` created
- [x] `gunicorn` added to requirements.txt
- [ ] Set all environment variables
- [ ] Configure CORS origins
- [ ] Add API keys
- [ ] Set SECRET_KEY
- [ ] Run migrations after deploy
- [ ] Create superuser
- [ ] Test all endpoints

---

## 🔐 Security Notes

1. **Never commit**:
   - `SECRET_KEY`
   - API keys
   - Database credentials

2. **Use Railway's secret variables** for sensitive data

3. **Set `DEBUG=False`** in production

4. **Configure ALLOWED_HOSTS** properly

---

## 🚀 You're Ready!

Your Railway deployment should now work. The current error was because Railway detected Node.js but you have a Django app.

With the files I created:
- `Procfile` → Tells Railway how to start Django
- `nixpacks.toml` → Configures Python build
- `requirements.txt` → Updated with gunicorn

Now re-deploy and it should work! 🎉
