import sys
import boto3
import joblib
import mlflow
import numpy as np
from awsglue.utils import getResolvedOptions
from sklearn.metrics import accuracy_score, classification_report

args = getResolvedOptions(sys.argv, ['JOB_NAME', 'MODEL_S3_PATH', 'MLFLOW_TRACKING_URI'])

# Set MLflow tracking URI
mlflow.set_tracking_uri(args['MLFLOW_TRACKING_URI'])

# Download model from S3
s3 = boto3.client('s3')
model_s3_path = args['MODEL_S3_PATH']
bucket = model_s3_path.split('/')[2]
key = '/'.join(model_s3_path.split('/')[3:]) + '/model.tar.gz'

print(f"Downloading model from {model_s3_path}")
s3.download_file(bucket, key, '/tmp/model.tar.gz')

# Extract and load model
import tarfile
with tarfile.open('/tmp/model.tar.gz', 'r:gz') as tar:
    tar.extractall('/tmp/model/')

model = joblib.load('/tmp/model/model.joblib')
scaler = joblib.load('/tmp/model/scaler.joblib')

# Create test data for evaluation
np.random.seed(42)
X_test = np.random.randn(100, 20)
y_test = np.random.choice([0, 1, 2], 100)

# Scale and predict
X_test_scaled = scaler.transform(X_test)
y_pred = model.predict(X_test_scaled)
accuracy = accuracy_score(y_test, y_pred)

print(f"Model evaluation accuracy: {accuracy:.4f}")

# Log to MLflow
with mlflow.start_run():
    mlflow.log_metric("evaluation_accuracy", accuracy)
    mlflow.log_param("evaluation_samples", len(y_test))
    
print("Model evaluation completed")
