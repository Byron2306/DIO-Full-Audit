#!/usr/bin/env python3
import os
import requests
from typing import List, Dict, Any

API_URL = os.environ.get('API_URL', 'http://localhost:8001')
API_PREFIX = API_URL.rstrip('/') + '/api'


def _headers(token: str = None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return headers


def start_amass(domain: str, token: str = None, timeout: int = 10) -> Dict[str, Any]:
    url = f"{API_PREFIX}/integrations/amass/run"
    r = requests.post(url, json={'domain': domain}, headers=_headers(token), timeout=timeout)
    r.raise_for_status()
    return r.json()


def list_integration_jobs(token: str = None, timeout: int = 10) -> List[Dict[str, Any]]:
    url = f"{API_PREFIX}/integrations/jobs"
    r = requests.get(url, headers=_headers(token), timeout=timeout)
    r.raise_for_status()
    return r.json()


def get_job(job_id: str, token: str = None, timeout: int = 10) -> Dict[str, Any]:
    url = f"{API_PREFIX}/integrations/jobs/{job_id}"
    r = requests.get(url, headers=_headers(token), timeout=timeout)
    r.raise_for_status()
    return r.json()


def direct_ingest(source: str, indicators: List[Dict[str, Any]], token: str = None, timeout: int = 30) -> Dict[str, Any]:
    url = f"{API_PREFIX}/integrations/ingest/direct"
    r = requests.post(url, json={'source': source, 'indicators': indicators}, headers=_headers(token), timeout=timeout)
    r.raise_for_status()
    return r.json()


def start_velociraptor(collection_name: str = None, token: str = None, timeout: int = 10) -> Dict[str, Any]:
    url = f"{API_PREFIX}/integrations/velociraptor/run"
    r = requests.post(url, json={'collection_name': collection_name}, headers=_headers(token), timeout=timeout)
    r.raise_for_status()
    return r.json()


def start_purplesharp(target: str = None, options: dict = None, token: str = None, timeout: int = 10) -> Dict[str, Any]:
    url = f"{API_PREFIX}/integrations/purplesharp/run"
    r = requests.post(url, json={'target': target, 'options': options or {}}, headers=_headers(token), timeout=timeout)
    r.raise_for_status()
    return r.json()


def ingest_host_logs(source: str, raw: str, token: str = None, timeout: int = 30) -> Dict[str, Any]:
    url = f"{API_PREFIX}/integrations/ingest/host"
    r = requests.post(url, json={'source': source, 'raw': raw}, headers=_headers(token), timeout=timeout)
    r.raise_for_status()
    return r.json()
