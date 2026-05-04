# Runs the SQLite-to-RDS migration as a one-off ECS Fargate task inside the VPC.
# Usage: .\scripts\run_migration_task.ps1

$Region        = "us-east-1"
$InfraStack    = "kiwi-finance-infra"
$AppStack      = "kiwi-finance-app"
$AccountId     = (aws sts get-caller-identity --query Account --output text --region $Region).Trim()
$EcrUri        = "$AccountId.dkr.ecr.$Region.amazonaws.com/kiwi-finance-app:latest"
$S3SqliteUri   = "s3://kiwi-finance-data-krisbro-314171434946/migration/kiwi_finance.db"

$SubnetA       = (aws cloudformation describe-stacks --stack-name $InfraStack --region $Region --query "Stacks[0].Outputs[?OutputKey=='PrivateSubnetA'].OutputValue" --output text).Trim()
$SecGroup      = (aws cloudformation describe-stacks --stack-name $InfraStack --region $Region --query "Stacks[0].Outputs[?OutputKey=='AppSecurityGroup'].OutputValue" --output text).Trim()
$SecretArn     = (aws cloudformation describe-stacks --stack-name $AppStack --region $Region --query "Stacks[0].Outputs[?OutputKey=='DatabaseUrlSecretArn'].OutputValue" --output text).Trim()
$Cluster       = "$AppStack-cluster"
$ExecRoleArn   = (aws cloudformation describe-stack-resources --stack-name $AppStack --region $Region --query "StackResources[?LogicalResourceId=='ECSTaskExecutionRole'].PhysicalResourceId" --output text).Trim()
$TaskRoleArn   = (aws cloudformation describe-stack-resources --stack-name $AppStack --region $Region --query "StackResources[?LogicalResourceId=='ECSTaskRole'].PhysicalResourceId" --output text).Trim()

Write-Host "Subnet:   $SubnetA"
Write-Host "SecGroup: $SecGroup"
Write-Host "Secret:   $SecretArn"

# Use Python to write the JSON file cleanly (avoids PowerShell escaping issues)
$TempFile = "$env:TEMP\kiwi-migrate-taskdef.json"
python -c @"
import json, sys
d = {
    'family': 'kiwi-finance-migrate',
    'networkMode': 'awsvpc',
    'requiresCompatibilities': ['FARGATE'],
    'cpu': '512',
    'memory': '1024',
    'executionRoleArn': '$ExecRoleArn',
    'taskRoleArn': '$TaskRoleArn',
    'containerDefinitions': [{
        'name': 'migrate',
        'image': '$EcrUri',
        'essential': True,
        'command': ['python', 'scripts/migrate_sqlite_to_rds.py'],
        'environment': [
            {'name': 'DATABASE_URL_SECRET_ARN', 'value': '$SecretArn'},
            {'name': 'SQLITE_S3_URI', 'value': '$S3SqliteUri'},
            {'name': 'DATABASE_PATH', 'value': '/tmp/kiwi_finance.db'}
        ],
        'logConfiguration': {
            'logDriver': 'awslogs',
            'options': {
                'awslogs-group': '/ecs/kiwi-finance-migrate',
                'awslogs-region': '$Region',
                'awslogs-stream-prefix': 'migrate',
                'awslogs-create-group': 'true'
            }
        }
    }]
}
print(json.dumps(d))
"@ | Out-File -FilePath $TempFile -Encoding utf8 -NoNewline

Write-Host "Registering task definition..."
$TaskDefResult = aws ecs register-task-definition --cli-input-json file://$TempFile --region $Region --output json | ConvertFrom-Json
Remove-Item $TempFile -ErrorAction SilentlyContinue

if (-not $TaskDefResult) { throw "Failed to register task definition" }
$TaskDefArn = $TaskDefResult.taskDefinition.taskDefinitionArn
Write-Host "Registered: $TaskDefArn"

Write-Host "Starting migration task..."
$RunResult = aws ecs run-task `
    --cluster $Cluster `
    --task-definition $TaskDefArn `
    --launch-type FARGATE `
    --network-configuration "awsvpcConfiguration={subnets=[$SubnetA],securityGroups=[$SecGroup],assignPublicIp=DISABLED}" `
    --region $Region --output json | ConvertFrom-Json

if (-not $RunResult.tasks) { throw "Failed to start task: $($RunResult.failures)" }
$TaskArn = $RunResult.tasks[0].taskArn
Write-Host "Task ARN: $TaskArn"
Write-Host "Waiting for migration to complete..."

aws ecs wait tasks-stopped --cluster $Cluster --tasks $TaskArn --region $Region

$Describe = aws ecs describe-tasks --cluster $Cluster --tasks $TaskArn --region $Region --output json | ConvertFrom-Json
$ExitCode = $Describe.tasks[0].containers[0].exitCode

Write-Host ""
if ($ExitCode -eq 0) {
    Write-Host "Migration completed successfully!"
} else {
    Write-Host "Migration failed (exit code $ExitCode). Logs:"
    aws logs tail /ecs/kiwi-finance-migrate --region $Region
}
