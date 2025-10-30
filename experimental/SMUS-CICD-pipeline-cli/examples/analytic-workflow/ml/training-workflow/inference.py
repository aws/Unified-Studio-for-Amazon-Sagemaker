import os
import joblib
import numpy as np
import pandas as pd
from io import StringIO

def model_fn(model_dir):
    """Load model and scaler from model directory"""
    model = joblib.load(os.path.join(model_dir, 'model.joblib'))
    scaler = joblib.load(os.path.join(model_dir, 'scaler.joblib'))
    return {'model': model, 'scaler': scaler}

def input_fn(request_body, content_type='text/csv'):
    """Parse input data"""
    if content_type == 'text/csv':
        df = pd.read_csv(StringIO(request_body))
        return df.values
    else:
        raise ValueError(f"Unsupported content type: {content_type}")

def predict_fn(input_data, model_dict):
    """Make predictions using loaded model and scaler"""
    scaler = model_dict['scaler']
    model = model_dict['model']
    
    # Scale input data
    input_scaled = scaler.transform(input_data)
    
    # Make predictions
    predictions = model.predict(input_scaled)
    
    return predictions

def output_fn(predictions, accept='text/csv'):
    """Format output"""
    import json
    if accept == 'text/csv':
        return '\n'.join(str(p) for p in predictions), accept
    elif accept == 'application/json':
        return json.dumps(predictions.tolist() if hasattr(predictions, 'tolist') else list(predictions)), accept
    else:
        raise ValueError(f"Unsupported accept type: {accept}")
