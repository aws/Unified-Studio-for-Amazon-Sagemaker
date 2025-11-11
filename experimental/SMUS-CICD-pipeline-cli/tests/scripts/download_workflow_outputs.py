#!/usr/bin/env python3
"""Download notebook outputs from a workflow run."""

import argparse
import subprocess
import tarfile
import tempfile
from pathlib import Path


def download_workflow_outputs(s3_bucket: str, output_dir: str):
    """Download all notebook outputs from workflow."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # List all output.tar.gz files
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
    
    downloaded_files = []
    
    for line in result.stdout.strip().split("\n"):
        if not line or "output.tar.gz" not in line:
            continue
        
        parts = line.split()
        if len(parts) < 4:
            continue
        
        s3_key = " ".join(parts[3:])
        s3_path = f"s3://{s3_bucket}/{s3_key}"
        
        # Download tar.gz
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tmp_path = tmp.name
        
        print(f"Downloading {s3_path}...")
        result = subprocess.run(
            ["aws", "s3", "cp", s3_path, tmp_path],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"  Error: {result.stderr}")
            Path(tmp_path).unlink(missing_ok=True)
            continue
        
        # Extract notebooks starting with _
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
    
    args = parser.parse_args()
    download_workflow_outputs(args.s3_bucket, args.output_dir)
