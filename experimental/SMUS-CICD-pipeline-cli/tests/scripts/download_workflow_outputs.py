#!/usr/bin/env python3
"""Download notebook outputs from a workflow run."""

import argparse
import subprocess
import tarfile
import tempfile
from pathlib import Path


def download_workflow_outputs(s3_bucket: str, output_dir: str, run_id: str = None):
    """Download notebook outputs from workflow, organized by workflow name and run ID."""
    s3_prefix = f"s3://{s3_bucket}/shared/workflows/output/notebooks/"
    
    print(f"Searching for outputs in {s3_prefix}...")
    result = subprocess.run(
        ["aws", "s3", "ls", s3_prefix, "--recursive"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"Error listing S3: {result.stderr}")
        return []
    
    # Parse all runs and find latest if no run_id specified
    runs = {}
    for line in result.stdout.strip().split("\n"):
        if not line or "output.tar.gz" not in line:
            continue
        
        parts = line.split()
        if len(parts) < 4:
            continue
        
        timestamp = f"{parts[0]} {parts[1]}"
        s3_key = " ".join(parts[3:])
        key_parts = s3_key.split("/")
        if len(key_parts) < 7:
            continue
        
        workflow_name = key_parts[4]
        current_run_id = key_parts[5]
        
        if workflow_name not in runs:
            runs[workflow_name] = {}
        if current_run_id not in runs[workflow_name]:
            runs[workflow_name][current_run_id] = {"timestamp": timestamp, "files": []}
        runs[workflow_name][current_run_id]["files"].append(s3_key)
    
    # If no run_id, get latest run per workflow
    if not run_id:
        latest_runs = {}
        for workflow_name, workflow_runs in runs.items():
            latest_run = max(workflow_runs.items(), key=lambda x: x[1]["timestamp"])
            latest_runs[workflow_name] = {latest_run[0]: latest_run[1]}
        runs = latest_runs
        print(f"Downloading latest runs only...")
    
    downloaded_files = []
    
    for workflow_name, workflow_runs in runs.items():
        for current_run_id, run_data in workflow_runs.items():
            if run_id and current_run_id != run_id:
                continue
            
            output_path = Path(output_dir) / workflow_name / current_run_id
            output_path.mkdir(parents=True, exist_ok=True)
            
            for s3_key in run_data["files"]:
                s3_path = f"s3://{s3_bucket}/{s3_key}"
                
                with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
                    tmp_path = tmp.name
                
                print(f"Downloading {workflow_name}/{current_run_id}...")
                result = subprocess.run(
                    ["aws", "s3", "cp", s3_path, tmp_path],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0:
                    print(f"  Error: {result.stderr}")
                    Path(tmp_path).unlink(missing_ok=True)
                    continue
                
                try:
                    with tarfile.open(tmp_path, "r:gz") as tar:
                        for member in tar.getmembers():
                            if member.name.startswith("_") and member.name.endswith(".ipynb"):
                                tar.extract(member, output_path)
                                extracted_path = output_path / member.name
                                downloaded_files.append(str(extracted_path))
                                print(f"  ✅ {extracted_path}")
                except Exception as e:
                    print(f"  Error extracting: {e}")
                finally:
                    Path(tmp_path).unlink(missing_ok=True)
    
    print(f"\n✅ Downloaded {len(downloaded_files)} notebooks")
    return downloaded_files


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download workflow notebook outputs")
    parser.add_argument("s3_bucket", help="S3 bucket name (e.g., amazon-sagemaker-198737698272-us-east-2-4uoxu0uszmmxbd)")
    parser.add_argument("--output-dir", default="tests/test-outputs/1-notebooks", help="Output directory")
    parser.add_argument("--run-id", help="Filter by specific run ID (optional)")
    
    args = parser.parse_args()
    download_workflow_outputs(args.s3_bucket, args.output_dir, args.run_id)
