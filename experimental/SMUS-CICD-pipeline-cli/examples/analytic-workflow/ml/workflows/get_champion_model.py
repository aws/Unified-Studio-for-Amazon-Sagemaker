import sys
import mlflow
from awsglue.utils import getResolvedOptions

args = getResolvedOptions(sys.argv, ['JOB_NAME', 'MODEL_NAME', 'MLFLOW_TRACKING_URI', 'STAGE'])

# Set MLflow tracking URI
mlflow.set_tracking_uri(args['MLFLOW_TRACKING_URI'])

model_name = args['MODEL_NAME']
stage = args['STAGE']

print(f"Retrieving champion model for {model_name} in {stage} stage")

try:
    # Get champion model using alias
    client = mlflow.MlflowClient()
    champion_version = client.get_model_version_by_alias(model_name, "champion")
    
    # Get model S3 path
    model_s3_path = champion_version.source
    
    print(f"Champion model found: version {champion_version.version}")
    print(f"Model S3 path: {model_s3_path}")
    
    # Output for XCom
    print(f"champion_model_s3_path={model_s3_path}")
    
except Exception as e:
    print(f"Error retrieving champion model: {str(e)}")
    raise

print("Champion model retrieval completed")
