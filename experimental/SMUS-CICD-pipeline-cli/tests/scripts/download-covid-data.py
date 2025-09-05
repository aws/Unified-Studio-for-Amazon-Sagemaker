#!/usr/bin/env python3
"""
Download COVID-19 dataset from GitHub releases.
"""

import argparse
import requests
import zipfile
import os
from pathlib import Path


def download_covid_data(output_dir):
    """Download COVID-19 dataset from GitHub releases."""
    print("📥 Downloading COVID-19 dataset...")
    
    # GitHub releases URL for the dataset
    url = "https://github.com/datasets/covid-19/archive/refs/heads/main.zip"
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    zip_file = output_path / "covid-19.zip"
    extract_dir = output_path / "covid-19"
    
    # Download the zip file
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    with open(zip_file, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    
    print(f"✅ Downloaded to {zip_file}")
    
    # Extract the zip file
    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
        zip_ref.extractall(output_path)
    
    # Move contents from covid-19-main to covid-19
    main_dir = output_path / "covid-19-main"
    if main_dir.exists():
        if extract_dir.exists():
            import shutil
            shutil.rmtree(extract_dir)
        main_dir.rename(extract_dir)
    
    # Clean up zip file
    zip_file.unlink()
    
    print(f"✅ Extracted to {extract_dir}")
    
    # List CSV files found
    csv_files = list(extract_dir.glob("**/*.csv"))
    print(f"📊 Found {len(csv_files)} CSV files:")
    for csv_file in csv_files:
        print(f"  - {csv_file.name}")
    
    return extract_dir


def main():
    parser = argparse.ArgumentParser(description='Download COVID-19 dataset')
    parser.add_argument('--output', default='.', help='Output directory')
    
    args = parser.parse_args()
    
    try:
        result_dir = download_covid_data(args.output)
        print(f"\n🎉 COVID-19 dataset ready at: {result_dir}")
        print(f"💡 Use this path with setup-covid-data.py: --data-path {result_dir}")
    except Exception as e:
        print(f"❌ Error downloading dataset: {e}")


if __name__ == "__main__":
    main()
