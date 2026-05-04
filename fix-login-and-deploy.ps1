#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Fixes the database password caching issue and redeploys the app
.DESCRIPTION
    This script rebuilds the Docker image with the database fix and updates the ECS service
#>

$ErrorActionPreference = "Stop"

Write-Host "=== Kiwi Finance - Fix Login Issue and Redeploy ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "This script will:"
Write-Host "  1. Build a new Docker image with the database password caching fix"
Write-Host "  2. Push it to ECR"
Write-Host "  3. Update the ECS service to use the new image"
Write-Host ""

# Check if Docker is running
try {
    docker ps | Out-Null
} catch {
    Write-Host "ERROR: Docker is not running. Please start Docker Desktop and try again." -ForegroundColor Red
    exit 1
}

$REGION = "us-east-1"
$accountId = (aws sts get-caller-identity --query Account --output text --region $REGION).Trim()
$ecrUri = "$accountId.dkr.ecr.$REGION.amazonaws.com/kiwi-finance-app"

Write-Host "Logging into ECR..." -ForegroundColor Yellow
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin "$accountId.dkr.ecr.$REGION.amazonaws.com"

$imageTag = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$imageUri = "${ecrUri}:${imageTag}"
$imageUriLatest = "${ecrUri}:latest"

Write-Host ""
Write-Host "Building Docker image..." -ForegroundColor Yellow
docker build -t $imageUri -t $imageUriLatest .

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker build failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Pushing to ECR..." -ForegroundColor Yellow
docker push $imageUri
docker push $imageUriLatest

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker push failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Updating ECS service..." -ForegroundColor Yellow
.\update-ecs-service.ps1

Write-Host ""
Write-Host "=== Deployment Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "The login issue has been fixed. The app will be ready in about 1-2 minutes."
Write-Host "Monitor the deployment:"
Write-Host "  aws ecs describe-services --cluster kiwi-finance-app-cluster --services kiwi-finance-app-app --region us-east-1 --query 'services[0].{runningCount:runningCount,desiredCount:desiredCount}'"
Write-Host ""
Write-Host "Check logs:"
Write-Host "  aws logs tail /ecs/kiwi-finance-app-app --region us-east-1 --follow"
Write-Host ""
Write-Host "Test the app:"
Write-Host "  https://mykiwifinance.com"
