# Deploy Nyra to Railway

Railway CLI is installed. Run these commands **in your terminal** (they need to open a browser).

## 1. Log in to Railway
```powershell
cd "c:\Users\Pico Mause\Dev\nyra-basic"
railway login
```
A browser will open — sign in with GitHub or email.

## 2. Create a new project
```powershell
railway init
```
Choose **Empty Project** when prompted. Name it `nyra` or similar.

## 3. Set environment variables
```powershell
railway variables set ANTHROPIC_API_KEY="your-anthropic-key"
railway variables set STELLARIA_API_KEY="your-stellaria-key"
railway variables set STELLARIA_BASE_URL="https://stellaria-web-production.up.railway.app"
```
(Get your keys from Anthropic console and Stellaria Settings.)

## 4. Deploy
```powershell
railway up
```
Railway will build and deploy. When done, you'll get a URL like `https://nyra-production-xxxx.up.railway.app`.

## 5. Register the webhook in Stellaria
Go to [Stellaria Settings](https://stellaria-web-production.up.railway.app/settings) → Reply Webhook and enter:
```
https://YOUR-RAILWAY-URL/api/stellaria/notify
```
