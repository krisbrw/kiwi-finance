"""
Registers and runs the SQLite-to-RDS migration as a one-off ECS Fargate task.
Run from the project root:
    python scripts/run_migration_task.py
"""
import boto3
import json
import sys
import time

REGION        = "us-east-1"
INFRA_STACK   = "kiwi-finance-infra"
APP_STACK     = "kiwi-finance-app"
S3_SQLITE_URI = "s3://kiwi-finance-data-krisbro-314171434946/migration/kiwi_finance.db"

cf  = boto3.client("cloudformation", region_name=REGION)
ecs = boto3.client("ecs", region_name=REGION)
sts = boto3.client("sts", region_name=REGION)

account_id = sts.get_caller_identity()["Account"]
ecr_uri    = f"{account_id}.dkr.ecr.{REGION}.amazonaws.com/kiwi-finance-app:latest"


def get_output(stack, key):
    stacks = cf.describe_stacks(StackName=stack)["Stacks"][0]["Outputs"]
    return next(o["OutputValue"] for o in stacks if o["OutputKey"] == key)


def get_resource(stack, logical_id):
    resources = cf.describe_stack_resources(StackName=stack)["StackResources"]
    return next(r["PhysicalResourceId"] for r in resources if r["LogicalResourceId"] == logical_id)


print("Fetching stack outputs...")
subnet_a     = get_output(INFRA_STACK, "PrivateSubnetA")
sec_group    = get_output(INFRA_STACK, "AppSecurityGroup")
secret_arn   = get_output(APP_STACK,   "DatabaseUrlSecretArn")
cluster      = f"{APP_STACK}-cluster"
exec_role    = get_resource(APP_STACK, "ECSTaskExecutionRole")
task_role    = get_resource(APP_STACK, "ECSTaskRole")

print(f"  Subnet:    {subnet_a}")
print(f"  SecGroup:  {sec_group}")
print(f"  Secret:    {secret_arn}")
print(f"  Cluster:   {cluster}")

task_def = {
    "family": "kiwi-finance-migrate",
    "networkMode": "awsvpc",
    "requiresCompatibilities": ["FARGATE"],
    "cpu": "512",
    "memory": "1024",
    "executionRoleArn": exec_role,
    "taskRoleArn": task_role,
    "containerDefinitions": [{
        "name": "migrate",
        "image": ecr_uri,
        "essential": True,
        "command": ["python", "scripts/migrate_sqlite_to_rds.py"],
        "environment": [
            {"name": "DATABASE_URL_SECRET_ARN", "value": secret_arn},
            {"name": "SQLITE_S3_URI",           "value": S3_SQLITE_URI},
            {"name": "DATABASE_PATH",           "value": "/tmp/kiwi_finance.db"},
        ],
        "logConfiguration": {
            "logDriver": "awslogs",
            "options": {
                "awslogs-group":         "/ecs/kiwi-finance-migrate",
                "awslogs-region":        REGION,
                "awslogs-stream-prefix": "migrate",
            }
        }
    }]
}

print("\nRegistering task definition...")
resp = ecs.register_task_definition(**task_def)
task_def_arn = resp["taskDefinition"]["taskDefinitionArn"]
print(f"  Registered: {task_def_arn}")

print("\nStarting migration task...")
run = ecs.run_task(
    cluster=cluster,
    taskDefinition=task_def_arn,
    launchType="FARGATE",
    networkConfiguration={
        "awsvpcConfiguration": {
            "subnets": [subnet_a],
            "securityGroups": [sec_group],
            "assignPublicIp": "DISABLED",
        }
    }
)

if run.get("failures"):
    print(f"Failed to start task: {run['failures']}")
    sys.exit(1)

task_arn = run["tasks"][0]["taskArn"]
print(f"  Task ARN: {task_arn}")
print("\nWaiting for migration to complete (check CloudWatch logs for progress)...")

waiter = ecs.get_waiter("tasks_stopped")
waiter.wait(cluster=cluster, tasks=[task_arn])

desc     = ecs.describe_tasks(cluster=cluster, tasks=[task_arn])
exit_code = desc["tasks"][0]["containers"][0].get("exitCode")
reason    = desc["tasks"][0]["containers"][0].get("reason", "")

print()
if exit_code == 0:
    print("Migration completed successfully!")
else:
    print(f"Migration failed (exit code {exit_code}). Reason: {reason}")
    print(f"\nView logs:")
    print(f"  aws logs tail /ecs/kiwi-finance-migrate --region {REGION} --follow")
    sys.exit(1)
