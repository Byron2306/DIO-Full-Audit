import logging
import hashlib
import os
import json
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

class VerityEngine:
    """
    Gate 3: The Memory of the Valar.
    Implements a runtime Merkle Witness for the Arda Substrate.
    Every file/block is mapped to a Merkle Tree anchored by the preboot covenant.
    """
    
    def __init__(self, root_dir: str = "backend"):
        self.root_dir = os.path.join(os.getcwd(), root_dir)
        self.merkle_tree: Dict[str, str] = {} # path -> hash (leaves)
        self.root_hash: Optional[str] = None

    async def build_merkle_tree(self) -> Tuple[str, Dict[str, str]]:
        """
        Builds a full Merkle Tree of the specified directory.
        Returns (root_hash, leaf_map).
        """
        logger.info(f"Verity: Building Merkle Tree for {self.root_dir}...")
        
        leaf_hashes = []
        path_to_hash = {}
        
        # 1. Collect and hash all files (Leaves)
        for root, dirs, files in os.walk(self.root_dir):
            for f in sorted(files):
                 if f.endswith(".py") or f.endswith(".json") or f.endswith(".md"):
                     file_path = os.path.join(root, f)
                     rel_path = os.path.relpath(file_path, self.root_dir)
                     
                     file_hash = self._hash_file(file_path)
                     path_to_hash[rel_path] = file_hash
                     leaf_hashes.append(file_hash)

        # 2. Build the Tree from Leaves to Root
        self.root_hash = self._compute_merkle_root(leaf_hashes)
        self.merkle_tree = path_to_hash
        
        logger.info(f"Verity: Merkle Tree complete. Root: {self.root_hash[:16]}")
        return self.root_hash, path_to_hash

    async def verify_integrity(self) -> List[str]:
        """
        Scans the current filesystem and returns a list of dissonant (altered) files.
        """
        dissonant_files = []
        logger.info("Verity: Verifying runtime integrity against Merkle anchors...")
        
        for rel_path, expected_hash in self.merkle_tree.items():
            full_path = os.path.join(self.root_dir, rel_path)
            if not os.path.exists(full_path):
                logger.warning(f"Verity: Missing File! {rel_path}")
                dissonant_files.append(rel_path)
                continue
                
            actual_hash = self._hash_file(full_path)
            if actual_hash != expected_hash:
                logger.critical(f"Verity: DISSONANCE! File {rel_path} has been altered!")
                dissonant_files.append(rel_path)
                
        return dissonant_files

    def _hash_file(self, file_path: str) -> str:
        """Computes the SHA256 of a file's content."""
        h = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                h.update(chunk)
        return h.hexdigest()

    def _compute_merkle_root(self, hashes: List[str]) -> str:
        """Determinstically reduces a list of hashes to a single Merkle Root."""
        if not hashes:
            return hashlib.sha256(b"empty_tree").hexdigest()
            
        current_layer = sorted(hashes)
        while len(current_layer) > 1:
            next_layer = []
            for i in range(0, len(current_layer), 2):
                if i + 1 < len(current_layer):
                    combined = current_layer[i] + current_layer[i+1]
                else:
                    # Duplicate the last hash for odd-numbered layers
                    combined = current_layer[i] + current_layer[i]
                next_layer.append(hashlib.sha256(combined.encode()).hexdigest())
            current_layer = next_layer
            
        return current_layer[0]

# Global singleton
verity_engine = VerityEngine()

def get_verity_engine():
    return verity_engine
