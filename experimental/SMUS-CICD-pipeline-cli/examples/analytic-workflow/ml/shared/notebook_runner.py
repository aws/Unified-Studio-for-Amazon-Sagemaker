#!/usr/bin/env python3

import subprocess
import sys
import os

def run_notebook():
    """Execute Jupyter notebook in SageMaker Processing job"""
    
    print("🚀 Starting ML Pipeline Notebook Execution")
    
    # Install required packages
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", 
        "jupyter", "nbconvert", "sagemaker", "mlflow", "scikit-learn", "pandas", "numpy"
    ])
    
    # Convert and execute notebook
    notebook_path = "/opt/ml/processing/input/ml_pipeline_notebook.ipynb"
    output_path = "/opt/ml/processing/output/"
    
    if os.path.exists(notebook_path):
        print(f"📓 Executing notebook: {notebook_path}")
        
        # Execute notebook and convert to HTML
        subprocess.check_call([
            "jupyter", "nbconvert", 
            "--to", "html",
            "--execute", 
            "--output-dir", output_path,
            notebook_path
        ])
        
        print("✅ Notebook execution completed successfully!")
        
        # Save execution summary
        with open(f"{output_path}/execution_summary.txt", "w") as f:
            f.write("ML Pipeline Notebook Execution Summary\n")
            f.write("=====================================\n")
            f.write("Status: SUCCESS\n")
            f.write("Notebook: ml_pipeline_notebook.ipynb\n")
            f.write("Output: HTML report generated\n")
        
    else:
        print(f"❌ Notebook not found: {notebook_path}")
        sys.exit(1)

if __name__ == "__main__":
    run_notebook()
