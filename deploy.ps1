[CmdletBinding()]
param(
    [string]$StackName = "kiwi-finance",
    [string]$Region = "us-east-2",
    [Parameter(Mandatory = $true)]
    [string]$ArtifactBucket,
    [string]$ArtifactPrefix = "artifacts/kiwi-finance",
    [string]$ScheduleExpression = "cron(0 13 * * ? *)",
    [string]$PlaidClientId,
    [string]$PlaidSecret,
    [string]$PlaidEnv,
    [string]$ExportBucket,
    [string]$AccountsPrefix,
    [string]$TransactionsPrefix,
    [string]$StateBucket,
    [string]$StateKey,
    [string]$KiwiUserId
)

$ErrorActionPreference = "Stop"

function Read-DotEnv {
    param(
        [string]$Path
    )

    $values = @{}

    if (-not (Test-Path -LiteralPath $Path)) {
        return $values
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }

        $parts = $trimmed -split "=", 2
        if ($parts.Count -ne 2) {
            continue
        }

        $values[$parts[0].Trim()] = $parts[1].Trim()
    }

    return $values
}

function Resolve-Setting {
    param(
        [string]$Name,
        [AllowEmptyString()]
        [string]$ExplicitValue,
        [hashtable]$DotEnvValues,
        [AllowEmptyString()]
        [string]$FallbackValue,
        [switch]$Required
    )

    if ($null -ne $ExplicitValue -and $ExplicitValue -ne "") {
        return $ExplicitValue
    }

    if ($DotEnvValues.ContainsKey($Name) -and $DotEnvValues[$Name] -ne "") {
        return $DotEnvValues[$Name]
    }

    if ($null -ne $FallbackValue -and $FallbackValue -ne "") {
        return $FallbackValue
    }

    if ($Required) {
        throw "Missing required setting: $Name. Pass it as a script parameter or add it to .env."
    }

    return $null
}

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$buildRoot = Join-Path $projectRoot "build"
$packageRoot = Join-Path $buildRoot "package"
$zipPath = Join-Path $buildRoot "kiwi-finance-lambda.zip"
$templatePath = Join-Path $projectRoot "infra\kiwi-finance.yaml"
$dotEnvPath = Join-Path $projectRoot ".env"
$dotEnvValues = Read-DotEnv -Path $dotEnvPath

$resolvedPlaidClientId = Resolve-Setting -Name "PLAID_CLIENT_ID" -ExplicitValue $PlaidClientId -DotEnvValues $dotEnvValues -FallbackValue $null -Required
$resolvedPlaidSecret = Resolve-Setting -Name "PLAID_SECRET" -ExplicitValue $PlaidSecret -DotEnvValues $dotEnvValues -FallbackValue $null -Required
$resolvedPlaidEnv = Resolve-Setting -Name "PLAID_ENV" -ExplicitValue $PlaidEnv -DotEnvValues $dotEnvValues -FallbackValue "sandbox"
$resolvedExportBucket = Resolve-Setting -Name "AWS_S3_BUCKET" -ExplicitValue $ExportBucket -DotEnvValues $dotEnvValues -FallbackValue $null -Required
$resolvedAccountsPrefix = Resolve-Setting -Name "AWS_S3_ACCOUNTS_PREFIX" -ExplicitValue $AccountsPrefix -DotEnvValues $dotEnvValues -FallbackValue "accounts"
$resolvedTransactionsPrefix = Resolve-Setting -Name "AWS_S3_TRANSACTIONS_PREFIX" -ExplicitValue $TransactionsPrefix -DotEnvValues $dotEnvValues -FallbackValue "transactions"
$resolvedStateBucket = Resolve-Setting -Name "AWS_STATE_BUCKET" -ExplicitValue $StateBucket -DotEnvValues $dotEnvValues -FallbackValue $resolvedExportBucket
$resolvedStateKey = Resolve-Setting -Name "AWS_STATE_KEY" -ExplicitValue $StateKey -DotEnvValues $dotEnvValues -FallbackValue "state/kiwi_finance.db"
$resolvedKiwiUserId = Resolve-Setting -Name "KIWI_USER_ID" -ExplicitValue $KiwiUserId -DotEnvValues $dotEnvValues -FallbackValue "aws-sandbox-user"

if (Test-Path -LiteralPath $packageRoot) {
    Remove-Item -LiteralPath $packageRoot -Recurse -Force
}

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

New-Item -ItemType Directory -Path $packageRoot -Force | Out-Null

Write-Host "Installing Python dependencies into build package..."
& python -m pip install -r (Join-Path $projectRoot "requirements.txt") -t $packageRoot

Write-Host "Copying application files..."
Copy-Item -LiteralPath (Join-Path $projectRoot "app") -Destination $packageRoot -Recurse
Copy-Item -LiteralPath (Join-Path $projectRoot "lambda_function.py") -Destination $packageRoot

Write-Host "Creating deployment zip..."
Compress-Archive -Path (Join-Path $packageRoot "*") -DestinationPath $zipPath -Force

$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$artifactKey = "$ArtifactPrefix/$StackName-$timestamp.zip"

Write-Host "Uploading package to s3://$ArtifactBucket/$artifactKey ..."
& aws s3 cp $zipPath "s3://$ArtifactBucket/$artifactKey" --region $Region

Write-Host "Deploying CloudFormation stack $StackName ..."
& aws cloudformation deploy `
    --template-file $templatePath `
    --stack-name $StackName `
    --region $Region `
    --capabilities CAPABILITY_IAM `
    --parameter-overrides `
        CodeBucket=$ArtifactBucket `
        CodeKey=$artifactKey `
        PlaidClientId=$resolvedPlaidClientId `
        PlaidSecret=$resolvedPlaidSecret `
        PlaidEnv=$resolvedPlaidEnv `
        KiwiUserId=$resolvedKiwiUserId `
        ExportBucket=$resolvedExportBucket `
        AccountsPrefix=$resolvedAccountsPrefix `
        TransactionsPrefix=$resolvedTransactionsPrefix `
        StateBucket=$resolvedStateBucket `
        StateKey=$resolvedStateKey `
        ScheduleExpression=$ScheduleExpression

if ($LASTEXITCODE -ne 0) {
    throw "CloudFormation deployment failed."
}

Write-Host ""
Write-Host "Deployment complete."
Write-Host "Stack name: $StackName"
Write-Host "Region: $Region"
Write-Host "Artifact package: s3://$ArtifactBucket/$artifactKey"
