#!/usr/bin/env python3
"""
Airflow DAG for ML Model Inference Pipeline
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.amazon.aws.operators.sagemaker import (
    SageMakerTrainingOperator,
    SageMakerModelOperator,
    SageMakerEndpointConfigOperator,
    SageMakerEndpointOperator,
    SageMakerTransformOperator
)
from airflow.providers.python.operators.python import PythonOperator
from airflow_tasks import (
    tag_champion_model_task,
    test_endpoint_task,
    create_test_data_task,
    validate_batch_results_task,
    cleanup_resources_task
)

# DAG configuration
default_args = {
    'owner': 'ml-team',
    'depends_on_past': False,
    'start_date': datetime(2024, 10, 18),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Constants
BUCKET_NAME = 'sagemaker-ml-workflow-058264284947-us-east-1'
ROLE_ARN = 'arn:aws:iam::058264284947:role/service-role/AmazonSageMaker-ExecutionRole-20241115T121975'
MLFLOW_ARN = 'arn:aws:sagemaker:us-east-1:058264284947:mlflow-tracking-server/wine-classification-mlflow-v2'
REGION = 'us-east-1'

# Create DAG
dag = DAG(
    'ml_model_inference_pipeline',
    default_args=default_args,
    description='Complete ML pipeline with SageMaker endpoint deployment',
    schedule_interval=None,  # Manual trigger
    catchup=False,
    tags=['ml', 'sagemaker', 'inference', 'mlflow']
)

# Task 1: Train Model
train_model = SageMakerTrainingOperator(
    task_id='train_model',
    config={
        'TrainingJobName': 'airflow-ml-training-{{ ds_nodash }}',
        'AlgorithmSpecification': {
            'TrainingImage': '683313688378.dkr.ecr.us-east-1.amazonaws.com/sagemaker-scikit-learn:1.2-1-cpu-py3',
            'TrainingInputMode': 'File'
        },
        'RoleArn': ROLE_ARN,
        'OutputDataConfig': {
            'S3OutputPath': f's3://{BUCKET_NAME}/airflow-models/'
        },
        'ResourceConfig': {
            'InstanceType': 'ml.m5.large',
            'InstanceCount': 1,
            'VolumeSizeInGB': 30
        },
        'StoppingCondition': {
            'MaxRuntimeInSeconds': 3600
        },
        'HyperParameters': {
            'n-estimators': '100',
            'max-depth': '6',
            'random-state': '42'
        },
        'Environment': {
            'MLFLOW_TRACKING_SERVER_ARN': MLFLOW_ARN
        }
    },
    dag=dag
)

# Task 2: Tag Champion Model
tag_champion = PythonOperator(
    task_id='tag_champion_model',
    python_callable=tag_champion_model_task,
    op_kwargs={
        'model_name': 'realistic-classifier-v1',
        'tracking_server_arn': MLFLOW_ARN
    },
    dag=dag
)

# Task 3: Create SageMaker Model
create_model = SageMakerModelOperator(
    task_id='create_model',
    config={
        'ModelName': 'airflow-ml-model-{{ ds_nodash }}',
        'PrimaryContainer': {
            'Image': '683313688378.dkr.ecr.us-east-1.amazonaws.com/sagemaker-scikit-learn:1.2-1-cpu-py3',
            'ModelDataUrl': '{{ ti.xcom_pull(task_ids="train_model")["Training"]["ModelArtifacts"]["S3ModelArtifacts"] }}',
            'Environment': {
                'SAGEMAKER_PROGRAM': 'inference.py',
                'SAGEMAKER_SUBMIT_DIRECTORY': '/opt/ml/code'
            }
        },
        'ExecutionRoleArn': ROLE_ARN
    },
    dag=dag
)

# Task 4: Create Endpoint Configuration
create_endpoint_config = SageMakerEndpointConfigOperator(
    task_id='create_endpoint_config',
    config={
        'EndpointConfigName': 'airflow-ml-config-{{ ds_nodash }}',
        'ProductionVariants': [{
            'VariantName': 'primary',
            'ModelName': 'airflow-ml-model-{{ ds_nodash }}',
            'InitialInstanceCount': 1,
            'InstanceType': 'ml.m5.large',
            'InitialVariantWeight': 1.0
        }]
    },
    dag=dag
)

# Task 5: Deploy Endpoint
deploy_endpoint = SageMakerEndpointOperator(
    task_id='deploy_endpoint',
    config={
        'EndpointName': 'airflow-ml-endpoint-{{ ds_nodash }}',
        'EndpointConfigName': 'airflow-ml-config-{{ ds_nodash }}'
    },
    wait_for_completion=True,
    check_interval=30,
    max_ingestion_time=1800,
    dag=dag
)

# Task 6: Test Endpoint
test_endpoint = PythonOperator(
    task_id='test_endpoint',
    python_callable=test_endpoint_task,
    op_kwargs={
        'endpoint_name': 'airflow-ml-endpoint-{{ ds_nodash }}',
        'region_name': REGION
    },
    dag=dag
)

# Task 7: Create Test Data for Batch Inference
create_test_data = PythonOperator(
    task_id='create_test_data',
    python_callable=create_test_data_task,
    op_kwargs={
        'bucket_name': BUCKET_NAME
    },
    dag=dag
)

# Task 8: Run Batch Transform
batch_inference = SageMakerTransformOperator(
    task_id='batch_inference',
    config={
        'TransformJobName': 'airflow-batch-inference-{{ ds_nodash }}',
        'ModelName': 'airflow-ml-model-{{ ds_nodash }}',
        'TransformInput': {
            'DataSource': {
                'S3DataSource': {
                    'S3DataType': 'S3Prefix',
                    'S3Uri': f's3://{BUCKET_NAME}/batch-inference/input/'
                }
            },
            'ContentType': 'text/csv',
            'SplitType': 'Line'
        },
        'TransformOutput': {
            'S3OutputPath': f's3://{BUCKET_NAME}/batch-inference/output-airflow/',
            'Accept': 'text/csv'
        },
        'TransformResources': {
            'InstanceType': 'ml.m5.large',
            'InstanceCount': 1
        }
    },
    wait_for_completion=True,
    check_interval=30,
    dag=dag
)

# Task 9: Validate Results
validate_results = PythonOperator(
    task_id='validate_results',
    python_callable=validate_batch_results_task,
    op_kwargs={
        'bucket_name': BUCKET_NAME,
        'output_prefix': 'batch-inference/output-airflow/'
    },
    dag=dag
)

# Task 10: Cleanup Resources
cleanup = PythonOperator(
    task_id='cleanup_resources',
    python_callable=cleanup_resources_task,
    op_kwargs={
        'endpoint_name': 'airflow-ml-endpoint-{{ ds_nodash }}',
        'model_name': 'airflow-ml-model-{{ ds_nodash }}',
        'endpoint_config_name': 'airflow-ml-config-{{ ds_nodash }}',
        'region_name': REGION
    },
    trigger_rule='all_done',  # Run even if previous tasks fail
    dag=dag
)

# Define task dependencies
train_model >> tag_champion >> create_model >> create_endpoint_config >> deploy_endpoint
deploy_endpoint >> test_endpoint
test_endpoint >> create_test_data >> batch_inference >> validate_results
validate_results >> cleanup
