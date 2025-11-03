import os
import joblib
import pandas as pd
from io import StringIO

def model_fn(model_dir):
    """Load model and scaler"""
    model = joblib.load(os.path.join(model_dir, 'model.joblib'))
    scaler = joblib.load(os.path.join(model_dir, 'scaler.joblib'))
    return {'model': model, 'scaler': scaler}

def input_fn(request_body, content_type='text/csv'):
    """Parse input data"""
    if content_type == 'text/csv':
        first_line = request_body.split('\n')[0] if '\n' in request_body else request_body
        first_value = first_line.split(',')[0] if ',' in first_line else first_line
        
        try:
            float(first_value.strip())
            return pd.read_csv(StringIO(request_body), header=None)
        except (ValueError, TypeError):
            df = pd.read_csv(StringIO(request_body), header=0)
            df.columns = range(len(df.columns))
            return df
    raise ValueError(f"Unsupported content type: {content_type}")

def predict_fn(input_data, model_dict):
    """Make predictions"""
    scaler = model_dict['scaler']
    model = model_dict['model']
    scaled_data = scaler.transform(input_data)
    return model.predict(scaled_data)

def output_fn(prediction, accept='text/csv'):
    """Format output"""
    if accept == 'text/csv':
        return '\n'.join(str(p) for p in prediction)
    raise ValueError(f"Unsupported accept type: {accept}")
