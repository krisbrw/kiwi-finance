# Kiwi Finance

Kiwi Finance is a small local data pipeline for pulling financial data from Plaid sandbox, storing it in a local SQLite database, and exporting that data to Amazon S3.

This project is useful if you want to practice an end-to-end workflow that looks like:

1. Source system API
2. Local ingestion app
3. Local relational storage
4. Cloud object storage
5. Future analytics layer such as Athena or Redshift

The app is written in Python with Flask and is designed for local development.

## What This Project Does

At a high level, the workflow is:

1. Start the local Flask app
2. Open the browser UI and connect a Plaid sandbox account
3. Fetch account and transaction data from Plaid
4. Save that data into a local SQLite database
5. Export the saved data to an S3 bucket as CSV files

Today, the project supports:

- Connecting a Plaid sandbox account
- Creating a dynamic sandbox Item for recurring transaction practice
- Saving Plaid item credentials locally
- Fetching accounts into SQLite
- Fetching transactions into SQLite with a saved sync cursor
- Simulating new sandbox transactions each day
- Exporting accounts to S3 as CSV
- Exporting transactions to S3 as CSV

## Project Structure

```text
kiwi-finance/
|-- run.py
|-- requirements.txt
|-- data/
|   `-- kiwi_finance.db
`-- app/
    `-- kiwi_finance/
        |-- main.py
        |-- database.py
        |-- plaid_client.py
        |-- config.py
        |-- s3_export.py
        `-- templates/
            `-- index.html
```

Key files:

- `run.py`: local entrypoint that starts the Flask app
- `app/kiwi_finance/main.py`: Flask routes for UI, Plaid calls, local reads, and S3 export
- `app/kiwi_finance/database.py`: SQLite connection, table creation, and local persistence helpers
- `app/kiwi_finance/plaid_client.py`: Plaid API client setup and Plaid API calls
- `app/kiwi_finance/s3_export.py`: CSV export and S3 upload logic
- `app/kiwi_finance/config.py`: environment-variable-based configuration

## Data Flow

The project currently moves data through these layers:

```text
Plaid Sandbox -> Flask App -> SQLite -> S3
```

More specifically:

1. Plaid Link in the browser returns a `public_token`
2. The app exchanges that token for an `access_token`
3. The `access_token` is stored in the `plaid_items` table
4. The app uses the `access_token` to call Plaid for accounts and transactions
5. Accounts are stored in the `accounts` table
6. A transactions sync cursor is stored in the `sync_state` table
7. Transactions are stored in the `transactions` table
8. Local rows are converted to CSV and uploaded to S3

## Prerequisites

Before running the project, you should have:

- Python installed
- A Plaid developer account and sandbox credentials
- An AWS account
- AWS CLI installed
- An S3 bucket you can write to

You should also have local AWS CLI credentials working. A quick check is:

```powershell
aws sts get-caller-identity
```

If that returns your `UserId`, `Account`, and `Arn`, your CLI credentials are working.

## Installation

Install Python dependencies from the project root:

```powershell
pip install -r requirements.txt
```

## Environment Configuration

Create a `.env` file in the project root.

Example:

```dotenv
PLAID_CLIENT_ID=your_plaid_client_id
PLAID_SECRET=your_plaid_secret
PLAID_ENV=sandbox

