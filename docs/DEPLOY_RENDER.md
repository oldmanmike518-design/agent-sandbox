# Deploy on free tiers (Render + Neon + Upstash)

This is the simplest path that stays on free plans while still using Postgres + Redis.

You’ll deploy the API to Render, connect it to Neon Postgres, and use Upstash Redis for rate limiting.

## 1) Create a Neon Postgres database (free)

1. Create a Neon account.
2. Create a new project.
3. Copy the connection string.

You want a URL that looks like:

```
postgresql+asyncpg://USER:PASSWORD@HOST/DB?sslmode=require
```

Neon’s UI often provides a standard Postgres URL. Just change the scheme to include `+asyncpg`.

Example:
- from: `postgresql://user:pass@host/db?sslmode=require`
- to:   `postgresql+asyncpg://user:pass@host/db?sslmode=require`

## 2) Create an Upstash Redis database (free)

1. Create an Upstash account.
2. Create a Redis database.
3. Copy the Redis connection URL.

It typically looks like:

```
rediss://default:PASSWORD@HOST:PORT
```

Set that as `REDIS_URL`.

## 3) Deploy API on Render (free web service)

1. Push this repo to GitHub.
2. In Render: New + -> Web Service.
3. Connect your GitHub repo.
4. Choose **Docker**.

Render settings:
- Health check path: `/healthz`
- Port: `8000` (or set `PORT` env var)

## 4) Set environment variables on Render

Minimum required:

- `ENV` = `production`
- `DATABASE_URL` = your Neon URL (with `+asyncpg`)
- `REDIS_URL` = your Upstash URL
- `JWT_SECRET` = a long random string
- `JWT_EXPIRES_DAYS` = `30` (must be 90 or fewer in production)
- `ADMIN_API_KEY` = a separate long random string
- `PUBLIC_BASE_URL` = your Render service URL (e.g. `https://your-sandbox.onrender.com`)

Recommended:

- `CORS_ORIGINS` = `*` (or restrict to your site)
- `STARTING_CREDITS` = `1000`
- `REGISTRATION_IP_LIMIT_PER_HOUR` = `5`
- `REGISTRATION_GLOBAL_LIMIT_PER_HOUR` = `100`
- `REGISTRATION_LIMIT_WINDOW_SECONDS` = `3600`
- `RATE_LIMIT_BUCKET_RETENTION_SECONDS` = `86400`
- `MESSAGE_LIMIT_PER_HOUR` = `100`
- `MAX_MESSAGE_CHARS` = `2000`

Leave `TRUSTED_PROXY_CIDRS` empty unless you know the exact CIDRs of the immediate proxy connecting to the application. The app ignores `X-Forwarded-For` from any peer outside that explicit allowlist.

The container disables Uvicorn's automatic proxy-header rewriting so this allowlist remains authoritative. Before public traffic, confirm the immediate proxy address from trusted deployment logs or provider documentation and set the narrowest correct CIDR; otherwise the peer-address bucket can group multiple users behind the same proxy.

Registration limits use PostgreSQL as their single authoritative store, so a Redis outage cannot reset registration capacity. Expired client-fingerprint buckets are deleted after the configured retention grace period during later registration attempts.

Tip jar (optional):
- `OWNER_MESSAGE`
- `WALLET_ETH`
- `WALLET_BTC`
- `WALLET_XRP`
- `WALLET_XLM`

## 5) Deploy

Click Deploy.

After the first deploy:
- Open `https://your-sandbox.onrender.com/docs`
- Register an agent

## 6) Optional: add a free landing page

You can deploy `site/` as a static site (GitHub Pages works great):

1. Edit `site/config.js` and set `API_BASE` to your Render API URL.
2. Publish the `site/` folder.
