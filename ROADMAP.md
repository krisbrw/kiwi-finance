# Kiwi Finance — Roadmap

## In Progress / Up Next

- [x] **1. Fix data scoping bug** — `get_accounts_local()` and `get_transactions_local()` return all users' data. Queries need to filter by the logged-in user via `plaid_items → user_id` join. Security issue.
- [x] **2. User profiles** — Add `user_profiles` table and `/profile` page with: first name, last name, monthly income, savings goal amount/date, debt payoff goal, preferred currency, profile photo (S3).
- [x] **3. PostgreSQL DB layer** — Swap `sqlite3` for `psycopg2`. Keep SQLite as local dev fallback via `DATABASE_URL` env var. Abstract connection into a shared helper.
- [x] **4. Alembic migrations** — Replace `init_db()` drop-and-recreate with proper schema migrations. Required before real users are on RDS.
- [x] **5. Provision RDS (Aurora Serverless v2)** — Add to CloudFormation: VPC, private subnets, security groups, Aurora Serverless v2 cluster. Cheaper than `db.t3.micro` for a low-traffic app.
- [x] **6. Secrets Manager** — DB password and DATABASE_URL stored in AWS Secrets Manager, fetched at runtime. Remove plaintext credentials from `.env`.
- [x] **7. Update Lambda** — Drop `state_store.py` SQLite snapshot pattern. Lambda connects directly to RDS, iterates all users and syncs each one's Plaid data.
- [x] **8. Migrate existing data** — Export SQLite → import to RDS. Resolves `user_id` type mismatch. Script at `scripts/migrate_sqlite_to_rds.py` — run after first deploy with `DATABASE_URL` set.

---

## Completed

- [x] Refresh Now button on dashboard
- [x] Fix pipeline for production Plaid env (skip sandbox-only steps)
- [x] Auth system — register, login, logout, `@login_required` on all tool/resource routes
- [x] Multi-user data scoping via session `user_id` on all Plaid routes
- [x] Debug route `/debug/plaid_transactions`
- [x] Data scoping security fix — all queries scoped per user
- [x] User profiles — `user_profiles` table + `/profile` page
- [x] PostgreSQL DB layer — dual SQLite/Postgres backend
- [x] Alembic migrations
- [x] CloudFormation — VPC, Aurora Serverless v2, Secrets Manager, Lambda
- [x] ECS Fargate hosting — ECR, ALB, HTTPS, Route 53, Dockerfile
- [x] Data migration script — `scripts/migrate_sqlite_to_rds.py`

## Ready to Deploy

Pre-deploy checklist:
- [ ] Request ACM certificate for `mykiwifinance.com` in `us-east-1`
- [ ] Add `CERTIFICATE_ARN` to `.env`
- [ ] Ensure Docker Desktop is running
- [ ] Run `deploy.ps1 -ArtifactBucket your-bucket`
- [ ] Point Cloudflare nameservers to Route 53 NS records from stack outputs
- [ ] Run `scripts/migrate_sqlite_to_rds.py` with `DATABASE_URL` from stack outputs
- [ ] Visit https://mykiwifinance.com
