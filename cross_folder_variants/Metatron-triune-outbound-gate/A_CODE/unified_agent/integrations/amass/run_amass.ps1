Param([string]$domain)
if (-not $domain) {
  Write-Host "Usage: .\run_amass.ps1 <domain.com>"
  exit 1
}
$timestamp = (Get-Date).ToString("yyyyMMddHHmmss")
$out = "amass_${domain}_$timestamp.json"
Write-Host "Running amass for domain: $domain -> $out"
# Uses official amass docker image
docker run --rm -v ${PWD}:/data caffix/amass:latest enum -d $domain -oJ /data/$out
Write-Host "Output: $out"
