#!/usr/bin/env python3
"""
Combine coverage reports from multiple test runs.
Downloads artifacts from GitHub Actions and merges coverage data.
"""

import argparse
import glob
import os
import subprocess
import sys
from pathlib import Path


def combine_coverage_files(coverage_dir: str, output_dir: str):
    """Combine multiple coverage data files into a single report."""
    
    # Debug: Show what we're looking for
    print(f"🔍 Searching in: {os.path.abspath(coverage_dir)}")
    print(f"🔍 Output to: {os.path.abspath(output_dir)}")
    print()
    
    coverage_files = glob.glob(f"{coverage_dir}/**/coverage-*.data", recursive=True)
    
    if not coverage_files:
        print("⚠️  No coverage data files found")
        print("   Falling back to XML-only reports")
        xml_files = glob.glob(f"{coverage_dir}/**/coverage-*.xml", recursive=True)
        if xml_files:
            print(f"📊 Found {len(xml_files)} XML coverage files:")
            for f in xml_files:
                print(f"  - {os.path.basename(f)}")
        else:
            print("❌ No coverage files found at all")
        
        # Run debug script if available
        debug_script = os.path.join(os.path.dirname(__file__), "debug_coverage.sh")
        if os.path.exists(debug_script):
            print("\n🐛 Running debug script...")
            subprocess.run(["bash", debug_script], cwd=coverage_dir)
        
        return False
    
    print(f"📊 Found {len(coverage_files)} coverage data files:")
    for f in coverage_files:
        print(f"  - {os.path.basename(f)}")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # Copy and rename all coverage data files to .coverage format
        print("\n📦 Copying coverage data files...")
        for i, f in enumerate(coverage_files):
            basename = os.path.basename(f).replace('.data', '')
            dest = os.path.join(output_dir, f".coverage.{basename}")
            subprocess.run(["cp", f, dest], check=True)
            print(f"  - {basename}")
        
        # Combine coverage data
        print("📦 Combining coverage data...")
        subprocess.run(
            ["coverage", "combine"],
            check=True,
            cwd=output_dir
        )
        
        # Generate combined reports
        print("📄 Generating combined XML report...")
        subprocess.run(
            ["coverage", "xml", "-o", "coverage-combined.xml"],
            check=True,
            cwd=output_dir
        )
        
        print("📄 Generating combined HTML report...")
        subprocess.run(
            ["coverage", "html", "-d", "htmlcov-combined"],
            check=True,
            cwd=output_dir
        )
        
        print("📊 Coverage Summary:")
        result = subprocess.run(
            ["coverage", "report"],
            capture_output=True,
            text=True,
            cwd=output_dir
        )
        print(result.stdout)
    
    except subprocess.CalledProcessError as e:
        print(f"❌ Error combining coverage: {e}")
        return False
    
    print(f"\n✅ Combined coverage report saved to {output_dir}/")
    print(f"   View HTML: open {output_dir}/htmlcov-combined/index.html")
    return True


def main():
    parser = argparse.ArgumentParser(description="Combine coverage reports from GitHub artifacts")
    parser.add_argument(
        "--coverage-dir",
        default="coverage-artifacts",
        help="Directory containing downloaded coverage artifacts"
    )
    parser.add_argument(
        "--output-dir",
        default="coverage-combined",
        help="Output directory for combined coverage report"
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.coverage_dir):
        print(f"❌ Coverage directory not found: {args.coverage_dir}")
        print("\nTo download artifacts from GitHub:")
        print("  gh run download <RUN_ID> -n test-summary-combined")
        sys.exit(1)
    
    success = combine_coverage_files(args.coverage_dir, args.output_dir)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