AWS_S3_BUCKET=kiwi-finance-data-krisbro-314171434946
AWS_S3_TRANSACTIONS_PREFIX=transactions
AWS_S3_ACCOUNTS_PREFIX=accounts
```

Notes:

- `PLAID_ENV` should be `sandbox` for local testing
- `AWS_S3_BUCKET` is the bucket used for exports
- the S3 prefixes default to `transactions` and `accounts` if not set
- `DATABASE_PATH` is optional for local development, but useful in AWS Lambda where the writable path should be `/tmp/kiwi_finance.db`
- `AWS_STATE_BUCKET` and `AWS_STATE_KEY` let you persist the SQLite database snapshot between AWS runs

## How To Start The App

From the project root, run:

```powershell
python run.py
```

What this does:

- adds the `app/` directory to Python's import path
- initializes the SQLite database if it does not exist
- starts the Flask development server

By default, Flask runs locally at:

```text
http://127.0.0.1:5000
```

## Exact Workflow

This is the recommended end-to-end workflow for the project.

### Step 1: Start the app

Run:

```powershell
python run.py
```

Then open:

```text
http://127.0.0.1:5000
```

### Step 2: Connect a Plaid sandbox account

On the homepage, click:

`Connect a bank account`

This opens Plaid Link in the browser. Complete the sandbox prompts using Plaid's fake data flow.

What happens behind the scenes:

- the app calls `/create_link_token`
- Plaid returns a temporary link token
- after the sandbox flow completes, Plaid returns a `public_token`
- the app calls `/exchange_public_token`
- the app stores the resulting `access_token` locally in SQLite

At this point, you are connected, but you have not necessarily saved accounts or transactions yet.

If you want to skip the browser flow while staying in sandbox, you can also use:

```text
http://127.0.0.1:5000/sandbox_connect
```

That route creates a sandbox Item using Plaid's dynamic transactions profile and saves the resulting access token automatically.

### Step 3: Fetch accounts from Plaid

Open this route in the browser:

```text
http://127.0.0.1:5000/accounts
```

What this does:

- reads the stored Plaid `access_token`
- calls Plaid's accounts API
- saves the returned account records into the local `accounts` table

To view the locally saved account data:

```text
http://127.0.0.1:5000/local_accounts
```

### Step 4: Fetch transactions from Plaid

Open this route in the browser:

```text
http://127.0.0.1:5000/transactions
```

What this does:

- reads the stored Plaid `access_token`
- reads the last saved transaction sync cursor
- calls Plaid's transactions sync API incrementally
- saves added and modified transaction records into the local `transactions` table
- removes deleted transactions from the local `transactions` table
- stores the latest cursor for the next run

To view the locally saved transaction data:

```text
http://127.0.0.1:5000/local_transactions
```

### Step 5: Export accounts to S3

Open this route in the browser:

```text
http://127.0.0.1:5000/export_accounts_to_s3
```

What this does:

- reads all rows from the local `accounts` table
- converts them to CSV in memory
- uploads the CSV to the configured S3 bucket

The uploaded key will look like:

```text
accounts/accounts_YYYYMMDDTHHMMSSZ.csv
```

### Step 6: Export transactions to S3

Open this route in the browser:

```text
http://127.0.0.1:5000/export_transactions_to_s3
```

What this does:

- reads all rows from the local `transactions` table
- converts them to CSV in memory
- uploads the CSV to the configured S3 bucket

The uploaded key will look like:

```text
transactions/transactions_YYYYMMDDTHHMMSSZ.csv
```

## Daily Sandbox Practice Workflow

If your goal is to practice a production-like daily pipeline with new data showing up over time, use this workflow instead of manually reconnecting each day.

### Option 1: One-click daily pipeline

Open:

```text
http://127.0.0.1:5000/run_daily_sandbox_pipeline
```

What this does:

- ensures a sandbox Item exists
- fetches accounts
- creates new synthetic sandbox transactions for today
- runs an incremental `/transactions/sync`
- exports accounts to S3
- exports transactions to S3

This is the easiest route to schedule later with Task Scheduler.

### Option 2: Manual daily sequence

If you want to see each step separately, run these in order:

1. `/sandbox_connect` once, or whenever you need a new sandbox Item
2. `/simulate_daily_transactions`
3. `/transactions`
4. `/export_transactions_to_s3`

You can also include `/accounts` and `/export_accounts_to_s3`, but account data is usually much more static in sandbox than transactions.

## AWS Automation

If your goal is to run this automatically every day in sandbox mode, the cleanest setup for the current codebase is:

```text
EventBridge Rule -> Lambda -> /tmp SQLite -> S3 exports + S3 state snapshot
```

There is now a one-command deployment path for this setup:

```powershell
.\deploy.ps1 -ArtifactBucket your-lambda-artifact-bucket
```

That command:

- reads Plaid and S3 settings from your local `.env`
- installs Lambda dependencies into a build folder
- zips the app
- uploads the zip to your artifact bucket
- deploys the CloudFormation stack
- creates or updates the Lambda, IAM roles, and daily EventBridge schedule

Why this shape works:

- Lambda is a good fit for a short daily batch job
- EventBridge Scheduler is AWS's managed scheduler for cron-like jobs
- Lambda only has writable temporary disk space, so the app should use `/tmp/kiwi_finance.db`
- to preserve the Plaid access token and transactions sync cursor across daily runs, the SQLite file is restored from S3 at the start of the run and uploaded back to S3 at the end

Files added for AWS execution:

- `lambda_function.py`: headless Lambda entrypoint for the daily sandbox pipeline
- `app/kiwi_finance/pipeline.py`: reusable daily job logic shared by Flask routes and Lambda
- `app/kiwi_finance/state_store.py`: downloads and uploads the SQLite snapshot to S3
- `infra/kiwi-finance.yaml`: CloudFormation template for the Lambda, IAM, and EventBridge rule
- `deploy.ps1`: one-command package, upload, and deploy script

Recommended Lambda environment variables:

```dotenv
PLAID_CLIENT_ID=your_plaid_client_id
PLAID_SECRET=your_plaid_secret
PLAID_ENV=sandbox
KIWI_USER_ID=aws-sandbox-user

