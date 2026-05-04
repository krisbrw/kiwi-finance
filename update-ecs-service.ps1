#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Updates the ECS service with the latest Docker image
#>

$ErrorActionPreference = "Stop"

$REGION        = "us-east-1"
$APP_STACK     = "kiwi-finance-app"
$INFRA_STACK   = "kiwi-finance-infra"

$accountId = (aws sts get-caller-identity --query Account --output text --region $REGION).Trim()
$ecrUri    = "$accountId.dkr.ecr.$REGION.amazonaws.com/kiwi-finance-app:latest"

Write-Host "Getting stack outputs..."
$execRoleArn   = aws cloudformation describe-stacks --stack-name $APP_STACK --region $REGION --query "Stacks[0].Outputs[?OutputKey=='ECSTaskExecutionRoleArn'].OutputValue" --output text
$taskRoleArn   = aws cloudformation describe-stacks --stack-name $APP_STACK --region $REGION --query "Stacks[0].Outputs[?OutputKey=='ECSTaskRoleArn'].OutputValue" --output text
$clusterName   = aws cloudformation describe-stacks --stack-name $APP_STACK --region $REGION --query "Stacks[0].Outputs[?OutputKey=='ECSClusterName'].OutputValue" --output text
$logGroup      = aws cloudformation describe-stacks --stack-name $APP_STACK --region $REGION --query "Stacks[0].Outputs[?OutputKey=='AppLogGroupName'].OutputValue" --output text
$secretArn     = aws cloudformation describe-stacks --stack-name $APP_STACK --region $REGION --query "Stacks[0].Outputs[?OutputKey=='DatabaseUrlSecretArn'].OutputValue" --output text
$serviceName   = "$APP_STACK-app"

# Load environment variables from .env
$dotEnvPath = Join-Path $PSScriptRoot ".env"
$env_vars = @{}
if (Test-Path $dotEnvPath) {
    Get-Content $dotEnvPath | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#")) {
            $parts = $line -split "=", 2
            if ($parts.Count -eq 2) {
                $env_vars[$parts[0].Trim()] = $parts[1].Trim()
            }
        }
    }
}

$resolvedPlaidClientId      = $env_vars["PLAID_CLIENT_ID"]
$resolvedPlaidSecret        = $env_vars["PLAID_SECRET"]
$resolvedPlaidEnv           = if ($env_vars["PLAID_ENV"]) { $env_vars["PLAID_ENV"] } else { "production" }
$resolvedSecretKey          = $env_vars["SECRET_KEY"]
$resolvedExportBucket       = $env_vars["AWS_S3_BUCKET"]
$resolvedAccountsPrefix     = if ($env_vars["AWS_S3_ACCOUNTS_PREFIX"]) { $env_vars["AWS_S3_ACCOUNTS_PREFIX"] } else { "accounts" }
$resolvedTransactionsPrefix = if ($env_vars["AWS_S3_TRANSACTIONS_PREFIX"]) { $env_vars["AWS_S3_TRANSACTIONS_PREFIX"] } else { "transactions" }

Write-Host "  Cluster:   $clusterName"
Write-Host "  Service:   $serviceName"
Write-Host "  Image:     $ecrUri"

# Register new task definition using Python
Write-Host "`nRegistering task definition..."
$taskDefArn = python -c @"
import boto3, json
ecs = boto3.client('ecs', region_name='$REGION')
resp = ecs.register_task_definition(
    family='$APP_STACK-app',
    networkMode='awsvpc',
    requiresCompatibilities=['FARGATE'],
    cpu='512',
    memory='1024',
    executionRoleArn='$execRoleArn',
    taskRoleArn='$taskRoleArn',
    containerDefinitions=[{
        'name': 'app',
        'image': '$ecrUri',
        'essential': True,
        'portMappings': [{'containerPort': 8000, 'protocol': 'tcp'}],
        'logConfiguration': {
            'logDriver': 'awslogs',
            'options': {
                'awslogs-group': '$logGroup',
                'awslogs-region': '$REGION',
                'awslogs-stream-prefix': 'app'
            }
        },
        'environment': [
            {'name': 'PLAID_CLIENT_ID',            'value': '$resolvedPlaidClientId'},
            {'name': 'PLAID_SECRET',               'value': '$resolvedPlaidSecret'},
            {'name': 'PLAID_ENV',                  'value': '$resolvedPlaidEnv'},
            {'name': 'SECRET_KEY',                 'value': '$resolvedSecretKey'},
            {'name': 'AWS_S3_BUCKET',              'value': '$resolvedExportBucket'},
            {'name': 'AWS_S3_ACCOUNTS_PREFIX',     'value': '$resolvedAccountsPrefix'},
            {'name': 'AWS_S3_TRANSACTIONS_PREFIX', 'value': '$resolvedTransactionsPrefix'},
            {'name': 'DATABASE_URL_SECRET_ARN',    'value': '$secretArn'},
        ]
    }]
)
print(resp['taskDefinition']['taskDefinitionArn'])
"@

if ($LASTEXITCODE -ne 0) {
    throw "Failed to register task definition"
}

Write-Host "  Task definition: $taskDefArn"

# Update the service
Write-Host "`nUpdating ECS service..."
aws ecs update-service `
    --cluster $clusterName `
    --service $serviceName `
    --task-definition $taskDefArn `
    --force-new-deployment `
    --region $REGION | Out-Null

if ($LASTEXITCODE -ne 0) {
    throw "Failed to update ECS service"
}

Write-Host "`nECS service updated successfully!"
Write-Host "Monitor deployment: https://console.aws.amazon.com/ecs/home?region=$REGION#/clusters/$clusterName/services/$serviceName"
Write-Host "`nCheck service status:"
Write-Host "  aws ecs describe-services --cluster $clusterName --services $serviceName --region $REGION --query 'services[0].{runningCount:runningCount,desiredCount:desiredCount}'"
