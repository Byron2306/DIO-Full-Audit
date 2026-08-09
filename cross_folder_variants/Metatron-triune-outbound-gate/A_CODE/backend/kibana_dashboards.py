"""
Kibana Dashboard Service - Pre-built security dashboards
"""
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional
import httpx
import logging

logger = logging.getLogger(__name__)

# Pre-built Kibana dashboard configurations
KIBANA_DASHBOARDS = {
    "security-overview": {
        "title": "Security Overview Dashboard",
        "description": "Main security dashboard with threat summary, alerts, and trends",
        "panels": [
            {
                "type": "metric",
                "title": "Total Threats (24h)",
                "query": {"match": {"event_type": "threat_detected"}},
                "timeRange": "24h"
            },
            {
                "type": "metric", 
                "title": "Critical Alerts",
                "query": {"match": {"severity": "critical"}},
                "timeRange": "24h"
            },
            {
                "type": "pie",
                "title": "Threats by Severity",
                "field": "severity",
                "timeRange": "7d"
            },
            {
                "type": "pie",
                "title": "Threats by Type",
                "field": "threat_type",
                "timeRange": "7d"
            },
            {
                "type": "line",
                "title": "Threat Trend (7 days)",
                "field": "@timestamp",
                "interval": "1d",
                "timeRange": "7d"
            },
            {
                "type": "table",
                "title": "Recent Critical Events",
                "columns": ["@timestamp", "event_type", "threat_name", "source_ip", "action_taken"],
                "query": {"match": {"severity": "critical"}},
                "limit": 10
            }
        ]
    },
    "threat-intelligence": {
        "title": "Threat Intelligence Dashboard",
        "description": "IOC matches, threat feeds, and intelligence metrics",
        "panels": [
            {
                "type": "metric",
                "title": "IOC Matches (24h)",
                "query": {"match": {"event_type": "ioc_match"}},
                "timeRange": "24h"
            },
            {
                "type": "pie",
                "title": "IOC Types",
                "field": "ioc_type",
                "timeRange": "7d"
            },
            {
                "type": "bar",
                "title": "Top Threat Actors",
                "field": "threat_actor",
                "limit": 10,
                "timeRange": "30d"
            },
            {
                "type": "table",
                "title": "Recent IOC Matches",
                "columns": ["@timestamp", "indicator", "ioc_type", "source", "confidence"],
                "limit": 20
            }
        ]
    },
    "geo-threat-map": {
        "title": "Geographic Threat Map",
        "description": "Global view of attack origins and targets",
        "panels": [
            {
                "type": "map",
                "title": "Attack Origins",
                "field": "geo.location",
                "timeRange": "7d"
            },
            {
                "type": "bar",
                "title": "Top Attacking Countries",
                "field": "geo.country",
                "limit": 15,
                "timeRange": "7d"
            },
            {
                "type": "bar",
                "title": "Top Attacking Cities",
                "field": "geo.city",
                "limit": 10,
                "timeRange": "7d"
            },
            {
                "type": "table",
                "title": "Top Attacking IPs",
                "columns": ["source_ip", "geo.country", "event_count", "last_seen"],
                "limit": 20
            }
        ]
    },
    "mitre-attack": {
        "title": "MITRE ATT&CK Dashboard",
        "description": "Tactics and techniques mapped to MITRE framework",
        "panels": [
            {
                "type": "heatmap",
                "title": "MITRE Tactics Heatmap",
                "x_field": "mitre.tactic",
                "y_field": "mitre.technique",
                "timeRange": "30d"
            },
            {
                "type": "bar",
                "title": "Top Tactics",
                "field": "mitre.tactic",
                "limit": 12,
                "timeRange": "30d"
            },
            {
                "type": "bar",
                "title": "Top Techniques",
                "field": "mitre.technique",
                "limit": 15,
                "timeRange": "30d"
            },
            {
                "type": "table",
                "title": "Recent ATT&CK Detections",
                "columns": ["@timestamp", "mitre.tactic", "mitre.technique", "description"],
                "limit": 20
            }
        ]
    },
    "endpoint-security": {
        "title": "Endpoint Security Dashboard",
        "description": "Agent status, EDR events, and endpoint health",
        "panels": [
            {
                "type": "metric",
                "title": "Active Agents",
                "query": {"match": {"agent_status": "active"}},
                "timeRange": "1h"
            },
            {
                "type": "metric",
                "title": "Quarantined Files (24h)",
                "query": {"match": {"action_taken": "quarantine"}},
                "timeRange": "24h"
            },
            {
                "type": "pie",
                "title": "Events by Agent",
                "field": "agent_id",
                "timeRange": "24h"
            },
            {
                "type": "line",
                "title": "Process Events Trend",
                "field": "@timestamp",
                "query": {"match": {"event_type": "process_event"}},
                "interval": "1h",
                "timeRange": "24h"
            },
            {
                "type": "table",
                "title": "Suspicious Processes",
                "columns": ["@timestamp", "agent_id", "process_name", "command_line", "severity"],
                "query": {"match": {"event_type": "suspicious_process"}},
                "limit": 15
            }
        ]
    },
    "playbook-analytics": {
        "title": "SOAR Playbook Analytics",
        "description": "Playbook execution metrics and automation stats",
        "panels": [
            {
                "type": "metric",
                "title": "Playbook Executions (24h)",
                "query": {"match": {"event_type": "playbook_executed"}},
                "timeRange": "24h"
            },
            {
                "type": "pie",
                "title": "Executions by Playbook",
                "field": "playbook_name",
                "timeRange": "7d"
            },
            {
                "type": "pie",
                "title": "Execution Results",
                "field": "execution_status",
                "timeRange": "7d"
            },
            {
                "type": "bar",
                "title": "Actions Taken",
                "field": "action_taken",
                "limit": 10,
                "timeRange": "7d"
            },
            {
                "type": "line",
                "title": "Automation Trend",
                "field": "@timestamp",
                "query": {"match": {"event_type": "playbook_executed"}},
                "interval": "1d",
                "timeRange": "30d"
            }
        ]
    }
}

