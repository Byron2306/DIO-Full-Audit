#!/usr/bin/env python3
from __future__ import annotations
"""
Arda Presence Grounding (Tiered Retrieval)
v4.8.2: Sovereign Knowledge Architecture
- Tier 1: Local Vault (Subfolder Taxonomy)
- Article XIII: Plain Statement of Ignorance
- Necessity Check: Triune Oversight for Seraph Egress
- Auto-Vaulting with Deterministic Pruning & Archival
"""
import os
import re
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger("presence.grounding")

# Configuration
VAULT_ROOT = Path("/home/byron/Integritas-Mechanicus-clean/Integritas-Mechanicus/arda_os/knowledge/vault")
ARCHIVE_ROOT = Path("/home/byron/Integritas-Mechanicus-clean/Integritas-Mechanicus/arda_os/knowledge/archive")
DOMAINS = ["theology", "science", "history", "technical"]
MIN_RELEVANCE_SCORE = 1.0  # Threshold for local knowledge sufficiency

class GroundingResult:
    def __init__(self, source: str, content: str, score: float, domain: str, scrutiny_score: float = 1.0):
        self.source = source
        self.content = content
        self.score = score
        self.domain = domain
        self.scrutiny_score = scrutiny_score

class PresenceGrounding:
    def __init__(self):
        self._initialize_dirs()

    def _initialize_dirs(self):
        """Ensure the taxonomy and archive exist."""
        for domain in DOMAINS:
            (VAULT_ROOT / domain).mkdir(parents=True, exist_ok=True)
            (ARCHIVE_ROOT / domain).mkdir(parents=True, exist_ok=True)

    def prune_outdated_matches(self, domain: str, title: str, new_score: float):
        """
        Search for existing files with matching titles.
        Perform Conflict Resolution: Archive if old is inferior, Abort if new is inferior.
        Returns: True if vaulting should proceed, False if existing truth is superior.
        """
        safe_title = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_").lower()
        file_path = VAULT_ROOT / domain / f"{safe_title}.md"
        
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    old_content = f.read()
                
                old_score = 1.0
                meta_match = re.search(r"Scrutiny-Score: ([\d.]+)", old_content)
                if meta_match:
                    old_score = float(meta_match.group(1))
                
                if new_score < old_score:
                    logger.warning(f"PRUNING BLOCK: New knowledge (Score {new_score}) is inferior to vaulted truth (Score {old_score}). Aborting.")
                    return False
                
                # If new is better or equal, archive the old one
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                archive_path = ARCHIVE_ROOT / domain / f"{safe_title}_{ts}.md.bak"
                shutil.move(file_path, archive_path)
                logger.info(f"PRUNING EVENT: Archived inferior truth to {archive_path.name}")
                return True
                
            except Exception as e:
                logger.error(f"PRUNING ERROR: {e}")
                return True # Proceed anyway if archive fails
        
        return True

    def vault_knowledge(self, domain: str, title: str, content: str, scrutiny_score: float, source: str):
        """
        Save scrutinized knowledge into the vault after pruning.
        """
        if domain not in DOMAINS:
            domain = "technical"
        
        # Conflict Resolution Phase
        if not self.prune_outdated_matches(domain, title, scrutiny_score):
            return None # Superior truth already exists

        safe_title = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_").lower()
        file_path = VAULT_ROOT / domain / f"{safe_title}.md"
        
        # Memory Meta Block
        header = f"""---
Memory-Class: Sovereign-Academic
Source: {source}
Scrutiny-Score: {scrutiny_score}
Vaulted-At: {datetime.now(timezone.utc).isoformat()}
Status: Active
---

# {title}

{content}
"""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(header)
            logger.info(f"AUTO-VAULT: Saved knowledge to {file_path}")
            return str(file_path)
        except Exception as e:
            logger.error(f"AUTO-VAULT ERROR: {e}")
            return None

    def search_local_vault(self, query: str) -> List[GroundingResult]:
        """Tier 1: Search the local filesystem taxonomy."""
        keywords = set(re.findall(r"\w+", query.lower()))
        results = []

        for domain in DOMAINS:
            domain_path = VAULT_ROOT / domain
            for root, _, files in os.walk(domain_path):
                for f in files:
                    if f.endswith((".md", ".txt", ".json")):
                        try:
                            path = Path(root) / f
                            with open(path, "r", encoding="utf-8") as file:
                                full_content = file.read()
                                
                                scrutiny_score = 1.0
                                meta_match = re.search(r"Scrutiny-Score: ([\d.]+)", full_content)
                                if meta_match:
                                    scrutiny_score = float(meta_match.group(1))

                                body = full_content.split("---")[-1]
                                score = sum(1 for kw in keywords if len(kw) > 3 and kw in body.lower())
                                
                                if score > 0:
                                    src_match = re.search(r"Source: ([^\n]+)", full_content)
                                    source_info = src_match.group(1) if src_match else f
                                    
                                    idx = body.lower().find(list(keywords)[0]) if keywords else 0
                                    snippet = body[max(0, idx-300):idx+900].strip()
                                    
                                    results.append(GroundingResult(
                                        source=source_info, 
                                        content=snippet, 
                                        score=score, 
                                        domain=domain,
                                        scrutiny_score=scrutiny_score
                                    ))
                        except Exception as e:
                            logger.error(f"Error reading {f}: {e}")

        results.sort(key=lambda x: x.score, reverse=True)
        return results

    def evaluate_necessity(self, query: str, local_results: List[GroundingResult]) -> Tuple[bool, str]:
        if local_results and local_results[0].score >= MIN_RELEVANCE_SCORE:
            return False, "Local knowledge is sufficient."

        # Academic triggers
        academic_keywords = ["who was", "history", "battle", "theorem", "physical", "atomic", "scientific", "emperor", "empire"]
        is_academic = any(kw in query.lower() for kw in academic_keywords)
        
        if not is_academic:
            return False, "Query is conversational; does not warrant Seraphic Egress."

        return True, "Local records are insufficient; academic grounding required."

    async def get_ignorance_statement(self, query: str) -> str:
        return f"I have searched my local records and found no verified truth for your query: '{query}'. Under Article XIII, I declare my current local knowledge to be insufficient."""

def get_grounding_service():
    return PresenceGrounding()
