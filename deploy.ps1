[CmdletBinding()]
param(
    [string]$InfraStackName = "kiwi-finance-infra",
    [string]$AppStackName   = "kiwi-finance-app",
    [string]$Region         = "us-east-1",
    [Parameter(Mandatory = $true)]
    [string]$ArtifactBucket,
    [string]$ArtifactPrefix        = "artifacts/kiwi-finance",
    [string]$ScheduleExpression    = "cron(0 13 * * ? *)",
    [string]$PlaidClientId,
    [string]$PlaidSecret,
    [string]$PlaidEnv,
    [string]$ExportBucket,
    [string]$AccountsPrefix,
    [string]$TransactionsPrefix,
    [string]$SecretKey,
    [string]$DBName,
    [string]$DBUsername,
    [string]$DomainName            = "mykiwifinance.com",
    [string]$CertificateArn,
    [switch]$InfraOnly,
    [switch]$AppOnly
)

$ErrorActionPreference = "Stop"

function Read-DotEnv {
    param([string]$Path)
    $values = @{}
    if (-not (Test-Path -LiteralPath $Path)) { return $values }
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
        $parts = $trimmed -split "=", 2
        if ($parts.Count -ne 2) { continue }
        $values[$parts[0].Trim()] = $parts[1].Trim()
    }
    return $values
}

function Resolve-Setting {
    param(
        [string]$Name,
        [AllowEmptyString()][string]$ExplicitValue,
        [hashtable]$DotEnvValues,
        [AllowEmptyString()][string]$FallbackValue,
        [switch]$Required
    )
    if ($null -ne $ExplicitValue -and $ExplicitValue -ne "") { return $ExplicitValue }
    if ($DotEnvValues.ContainsKey($Name) -and $DotEnvValues[$Name] -ne "") { return $DotEnvValues[$Name] }
    if ($null -ne $FallbackValue -and $FallbackValue -ne "") { return $FallbackValue }
    if ($Required) { throw "Missing required setting: $Name" }
    return $null
}

$projectRoot  = Split-Path -Parent $MyInvocation.MyCommand.Path
$buildRoot    = Join-Path $projectRoot "build"
$packageRoot  = Join-Path $buildRoot "package"
$zipPath      = Join-Path $buildRoot "kiwi-finance-lambda.zip"
$dotEnvPath   = Join-Path $projectRoot ".env"
$env          = Read-DotEnv -Path $dotEnvPath

$resolvedPlaidClientId      = Resolve-Setting -Name "PLAID_CLIENT_ID"            -ExplicitValue $PlaidClientId      -DotEnvValues $env -Required
$resolvedPlaidSecret        = Resolve-Setting -Name "PLAID_SECRET"               -ExplicitValue $PlaidSecret        -DotEnvValues $env -Required
$resolvedPlaidEnv           = Resolve-Setting -Name "PLAID_ENV"                  -ExplicitValue $PlaidEnv           -DotEnvValues $env -FallbackValue "production"
$resolvedExportBucket       = Resolve-Setting -Name "AWS_S3_BUCKET"              -ExplicitValue $ExportBucket       -DotEnvValues $env -Required
$resolvedAccountsPrefix     = Resolve-Setting -Name "AWS_S3_ACCOUNTS_PREFIX"     -ExplicitValue $AccountsPrefix     -DotEnvValues $env -FallbackValue "accounts"
$resolvedTransactionsPrefix = Resolve-Setting -Name "AWS_S3_TRANSACTIONS_PREFIX" -ExplicitValue $TransactionsPrefix -DotEnvValues $env -FallbackValue "transactions"
$resolvedSecretKey          = Resolve-Setting -Name "SECRET_KEY"                 -ExplicitValue $SecretKey          -DotEnvValues $env -Required
$resolvedDBName             = Resolve-Setting -Name "DB_NAME"                    -ExplicitValue $DBName             -DotEnvValues $env -FallbackValue "kiwifinance"
$resolvedDBUsername         = Resolve-Setting -Name "DB_USERNAME"                -ExplicitValue $DBUsername         -DotEnvValues $env -FallbackValue "kiwidbadmin"
$resolvedCertArn            = Resolve-Setting -Name "CERTIFICATE_ARN"            -ExplicitValue $CertificateArn     -DotEnvValues $env -Required

$accountId = (aws sts get-caller-identity --query Account --output text --region $Region).Trim()
$ecrUri    = "$accountId.dkr.ecr.$Region.amazonaws.com/kiwi-finance-app"

