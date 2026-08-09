# Helper to run BloodHound Docker (UI) for local analysis
# BloodHound requires Neo4j; the container below runs the BloodHound UI only (data should be loaded via UI or SharpHound uploads).

param([string]$name = 'bloodhound')
Write-Host "Starting BloodHound container: $name"

docker run -d --name $name -p 7474:7474 -p 7687:7687 bloodhound:latest || Write-Host "Ensure you have a BloodHound/Neo4j setup; this is a placeholder helper."
Write-Host "Start BloodHound UI and import SharpHound data."
