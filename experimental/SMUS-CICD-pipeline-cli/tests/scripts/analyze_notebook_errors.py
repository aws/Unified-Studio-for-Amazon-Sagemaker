#!/usr/bin/env python3
"""Analyze executed notebooks for errors and failures."""

import argparse
import json
import sys
from pathlib import Path


def analyze_notebook(notebook_path: Path) -> dict:
    """Analyze a notebook for errors and return results."""
    with open(notebook_path) as f:
        nb = json.load(f)
    
    results = {
        "path": str(notebook_path),
        "total_cells": len(nb["cells"]),
        "errors": [],
        "has_errors": False
    }
    
    for i, cell in enumerate(nb["cells"]):
        for out in cell.get("outputs", []):
            out_type = out.get("output_type")
            
            # Check for error output type
            if out_type == "error":
                results["errors"].append({
                    "cell": i,
                    "type": "error",
                    "name": out.get("ename"),
                    "value": out.get("evalue"),
                    "traceback": out.get("traceback", [])
                })
                results["has_errors"] = True
            
            # Check for error in display_data (rich error formatting)
            elif out_type == "display_data":
                data = out.get("data", {})
                text_plain = "".join(data.get("text/plain", []))
                text_html = "".join(data.get("text/html", []))
                
                # Look for error indicators in rich output
                if any(indicator in text_plain.lower() for indicator in ["error", "exception", "traceback"]):
                    results["errors"].append({
                        "cell": i,
                        "type": "display_error",
                        "text": text_plain[:500]
                    })
                    results["has_errors"] = True
                elif "color: #ff0000" in text_html or "text-decoration-color: #ff0000" in text_html:
                    # Red text in HTML often indicates errors
                    results["errors"].append({
                        "cell": i,
                        "type": "display_error_html",
                        "html_snippet": text_html[:500]
                    })
                    results["has_errors"] = True
            
            # Check for error keywords in stream output
            elif out_type == "stream":
                text = "".join(out.get("text", []))
                if any(indicator in text.lower() for indicator in ["error:", "exception:", "traceback"]):
                    results["errors"].append({
                        "cell": i,
                        "type": "stream_error",
                        "text": text[:500]
                    })
                    results["has_errors"] = True
    
    return results


def print_results(results: dict, verbose: bool = False):
    """Print analysis results."""
    print(f"\n📓 Notebook: {results['path']}")
    print(f"   Total cells: {results['total_cells']}")
    
    if results["has_errors"]:
        print(f"   ❌ Found {len(results['errors'])} error(s)")
        for err in results["errors"]:
            print(f"\n   Cell {err['cell']} ({err['type']}):")
            if err["type"] == "error":
                print(f"      {err['name']}: {err['value']}")
                if verbose:
                    print("      Traceback:")
                    for line in err["traceback"][:5]:
                        print(f"         {line}")
            elif "text" in err:
                print(f"      {err['text'][:200]}")
            elif "html_snippet" in err:
                print(f"      HTML error detected (use --verbose for details)")
                if verbose:
                    print(f"      {err['html_snippet'][:300]}")
    else:
        print("   ✅ No errors found")
    
    return results["has_errors"]


def main():
    parser = argparse.ArgumentParser(description="Analyze notebooks for errors")
    parser.add_argument("notebook_path", nargs="?", help="Path to notebook or directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed error info")
    parser.add_argument("--open-errors", action="store_true", help="Open notebooks with errors")
    
    args = parser.parse_args()
    
    # Default to test outputs directory
    if not args.notebook_path:
        args.notebook_path = "tests/test-outputs/notebooks"
    
    path = Path(args.notebook_path)
    
    if not path.exists():
        print(f"❌ Path not found: {path}")
        return 1
    
    # Find all notebooks
    if path.is_file():
        notebooks = [path]
    else:
        notebooks = list(path.rglob("*.ipynb"))
    
    if not notebooks:
        print(f"❌ No notebooks found in {path}")
        return 1
    
    print(f"Analyzing {len(notebooks)} notebook(s)...")
    
    error_count = 0
    notebooks_with_errors = []
    
    for nb_path in notebooks:
        results = analyze_notebook(nb_path)
        has_errors = print_results(results, args.verbose)
        if has_errors:
            error_count += 1
            notebooks_with_errors.append(nb_path)
    
    print(f"\n{'='*60}")
    print(f"Summary: {error_count}/{len(notebooks)} notebook(s) with errors")
    
    if args.open_errors and notebooks_with_errors:
        print(f"\nOpening {len(notebooks_with_errors)} notebook(s) with errors...")
        import subprocess
        for nb in notebooks_with_errors:
            subprocess.run(["open", str(nb)])
    
    return 1 if error_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
