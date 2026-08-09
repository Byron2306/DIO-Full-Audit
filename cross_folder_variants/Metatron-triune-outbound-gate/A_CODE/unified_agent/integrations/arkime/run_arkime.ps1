# Simple helper to start an Arkime (Moloch) container for local testing.
# NOTE: Full Arkime deployment requires ElasticSearch and some config; this helper assumes ES at http://host.docker.internal:9200 or localhost:9200

param()
Write-Host "Starting Arkime (Moloch) container for quick tests"
$es = $env:ARKIME_ES_URL
if (-not $es) { $es = 'http://host.docker.internal:9200' }

# Use the official arkimeimage if available; adjust env vars for your environment
docker run -d --name arkime -p 8005:8005 -p 8006:8006 \
  -e ES_HOSTS=$es \
  -e CAPTURE_INTERFACE=eth0 \
  quay.io/arkime/arkime:latest || docker run -d --name arkime -p 8005:8005 -p 8006:8006 quay.io/arkime/arkime:latest

Write-Host "Arkime container started (if image available). UI will be on http://localhost:8005 (if container started)."
