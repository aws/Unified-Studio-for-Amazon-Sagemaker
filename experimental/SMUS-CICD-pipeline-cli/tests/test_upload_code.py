#!/usr/bin/env python3
"""Test upload_code_to_dev_project functionality."""

import subprocess
import os
import sys

def test_ml_training_upload():
    """Test uploading ML training code using the refactored method."""
    print("=" * 60)
    print("Testing ML Training Code Upload")
    print("=" * 60)
    
    ml_dir = os.path.abspath("examples/analytic-workflow/ml")
    
    print(f"\n📁 Source directory: {ml_dir}")
    print(f"📁 Exists: {os.path.exists(ml_dir)}")
    
    # List what will be uploaded
    print(f"\n📦 Files to upload:")
    notebook_count = 0
    for root, dirs, files in os.walk(ml_dir):
        dirs[:] = [d for d in dirs if d not in ['__pycache__', '.ipynb_checkpoints']]
        for file in files:
            if file.endswith('.ipynb'):
                rel_path = os.path.relpath(os.path.join(root, file), ml_dir)
                print(f"   - {rel_path}")
                notebook_count += 1
    
    print(f"\n📊 Total notebooks to upload: {notebook_count}")
    
    # Test sync command directly
    print(f"\n🔄 Testing sync command (dry-run)...")
    s3_uri = "s3://amazon-sagemaker-198737698272-us-east-2-b1rdp2ugixo97t/shared/ml/"
    
    cmd = ["aws", "s3", "sync", ml_dir, s3_uri, "--dryrun", 
           "--exclude", "*.pyc", 
           "--exclude", "__pycache__/*", 
           "--exclude", ".ipynb_checkpoints/*"]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        uploads = [line for line in result.stdout.split('\n') if 'upload:' in line and '.ipynb' in line]
        print(f"   Would upload {len(uploads)} notebook(s):")
        for line in uploads:
            filename = line.split('/')[-1]
            print(f"   - {filename}")
        
        if len(uploads) == notebook_count:
            print(f"\n✅ Dry-run successful - all notebooks would be uploaded")
        else:
            print(f"\n⚠️ Mismatch: {notebook_count} local notebooks but {len(uploads)} would upload")
    else:
        print(f"❌ Dry-run failed: {result.stderr}")
        return False
    
    # Verify current S3 state
    print(f"\n🔍 Checking current S3 state...")
    result = subprocess.run(
        ["aws", "s3", "ls", s3_uri, "--recursive"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        notebooks_in_s3 = [line for line in result.stdout.split('\n') if '.ipynb' in line and '.ipynb_checkpoints' not in line]
        print(f"   Found {len(notebooks_in_s3)} notebook(s) in S3:")
        for nb in notebooks_in_s3:
            parts = nb.split()
            if len(parts) >= 4:
                filename = parts[-1].split('/')[-1]
                timestamp = f"{parts[0]} {parts[1]}"
                print(f"   - {filename} (modified: {timestamp})")
        
        return len(notebooks_in_s3) == notebook_count
    else:
        print(f"❌ Failed to list S3: {result.stderr}")
        return False

if __name__ == "__main__":
    print("\nTesting Upload Code Functionality\n")
    
    # Ensure we're in the right directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    os.chdir(project_root)
    print(f"Working directory: {os.getcwd()}")
    
    success = test_ml_training_upload()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ All upload tests passed!")
        sys.exit(0)
    else:
        print("❌ Upload test failed")
        sys.exit(1)
