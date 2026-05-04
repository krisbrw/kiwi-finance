[CmdletBinding()]
param(
    [string]$AppStackName = "kiwi-finance-app",
    [string]$Region = "us-east-1",
    [Parameter(Mandatory = $true)]
    [string]$ArtifactBucket,
    [string]$ArtifactPrefix = "artifacts/kiwi-finance"
)

$ErrorActionPreference = "Stop"

$projectRoot  = Split-Path -Parent $MyInvocation.MyCommand.Path
$buildRoot    = Join-Path $projectRoot "build"
$packageRoot  = Join-Path $buildRoot "package"
$zipPath      = Join-Path $buildRoot "kiwi-finance-lambda.zip"

Write-Host ""
Write-Host "=== Rebuilding Lambda package with Linux-compatible dependencies ==="

# Clean build directory
if (Test-Path -LiteralPath $packageRoot) { Remove-Item -LiteralPath $packageRoot -Recurse -Force }
if (Test-Path -LiteralPath $zipPath)     { Remove-Item -LiteralPath $zipPath -Force }
New-Item -ItemType Directory -Path $packageRoot -Force | Out-Null

# Install dependencies for Linux Lambda environment
Write-Host "Installing Python dependencies for Linux Lambda (manylinux2014_x86_64)..."
python -m pip install -r (Join-Path $projectRoot "requirements.txt") -t $packageRoot --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 --only-binary=:all: --upgrade --no-cache-dir

# Copy application code
Write-Host "Copying application code..."
Copy-Item -LiteralPath (Join-Path $projectRoot "app") -Destination $packageRoot -Recurse
Copy-Item -LiteralPath (Join-Path $projectRoot "lambda_function.py") -Destination $packageRoot

# Create zip
Write-Host "Creating deployment package..."
Compress-Archive -Path (Join-Path $packageRoot "*") -DestinationPath $zipPath -Force

# Upload to S3
$timestamp   = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$artifactKey = "$ArtifactPrefix/$AppStackName-$timestamp.zip"
Write-Host "Uploading to S3..."
aws s3 cp $zipPath "s3://$ArtifactBucket/$artifactKey" --region $Region
Write-Host "Lambda package uploaded: s3://$ArtifactBucket/$artifactKey"

# Update Lambda function
$functionName = "$AppStackName-daily-job"
Write-Host "Updating Lambda function: $functionName"
aws lambda update-function-code `
    --function-name $functionName `
    --s3-bucket $ArtifactBucket `
    --s3-key $artifactKey `
    --region $Region | Out-Null

Write-Host ""
Write-Host "Lambda function updated successfully!"
Write-Host "Testing the function..."
aws lambda invoke --function-name $functionName --log-type Tail response.json --region $Region | Out-Null
$response = Get-Content response.json -Raw | ConvertFrom-Json
Write-Host ""
Write-Host "Lambda Response:"
Write-Host $response.body
Write-Host ""
Write-Host "Done! The daily job should now work correctly."