# =============================================================================
# STAGE 1 - Infrastructure
# =============================================================================
if (-not $AppOnly) {
    Write-Host ""
    Write-Host "=== STAGE 1: Infrastructure stack '$InfraStackName' ==="
    aws cloudformation deploy `
        --template-file (Join-Path $projectRoot "infra\kiwi-finance-infra.yaml") `
        --stack-name $InfraStackName `
        --region $Region `
        --capabilities CAPABILITY_IAM `
        --no-fail-on-empty-changeset `
        --parameter-overrides `
            DomainName=$DomainName `
            CertificateArn=$resolvedCertArn `
            DBName=$resolvedDBName `
            DBUsername=$resolvedDBUsername
    if ($LASTEXITCODE -ne 0) { throw "Infrastructure stack deployment failed." }
    Write-Host "Infrastructure stack deployed."
}
if ($InfraOnly) { exit 0 }

# =============================================================================
# STAGE 2 - Docker image
# =============================================================================
Write-Host ""
Write-Host "=== STAGE 2: Building and pushing Docker image ==="
aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin "$accountId.dkr.ecr.$Region.amazonaws.com"
$imageTag       = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$imageUri       = "${ecrUri}:${imageTag}"
$imageUriLatest = "${ecrUri}:latest"
docker build -t $imageUri -t $imageUriLatest $projectRoot
docker push $imageUri
docker push $imageUriLatest
Write-Host "Image pushed: $imageUri"

# =============================================================================
# STAGE 3 - Lambda package
# =============================================================================
# STAGE 3 - Lambda package
# =============================================================================
Write-Host ""
Write-Host "=== STAGE 3: Lambda package ==="
if (Test-Path -LiteralPath $packageRoot) { Remove-Item -LiteralPath $packageRoot -Recurse -Force }
if (Test-Path -LiteralPath $zipPath)     { Remove-Item -LiteralPath $zipPath -Force }
New-Item -ItemType Directory -Path $packageRoot -Force | Out-Null
Write-Host "Installing Python dependencies for Linux Lambda environment..."
python -m pip install -r (Join-Path $projectRoot "requirements.txt") -t $packageRoot --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 --only-binary=:all: --upgrade --no-cache-dir
Copy-Item -LiteralPath (Join-Path $projectRoot "app") -Destination $packageRoot -Recurse
Copy-Item -LiteralPath (Join-Path $projectRoot "lambda_function.py") -Destination $packageRoot
Compress-Archive -Path (Join-Path $packageRoot "*") -DestinationPath $zipPath -Force
$timestamp   = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$artifactKey = "$ArtifactPrefix/$AppStackName-$timestamp.zip"
aws s3 cp $zipPath "s3://$ArtifactBucket/$artifactKey" --region $Region
Write-Host "Lambda package: s3://$ArtifactBucket/$artifactKey"