AWS_S3_BUCKET=kiwi-finance-data-krisbro-314171434946
AWS_S3_ACCOUNTS_PREFIX=accounts
AWS_S3_TRANSACTIONS_PREFIX=transactions

DATABASE_PATH=/tmp/kiwi_finance.db
AWS_STATE_BUCKET=kiwi-finance-data-krisbro-314171434946
AWS_STATE_KEY=state/kiwi_finance.db
```

The Lambda handler is:

```text
lambda_function.lambda_handler
```

### One-Command Deployment

Before running the deploy command:

- make sure your local `.env` has valid `PLAID_CLIENT_ID`, `PLAID_SECRET`, and `AWS_S3_BUCKET`
- make sure the artifact bucket already exists
- make sure your AWS CLI is authenticated in the target account

From the project root, run:

```powershell
.\deploy.ps1 -ArtifactBucket your-lambda-artifact-bucket
```

Common optional parameters:

```powershell
.\deploy.ps1 `
  -ArtifactBucket your-lambda-artifact-bucket `
  -StackName kiwi-finance `
  -Region us-east-2 `
  -ScheduleExpression "cron(0 13 * * ? *)"
```

What each setting means:

- `ArtifactBucket`: where the packaged Lambda zip is uploaded before CloudFormation deploys it
- `StackName`: the CloudFormation stack name
- `Region`: the AWS region for the stack
- `ScheduleExpression`: the EventBridge cron or rate expression, interpreted in UTC

The deploy script reads these from `.env` by default:

- `PLAID_CLIENT_ID`
- `PLAID_SECRET`
- `PLAID_ENV`
- `KIWI_USER_ID`
- `AWS_S3_BUCKET`
- `AWS_S3_ACCOUNTS_PREFIX`
- `AWS_S3_TRANSACTIONS_PREFIX`
- `AWS_STATE_BUCKET`
- `AWS_STATE_KEY`

If needed, you can override any of those with explicit script parameters.

### What The Lambda Job Does

On each invocation it:

1. downloads the latest SQLite snapshot from `AWS_STATE_BUCKET/AWS_STATE_KEY` if it exists
2. initializes any missing tables
3. ensures a Plaid sandbox Item exists
4. fetches accounts into SQLite
5. creates today's synthetic sandbox transactions
6. runs incremental `/transactions/sync`
7. exports accounts and transactions to S3 as CSV
8. uploads the updated SQLite database back to S3

### CloudFormation Resources

The CloudFormation stack creates:

- a Python 3.12 Lambda function using `lambda_function.lambda_handler`
- a Lambda execution role with CloudWatch Logs and S3 access
- a daily EventBridge rule
- a Lambda invoke permission for EventBridge

The Lambda starts with:

- timeout: 60 seconds
- memory: 512 MB

### Scheduling

This template uses an EventBridge rule with a cron expression in UTC.

If you want a concrete example, a once-daily UTC schedule looks like:

```text
cron(0 13 * * ? *)
```

That example runs once per day at 13:00 UTC.

### Important Limitation

This SQLite-in-S3 pattern is a practical fit for a single daily sandbox job. It is not the right long-term design for concurrent writers or higher-scale production use.

If you later want to harden this for production, the next step would be moving the persistent state out of SQLite and into managed AWS storage such as DynamoDB or RDS.

## Available Routes

Main routes in the app:

- `/`: homepage with the Plaid Link button
- `/create_link_token`: creates a Plaid Link token
- `/exchange_public_token`: exchanges a Plaid public token for an access token
- `/accounts`: fetches accounts from Plaid and stores them locally
- `/local_accounts`: returns locally stored accounts
- `/transactions`: fetches transactions from Plaid and stores them locally
- `/local_transactions`: returns locally stored transactions
- `/sandbox_connect`: creates and connects a dynamic Plaid sandbox item without going through the full browser UI
- `/simulate_daily_transactions`: creates new synthetic transactions in the sandbox Item for the current day
- `/run_daily_sandbox_pipeline`: runs the daily sandbox workflow end to end
- `/export_accounts_to_s3`: uploads local accounts to S3 as CSV
- `/export_transactions_to_s3`: uploads local transactions to S3 as CSV

## Local Storage

The local SQLite database lives at:

```text
data/kiwi_finance.db
```

Current tables:

- `plaid_items`
- `accounts`
- `transactions`
- `sync_state`

You can inspect the database with any SQLite client, or by adding simple Python queries.

## S3 Output

Your configured bucket is:

```text
kiwi-finance-data-krisbro-314171434946
```

Current export pattern:

- `accounts/accounts_YYYYMMDDTHHMMSSZ.csv`
- `transactions/transactions_YYYYMMDDTHHMMSSZ.csv`

This is a good starting point for raw landed data. A future improvement would be partitioned paths such as:

- `transactions/year=2026/month=03/transactions_...csv`
- `accounts/year=2026/month=03/accounts_...csv`

That structure would be more convenient for Athena later.

## Common Commands

Start the app:

```powershell
python run.py
```

Check AWS CLI auth:

```powershell
aws sts get-caller-identity
```

List the S3 bucket:

```powershell
aws s3 ls s3://kiwi-finance-data-krisbro-314171434946
```

## Troubleshooting

### Missing Plaid credentials

If the app fails at startup with a message about missing Plaid credentials, check that your `.env` file contains:

- `PLAID_CLIENT_ID`
- `PLAID_SECRET`

### No access token found

If `/accounts` or `/transactions` returns:

```text
{"error": "No access token found"}
```

you need to reconnect a Plaid sandbox account first from the homepage, or use `/sandbox_connect`.

### S3 export fails

If an S3 export fails:

1. confirm AWS CLI auth works with `aws sts get-caller-identity`
2. confirm your bucket name is correct in `.env`
3. confirm your IAM user or role has `s3:PutObject` permission
4. confirm the bucket exists

### No rows exported

If an export route says there is no data:

- fetch accounts through `/accounts`
- fetch transactions through `/transactions`

The export routes only upload data already stored in the local SQLite database.

## Suggested Next Steps

If you want to keep building this project, strong next steps would be:

- add buttons on the homepage for fetch and export actions
- write data to Parquet instead of CSV
- organize S3 paths with partitions
- create Athena tables on top of the S3 data
- separate route logic from business logic as the app grows

## Summary

Kiwi Finance is currently a local ingestion and export workflow:

- Plaid sandbox is the source
- Flask is the orchestration layer
- SQLite is the local storage layer
- S3 is the cloud landing zone

That makes it a nice practice project for moving from API ingestion toward analytics-ready cloud storage.
