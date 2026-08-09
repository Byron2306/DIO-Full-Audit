# Start SpiderFoot in Docker and expose web UI/API on localhost:5001
# Optionally pass a container name as first arg
Param([string]$name = 'spiderfoot')
Write-Host "Starting SpiderFoot container: $name"
# Pull & run (persistent container)
docker run -d --name $name -p 5001:5001 spiderfoot/spiderfoot:latest
Write-Host "SpiderFoot should be available at http://localhost:5001"
