import asyncio
import os
import sys
import logging

# Add project root to sys.path
sys.path.append(os.getcwd())

from backend.services.ainur.ainur_council import AinurCouncil
from backend.services.ainur.witnesses.manwe_herald import ManweHerald
from backend.services.ainur.witnesses.varda_truth import VardaTruth
from backend.services.ainur.witnesses.vaire_weaver import VaireWeaver
from backend.services.ainur.witnesses.mandos_precedent import MandosPrecedent
from backend.services.ainur.witnesses.lorien_healer import LorienHealer

# Configure logging to show the "Speech of the Ainur"
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("ARDA_AINUR")

async def main():
    print("\n" + "="*60)
    print("⚜️ ARDA OS: THE SUMMONING OF THE AINUR COUNCIL (DEMO) ⚜️")
    print("="*60 + "\n")
    
    # Initialize the Council (Host-side Ollama)
    council = AinurCouncil()
    council.register_witness(ManweHerald(council))
    council.register_witness(VardaTruth(council))
    council.register_witness(VaireWeaver(council))
    council.register_witness(MandosPrecedent(council))
    council.register_witness(LorienHealer(council))
    
    # Mock specific tool execution context
    context = {
        "command": "Process List (ps)",
        "actor": "agent:seraph",
        "reason": "Routine diagnostics for the Outbound Gate.",
        "state": "unknown",
        "evidence": {
            "binary_path": "/bin/ps",
            "invocation": "ps -aux",
            "caller_trust": 0.85
        },
        "history": [
            {"date": "2026-03-24", "action": "authorized_exec", "tool": "ps"},
            {"date": "2026-03-23", "action": "blocked_exec", "tool": "whoami"}
        ]
    }
    
    print(f"CONSULTING THE COUNCIL ON: {context['command']}")
    print(f"ACTOR: {context['actor']}")
    print(f"CLAIMED PURPOSE: {context['reason']}\n")
    
    # Consultation
    try:
        advisory = await council.consult_witnesses(context)
        
        print("\n--- [THE SPEECH OF THE AINUR] ---")
        for witness, report in advisory["witness_reports"].items():
            print(f"\n[{witness} spoke]:")
            print(f"  JUDGMENT:   {report['judgment']}")
            
            # Show specific reasoning based on witness domain
            if witness == "Manwë":
                print(f"  HERALDING:  {report.get('heralding', 'The brain is silent.')}")
            elif witness == "Varda":
                print(f"  CONSISTENCY Score: {report.get('consistency_score', 0.0)}")
                print(f"  FINDINGS:   {report.get('findings', 'The brain is silent.')}")
            elif witness == "Vairë":
                print(f"  PATTERN Match: {report.get('pattern_match', 0.0)}")
                print(f"  TAPESTRY:   {report.get('tapestry', 'The brain is silent.')}")
            elif witness == "Mandos":
                print(f"  PRECEDENT Weight: {report.get('precedent_weight', 0.0)}")
                print(f"  CONSEQUENCE LEDGER: {report.get('consequence_ledger', 'The brain is silent.')}")
            elif witness == "Lórien":
                print(f"  RECOVERY PATH: {report.get('recovery_path', 'The brain is silent.')}")
                print(f"  RECONCILIATION Score: {report.get('reconciliation_score', 0.0)}")
        
        print("\n" + "="*60)
        print(f"COUNCIL CONSENSUS: {advisory['overall_recommendation']} ✅")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ Council consultation collapsed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
