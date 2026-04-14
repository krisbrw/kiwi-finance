# Kiwi-Finance

Personal finance app with real-time budget tracking across bank accounts.

## What it does

- Connects to bank accounts via Plaid API for automatic transaction sync
- Tracks budgets in real time using WebSocket push notifications
- Mobile app built with React Native (Android-first, iOS planned)
- Web app built with React.js
- Backend on AWS Lambda with PostgreSQL for data storage

## Stack

| Layer | Tech |
|---|---|
| Mobile | React Native (Android-first) |
| Web | React.js |
| Backend | Node.js · Express · AWS Lambda |
| Database | PostgreSQL · AWS RDS |
| Auth | AWS Cognito |
| Banking | Plaid API |
| Real-time | WebSockets · AWS API Gateway |
| Secrets | AWS Secrets Manager |
| CI/CD | GitHub Actions |

## Project structure

```
kiwi-finance/
├── backend/        # Node.js API + Lambda handlers
├── mobile/         # React Native app (Android-first)
├── web/            # React.js web app
├── shared/         # Shared types, utils, constants
├── .env.example    # Environment variable reference
└── README.md
```

## Local setup

```bash
cp .env.example .env
# Fill in your values in .env — never commit .env

# Backend
cd backend
npm install
npm run dev

# Mobile
cd mobile
npm install
npx expo start

# Web
cd web
npm install
npm run dev
```

## Environment variables

See `.env.example` for all required variables. Never commit `.env`.

## Demo mode

This app runs in Plaid sandbox mode by default, using fake bank data safe for demos and portfolio review. Set `PLAID_ENV=production` in `.env` to connect real accounts (private use only).

## Related projects

- [Athenium](https://github.com/krisbrw/athenium) — Nashville data platform
- [Portfolio](https://krisbrw.github.io)