# Kibana saved object format for dashboards
def generate_kibana_dashboard_ndjson(dashboard_id: str, dashboard_config: Dict) -> str:
    """Generate NDJSON format for Kibana dashboard import"""
    
    # Dashboard object
    dashboard_obj = {
        "type": "dashboard",
        "id": f"anti-ai-{dashboard_id}",
        "attributes": {
            "title": dashboard_config["title"],
            "description": dashboard_config["description"],
            "panelsJSON": json.dumps([
                {
                    "panelIndex": str(i),
                    "gridData": {
                        "x": (i % 3) * 16,
                        "y": (i // 3) * 12,
                        "w": 16,
                        "h": 12,
                        "i": str(i)
                    },
                    "type": "visualization",
                    "title": panel["title"]
                }
                for i, panel in enumerate(dashboard_config["panels"])
            ]),
            "optionsJSON": json.dumps({
                "useMargins": True,
                "syncColors": False,
                "hidePanelTitles": False
            }),
            "timeRestore": True,
            "timeTo": "now",
            "timeFrom": "now-7d",
            "refreshInterval": {
                "pause": False,
                "value": 60000
            },
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": []
                })
            }
        },
        "references": []
    }
    
    return json.dumps(dashboard_obj)


class KibanaDashboardService:
    def __init__(self):
        self.dashboards = KIBANA_DASHBOARDS
        self.elasticsearch_url = os.environ.get("ELASTICSEARCH_URL") or "http://elasticsearch:9200"
        self.api_key = os.environ.get("ELASTICSEARCH_API_KEY")
        self.elasticsearch_username = os.environ.get("ELASTICSEARCH_USERNAME")
        self.elasticsearch_password = os.environ.get("ELASTICSEARCH_PASSWORD")
        self.kibana_url = os.environ.get("KIBANA_URL") or "http://kibana:5601"
        
        # Auto-configure if environment variables are set
        if self.elasticsearch_url:
            # Derive Kibana URL from ES URL
            if not os.environ.get("KIBANA_URL"):
                self.kibana_url = self.elasticsearch_url.replace(":9243", ":5601").replace(":9200", ":5601").replace(":443", ":5601")
            logger.info(f"Kibana configured from environment: {self.elasticsearch_url}")
    
    def configure(
        self,
        elasticsearch_url: str,
        api_key: Optional[str] = None,
        kibana_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        """Configure Elasticsearch/Kibana connection"""
        self.elasticsearch_url = elasticsearch_url
        self.api_key = api_key
        self.elasticsearch_username = username
        self.elasticsearch_password = password
        # Derive Kibana URL from ES URL if not provided
        self.kibana_url = kibana_url or elasticsearch_url.replace(":9243", ":5601").replace(":443", ":5601")

    def _get_auth_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "kbn-xsrf": "true"
        }
        if self.api_key:
            headers["Authorization"] = f"ApiKey {self.api_key}"
        elif self.elasticsearch_username and self.elasticsearch_password:
            import base64
            basic_token = base64.b64encode(
                f"{self.elasticsearch_username}:{self.elasticsearch_password}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {basic_token}"
        return headers
    
    def get_available_dashboards(self) -> List[Dict]:
        """Get list of available pre-built dashboards"""
        return [
            {
                "id": dashboard_id,
                "title": config["title"],
                "description": config["description"],
                "panel_count": len(config["panels"])
            }
            for dashboard_id, config in self.dashboards.items()
        ]
    
    def get_dashboard_config(self, dashboard_id: str) -> Optional[Dict]:
        """Get full configuration for a specific dashboard"""
        return self.dashboards.get(dashboard_id)
    
    async def create_index_pattern(self) -> Dict:
        """Create the security-events index pattern in Kibana"""
        if not self.elasticsearch_url:
            return {"success": False, "error": "Not configured"}
        
        # Create index pattern via Kibana API
        headers = self._get_auth_headers()
        
        index_pattern = {
            "attributes": {
                "title": "security-events-*",
                "timeFieldName": "@timestamp"
            }
        }
        
        try:
            async with httpx.AsyncClient() as client:
                # Try to create via Kibana API
                response = await client.post(
                    f"{self.kibana_url}/api/saved_objects/index-pattern/security-events",
                    json=index_pattern,
                    headers=headers,
                    timeout=30
                )
                
                if response.status_code in [200, 201, 409]:  # 409 = already exists
                    return {"success": True, "message": "Index pattern created/exists"}
                else:
                    logger.warning(f"Kibana API response: {response.status_code}")
                    return {"success": False, "error": response.text}
        except Exception as e:
            logger.error(f"Failed to create index pattern: {e}")
            return {"success": False, "error": str(e)}
    
    def get_dashboard_export(self, dashboard_id: str) -> Optional[str]:
        """Get NDJSON export for a dashboard (for manual import)"""
        config = self.dashboards.get(dashboard_id)
        if not config:
            return None
        return generate_kibana_dashboard_ndjson(dashboard_id, config)
    
    def get_all_dashboards_export(self) -> str:
        """Get NDJSON export for all dashboards"""
        exports = []
        for dashboard_id, config in self.dashboards.items():
            exports.append(generate_kibana_dashboard_ndjson(dashboard_id, config))
        return "\n".join(exports)
    
    def get_visualization_queries(self, dashboard_id: str) -> List[Dict]:
        """Get Elasticsearch queries for dashboard visualizations"""
        config = self.dashboards.get(dashboard_id)
        if not config:
            return []
        
        queries = []
        for panel in config["panels"]:
            query = {
                "title": panel["title"],
                "type": panel["type"],
                "index": "security-events-*",
                "time_field": "@timestamp"
            }
            
            if panel["type"] == "metric":
                query["agg"] = {"type": "count"}
                if "query" in panel:
                    query["filter"] = panel["query"]
            
            elif panel["type"] in ["pie", "bar"]:
                query["agg"] = {
                    "type": "terms",
                    "field": panel.get("field"),
                    "size": panel.get("limit", 10)
                }
            
            elif panel["type"] == "line":
                query["agg"] = {
                    "type": "date_histogram",
                    "field": panel.get("field", "@timestamp"),
                    "interval": panel.get("interval", "1d")
                }
            
            elif panel["type"] == "table":
                query["agg"] = {"type": "top_hits"}
                query["columns"] = panel.get("columns", [])
                query["size"] = panel.get("limit", 10)
            
            queries.append(query)
        
        return queries


# Global instance
kibana_dashboard_service = KibanaDashboardService()
