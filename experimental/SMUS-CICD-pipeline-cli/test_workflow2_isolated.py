#!/usr/bin/env python3
"""Test workflow2_summary in isolation"""
import subprocess
import sys
import time

def run_cmd(cmd):
    """Run command and return output"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr

def main():
    print("=" * 80)
    print("Testing workflow2_summary (covid_data_summary task) in isolation")
    print("=" * 80)
    
    # Step 1: Deploy workflow2
    print("\n[1/3] Deploying workflow2_summary...")
    rc, out, err = run_cmd(
        "cd /Users/amirbo/code/smus/experimental/SMUS-CICD-pipeline-cli && "
        "source .venv/bin/activate && "
        "python -m smus_cicd.cli deploy --targets test --pipeline examples/analytic-workflow/etl/pipeline_workflow2.yaml"
    )
    print(out)
    if "Error" in out or rc != 0:
        print(f"❌ Deploy had issues")
        if err:
            print(f"stderr: {err}")
    else:
        print("✅ Workflow deployed")
    
    # Step 2: Start workflow
    print("\n[2/3] Starting workflow...")
    rc, out, err = run_cmd(
        "cd /Users/amirbo/code/smus/experimental/SMUS-CICD-pipeline-cli && "
        "source .venv/bin/activate && "
        "python -m smus_cicd.cli run --targets test --pipeline examples/analytic-workflow/etl/pipeline_workflow2.yaml"
    )
    print(out)
    if rc != 0:
        print(f"❌ Run failed")
        if err:
            print(f"stderr: {err}")
    else:
        print("✅ Workflow started")
    
    # Step 3: Wait and check logs
    print("\n[3/3] Waiting 90 seconds then checking logs...")
    time.sleep(90)
    
    rc, out, err = run_cmd(
        "cd /Users/amirbo/code/smus/experimental/SMUS-CICD-pipeline-cli && "
        "source .venv/bin/activate && "
        "python -m smus_cicd.cli logs --targets test --pipeline examples/analytic-workflow/etl/pipeline_workflow2.yaml"
    )
    print(out[-3000:])  # Last 3000 chars
    
    print("\n" + "=" * 80)
    print("RESULT: Check logs above for 'multiple values for keyword argument' error")
    print("=" * 80)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

