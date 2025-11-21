import os
import joblib
import pandas as pd
import numpy as np
from io import StringIO
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, classification_report
import argparse

# MLflow integration
try:
    import mlflow
    import mlflow.sklearn
    mlflow_available = True
except ImportError:
    mlflow_available = False
    print("MLflow not available, skipping MLflow logging")

def create_synthetic_data():
    """Create realistic synthetic dataset"""
    np.random.seed(42)
    n_samples = 2000
    n_features = 20
    n_classes = 3
    
    # Create base features with some structure
    X = np.random.randn(n_samples, n_features)
    
    # Add some feature interactions and noise
    X[:, 0] = X[:, 1] * 0.5 + X[:, 2] * 0.3 + np.random.randn(n_samples) * 0.2
    X[:, 3] = X[:, 4] ** 2 + np.random.randn(n_samples) * 0.1
    
    # Create target with realistic class distribution
    y = np.random.choice(n_classes, n_samples, p=[0.5, 0.3, 0.2])
    
    # Add some predictive signal
    for i in range(n_classes):
        mask = y == i
        X[mask, i*3:(i+1)*3] += np.random.randn(np.sum(mask), 3) * 0.5 + i
    
    return X, y

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--n-estimators', type=int, default=100)
    parser.add_argument('--max-depth', type=int, default=10)
    parser.add_argument('--random-state', type=int, default=42)
    parser.add_argument('--model-name', type=str, default='realistic-classifier-v1')
    args = parser.parse_args()
    
    print(f"Training with parameters: n_estimators={args.n_estimators}, max_depth={args.max_depth}")
    
    # MLflow setup if available
    if mlflow_available:
        mlflow_tracking_uri = os.environ.get('MLFLOW_TRACKING_SERVER_ARN')
        if not mlflow_tracking_uri:
            raise ValueError("MLFLOW_TRACKING_SERVER_ARN environment variable is required but not set")
        
        # Import sagemaker_mlflow to enable ARN resolution
        try:
            import sagemaker_mlflow
        except ImportError:
            print("Warning: sagemaker_mlflow not available, ARN resolution may fail")
        
        mlflow.set_tracking_uri(mlflow_tracking_uri)
        print(f"MLflow tracking URI set to: {mlflow_tracking_uri}")
        
        # Set custom artifact location to project S3 bucket
        artifact_location = os.environ.get('MLFLOW_ARTIFACT_LOCATION')
        if artifact_location:
            os.environ['MLFLOW_ARTIFACT_URI'] = artifact_location
            print(f"MLflow artifact location set to: {artifact_location}")
        
        # Start MLflow run
        with mlflow.start_run():
            # Log parameters
            mlflow.log_param("n_estimators", args.n_estimators)
            mlflow.log_param("max_depth", args.max_depth)
            mlflow.log_param("random_state", args.random_state)
            mlflow.log_param("algorithm", "RandomForest")
            
            # Create synthetic data
            X, y = create_synthetic_data()
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=args.random_state)
            
            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Train model
            model = RandomForestClassifier(
                n_estimators=args.n_estimators, 
                max_depth=args.max_depth, 
                random_state=args.random_state
            )
            model.fit(X_train_scaled, y_train)
            
            # Evaluate
            y_pred = model.predict(X_test_scaled)
            accuracy = accuracy_score(y_test, y_pred)
            
            print(f"Model accuracy: {accuracy:.4f}")
            print(classification_report(y_test, y_pred))
            
            # Log metrics to MLflow
            mlflow.log_metric("accuracy", accuracy)
            mlflow.log_metric("n_samples", len(X))
            mlflow.log_metric("n_features", X.shape[1])
            mlflow.log_metric("n_classes", len(np.unique(y)))
            
            # Log model to MLflow
            mlflow.sklearn.log_model(
                model, 
                "model",
                registered_model_name=args.model_name
            )
            
            print(f"✅ Model logged to MLflow with name: {args.model_name}")
    else:
        # Fallback without MLflow
        print("Running without MLflow integration")
        X, y = create_synthetic_data()
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=args.random_state)
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        model = RandomForestClassifier(n_estimators=args.n_estimators, max_depth=args.max_depth, random_state=args.random_state)
        model.fit(X_train_scaled, y_train)
        y_pred = model.predict(X_test_scaled)
        accuracy = accuracy_score(y_test, y_pred)
        print(f"Model accuracy: {accuracy:.4f}")
    
    # Save model and scaler for SageMaker
    model_dir = os.environ.get('SM_MODEL_DIR', '/opt/ml/model')
    os.makedirs(model_dir, exist_ok=True)
    
    joblib.dump(model, os.path.join(model_dir, 'model.joblib'))
    joblib.dump(scaler, os.path.join(model_dir, 'scaler.joblib'))
    
    # Copy inference script to model directory for batch transform
    import shutil
    code_dir = os.path.join(model_dir, 'code')
    os.makedirs(code_dir, exist_ok=True)
    
    print("Model training completed and saved")


# Inference functions for SageMaker
def model_fn(model_dir):
    """Load model for inference"""
    model = joblib.load(os.path.join(model_dir, 'model.joblib'))
    scaler = joblib.load(os.path.join(model_dir, 'scaler.joblib'))
    return {'model': model, 'scaler': scaler}


def input_fn(request_body, content_type='text/csv'):
    """Parse input data"""
    if content_type == 'text/csv':
        # First, try to detect if there's a header
        first_line = request_body.split('\n')[0] if '\n' in request_body else request_body
        first_value = first_line.split(',')[0] if ',' in first_line else first_line
        
        # Check if first value is numeric
        try:
            float(first_value.strip())
            # First row is numeric, no header
            return pd.read_csv(StringIO(request_body), header=None)
        except (ValueError, TypeError):
            # First row is non-numeric, skip it and return data without column names
            df = pd.read_csv(StringIO(request_body), header=0)
            # Reset column names to numeric indices
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
