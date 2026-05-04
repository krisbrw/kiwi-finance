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
Write-Host "=== Building Lambda package using Docker (Linux environment) ==="

# Clean build directory
if (Test-Path -LiteralPath $buildRoot) { 
    try {
        Remove-Item -LiteralPath $buildRoot -Recurse -Force -ErrorAction Stop
    } catch {
        Write-Host "Warning: Could not fully clean build directory. Retrying..." -ForegroundColor Yellow
        Start-Sleep -Seconds 2
        Remove-Item -LiteralPath $buildRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null
New-Item -ItemType Directory -Path $packageRoot -Force | Out-Null

# Build using Docker with Amazon Linux 2 (same as Lambda runtime)
Write-Host "Building dependencies in Docker container (Amazon Linux 2)..."

# Use bash to run the pip command inside the container
# Let pip naturally build for the Linux environment (no platform/only-binary flags needed)
$pipCommand = "pip install -r requirements.txt -t /workspace/build/package --no-cache-dir"

docker run --rm `
    -v "${PWD}:/workspace" `
    -w /workspace `
    --entrypoint bash `
    public.ecr.aws/lambda/python:3.12 `
    -c $pipCommand

if ($LASTEXITCODE -ne 0) {
    throw "Docker build failed"
}

# Copy application code
Write-Host "Copying application code..."
Copy-Item -LiteralPath (Join-Path $projectRoot "app") -Destination $packageRoot -Recurse
Copy-Item -LiteralPath (Join-Path $projectRoot "lambda_function.py") -Destination $packageRoot

# Create zip
Write-Host "Creating deployment package..."
Push-Location $packageRoot
Compress-Archive -Path * -DestinationPath $zipPath -Force
Pop-Location

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
Write-Host "Waiting for Lambda update to complete..."
Start-Sleep -Seconds 5

Write-Host "Testing the function..."
aws lambda invoke --function-name $functionName --log-type Tail response.json --region $Region | Out-Null
$response = Get-Content response.json -Raw | ConvertFrom-Json
Write-Host ""
Write-Host "Lambda Response:"
Write-Host $response.body
Write-Host ""

if ($response.statusCode -eq 200) {
    Write-Host "SUCCESS! The Lambda function is now working correctly." -ForegroundColor Green
    Write-Host "The daily job will automatically sync transactions from Plaid every day at 1 PM UTC (8 AM EST)."
} else {
    Write-Host "ERROR: Lambda function still failing. Check the response above." -ForegroundColor Red
}