# =============================================================================
# STAGE 4 - CloudFormation app stack (IAM, Lambda, ECS cluster only)
# =============================================================================
Write-Host ""
Write-Host "=== STAGE 4: App stack (IAM, Lambda, ECS cluster) ==="
aws cloudformation deploy `
    --template-file (Join-Path $projectRoot "infra\kiwi-finance-app.yaml") `
    --stack-name $AppStackName `
    --region $Region `
    --capabilities CAPABILITY_IAM `
    --no-fail-on-empty-changeset `
    --parameter-overrides `
        InfraStackName=$InfraStackName `
        CodeBucket=$ArtifactBucket `
        CodeKey=$artifactKey `
        PlaidClientId=$resolvedPlaidClientId `
        PlaidSecret=$resolvedPlaidSecret `
        PlaidEnv=$resolvedPlaidEnv `
        SecretKey=$resolvedSecretKey `
        ExportBucket=$resolvedExportBucket `
        AccountsPrefix=$resolvedAccountsPrefix `
        TransactionsPrefix=$resolvedTransactionsPrefix `
        DBName=$resolvedDBName `
        DBUsername=$resolvedDBUsername `
        ScheduleExpression=$ScheduleExpression
if ($LASTEXITCODE -ne 0) { throw "App stack deployment failed." }
Write-Host "App stack deployed."

# =============================================================================
# STAGE 5 - ECS task definition + service (managed outside CloudFormation)
# =============================================================================
Write-Host ""
Write-Host "=== STAGE 5: Deploying ECS service ==="

# Get stack outputs
$secretArn     = aws cloudformation describe-stacks --stack-name $AppStackName --region $Region --query "Stacks[0].Outputs[?OutputKey=='DatabaseUrlSecretArn'].OutputValue" --output text
$execRoleArn   = aws cloudformation describe-stacks --stack-name $AppStackName --region $Region --query "Stacks[0].Outputs[?OutputKey=='ECSTaskExecutionRoleArn'].OutputValue" --output text
$taskRoleArn   = aws cloudformation describe-stacks --stack-name $AppStackName --region $Region --query "Stacks[0].Outputs[?OutputKey=='ECSTaskRoleArn'].OutputValue" --output text
$clusterName   = aws cloudformation describe-stacks --stack-name $AppStackName --region $Region --query "Stacks[0].Outputs[?OutputKey=='ECSClusterName'].OutputValue" --output text
$logGroup      = aws cloudformation describe-stacks --stack-name $AppStackName --region $Region --query "Stacks[0].Outputs[?OutputKey=='AppLogGroupName'].OutputValue" --output text
$subnetA       = aws cloudformation describe-stacks --stack-name $InfraStackName --region $Region --query "Stacks[0].Outputs[?OutputKey=='PrivateSubnetA'].OutputValue" --output text
$subnetB       = aws cloudformation describe-stacks --stack-name $InfraStackName --region $Region --query "Stacks[0].Outputs[?OutputKey=='PrivateSubnetB'].OutputValue" --output text
$secGroup      = aws cloudformation describe-stacks --stack-name $InfraStackName --region $Region --query "Stacks[0].Outputs[?OutputKey=='AppSecurityGroup'].OutputValue" --output text
$targetGroupArn = aws cloudformation describe-stacks --stack-name $InfraStackName --region $Region --query "Stacks[0].Outputs[?OutputKey=='ALBTargetGroupArn'].OutputValue" --output text
$serviceName   = "$AppStackName-app"

# Register task definition via Python (avoids PowerShell JSON escaping issues)
Write-Host "Registering task definition..."
$taskDefArn = python -c @"
import boto3, json, sys
ecs = boto3.client('ecs', region_name='$Region')
resp = ecs.register_task_definition(
    family='$AppStackName-app',
    networkMode='awsvpc',
    requiresCompatibilities=['FARGATE'],
    cpu='512',
    memory='1024',
    executionRoleArn='$execRoleArn',
    taskRoleArn='$taskRoleArn',
    containerDefinitions=[{
        'name': 'app',
        'image': '$imageUri',
        'essential': True,
        'portMappings': [{'containerPort': 8000, 'protocol': 'tcp'}],
        'logConfiguration': {
            'logDriver': 'awslogs',
            'options': {
                'awslogs-group': '$logGroup',
                'awslogs-region': '$Region',
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
Write-Host "Task definition: $taskDefArn"

# Create or update ECS service
$ErrorActionPreference = "Continue"
$existingService = aws ecs describe-services --cluster $clusterName --services $serviceName --region $Region --query "services[?status=='ACTIVE'].serviceName" --output text 2>$null
$ErrorActionPreference = "Stop"

if ($existingService -eq $serviceName) {
    Write-Host "Updating existing ECS service..."
    aws ecs update-service `
        --cluster $clusterName `
        --service $serviceName `
        --task-definition $taskDefArn `
        --force-new-deployment `
        --region $Region | Out-Null
} else {
    Write-Host "Creating ECS service..."
    aws ecs create-service `
        --cluster $clusterName `
        --service-name $serviceName `
        --task-definition $taskDefArn `
        --desired-count 1 `
        --launch-type FARGATE `
        --network-configuration "awsvpcConfiguration={subnets=[$subnetA,$subnetB],securityGroups=[$secGroup],assignPublicIp=DISABLED}" `
        --load-balancers "targetGroupArn=$targetGroupArn,containerName=app,containerPort=8000" `
        --health-check-grace-period-seconds 120 `
        --region $Region | Out-Null
}

Write-Host "ECS service deployment triggered."
Write-Host "Monitor: https://console.aws.amazon.com/ecs/home?region=$Region#/clusters/$clusterName/services"

# =============================================================================
# Done
# =============================================================================
Write-Host ""
Write-Host "Deploy complete. ECS is rolling out the new container in the background."
Write-Host "Once healthy, run: python scripts/run_migration_task.py"
Write-Host "Then visit: https://mykiwifinance.com"
