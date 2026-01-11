# Deployment Guide - Ghana Legal AI

This guide covers deploying the Ghana Legal AI system to production.

## 1. Database (MongoDB Atlas)
Already configured! Ensure your IP access list in MongoDB Atlas includes:
- `0.0.0.0/0` (Allow from anywhere) OR
- Specific IP addresses of your backend deployment services (Render/Railway).

## 2. Backend (FastAPI)
We recommend **Render** or **Railway** for easy Python deployment.

### Deploying to Render
1. **Create a Web Service** on [Render](https://render.com).
2. Connect your GitHub repository.
3. Settings:
   - **Root Directory**: `ghana-legal-ai/legal-api`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python -m src.ghana_legal.infrastructure.api` (Adjust python path if needed, e.g., `cd src && uvicorn ghana_legal.infrastructure.api:app --host 0.0.0.0 --port $PORT`)
4. **Environment Variables**:
   Add all keys from your local `.env`:
   - `GROQ_API_KEY`
   - `OPENAI_API_KEY`
   - `MONGO_URI`
   - `COMET_API_KEY`
   - `COMET_PROJECT`

### Deploying to Railway
1. **New Project** → Deploy from GitHub repo.
2. Select the repository.
3. Configure the `legal-api` service.
4. Add Environment Variables in the "Variables" tab.
5. Railway often auto-detects `requirements.txt`.

## 3. Frontend (Next.js)
**Vercel** is the best platform for Next.js.

1. **Import Project** on [Vercel](https://vercel.com).
2. Select your repository.
3. **Framework Preset**: Next.js (Auto-detected).
4. **Root Directory**: Edit to `ghana-legal-ai/legal-web`.
5. **Environment Variables**:
   - `NEXT_PUBLIC_API_URL`: The URL of your deployed Backend (e.g., `https://ghana-legal-api.onrender.com`).
   - *Note: Do not add backend secrets (Groq/Mongo keys) here.*

## 4. Final Verification
1. Open your Vercel URL (e.g., `https://ghana-legal-ai.vercel.app`).
2. Try a chat query.
3. Check Opik/Comet to ensure the trace was logged.
