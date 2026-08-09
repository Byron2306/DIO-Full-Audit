import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "backend"))

async def test_atomic():
    print("--- Testing Atomic Validation Job Building ---")
    try:
        # Load env vars
        from dotenv import load_dotenv
        load_dotenv()
        
        from atomic_validation import atomic_validation
        
        # Check status
        status = atomic_validation.get_status()
        print(f"Status: {status}")
        
        if not status["runner_available"]:
            print("ERROR: Runner still not available!")
            return

        jobs = atomic_validation.list_jobs().get("jobs", [])
        if not jobs:
            print("ERROR: No atomic validation jobs are configured.")
            return

        job_id = jobs[0]["job_id"]
        print(f"Executing dry-run for job {job_id}...")
        result = atomic_validation.run_job(job_id, dry_run=True)
        print(f"Dry Run Result: {result}")
        print(f"Command formed: {' '.join(result.get('command', []))}")
        
        # Check if technique folder exists
        if status["atomic_root_exists"]:
            print("Atomic root exists. Ready for real execution.")
        else:
            print("WARNING: Atomic root still reported as missing.")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_atomic())
