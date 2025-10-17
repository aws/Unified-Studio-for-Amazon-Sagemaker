# AWS Airflow Operators Reference

This document provides a comprehensive list of AWS operators available for Apache Airflow workflows in SageMaker Unified Studio.

## Core Operators

### EmptyOperator
- **[EmptyOperator](https://airflow.apache.org/docs/apache-airflow/stable/_api/airflow/operators/empty/index.html)** - No-op operator for workflow control

## AWS Service Operators

### Amazon SageMaker
- **[SageMakerNotebookOperator](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/operators/sagemaker/index.html#airflow.providers.amazon.aws.operators.sagemaker.SageMakerNotebookOperator)** - Manage SageMaker notebooks
- **[SageMakerProcessingOperator](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/operators/sagemaker/index.html#airflow.providers.amazon.aws.operators.sagemaker.SageMakerProcessingOperator)** - Run processing jobs
- **[SageMakerTrainingOperator](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/operators/sagemaker/index.html#airflow.providers.amazon.aws.operators.sagemaker.SageMakerTrainingOperator)** - Execute training jobs
- **[SageMakerEndpointOperator](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/operators/sagemaker/index.html#airflow.providers.amazon.aws.operators.sagemaker.SageMakerEndpointOperator)** - Deploy model endpoints
- **[SageMakerModelOperator](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/operators/sagemaker/index.html#airflow.providers.amazon.aws.operators.sagemaker.SageMakerModelOperator)** - Create models
- **[SageMakerStartPipelineOperator](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/operators/sagemaker/index.html#airflow.providers.amazon.aws.operators.sagemaker.SageMakerStartPipelineOperator)** - Start ML pipelines

### Amazon Athena
- **[AthenaOperator](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/operators/athena/index.html#airflow.providers.amazon.aws.operators.athena.AthenaOperator)** - Execute Athena queries

### Amazon EMR
- **[EmrAddStepsOperator](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/operators/emr/index.html#airflow.providers.amazon.aws.operators.emr.EmrAddStepsOperator)** - Add steps to EMR cluster
- **[EmrCreateJobFlowOperator](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/operators/emr/index.html#airflow.providers.amazon.aws.operators.emr.EmrCreateJobFlowOperator)** - Create EMR cluster
- **[EmrContainerOperator](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/operators/emr/index.html#airflow.providers.amazon.aws.operators.emr.EmrContainerOperator)** - Run EMR on EKS jobs
- **[EmrServerlessStartJobOperator](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/operators/emr/index.html#airflow.providers.amazon.aws.operators.emr.EmrServerlessStartJobOperator)** - Start EMR Serverless jobs

### Amazon S3
- **[S3CreateBucketOperator](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/operators/s3/index.html#airflow.providers.amazon.aws.operators.s3.S3CreateBucketOperator)** - Create S3 buckets
- **[S3CopyObjectOperator](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/operators/s3/index.html#airflow.providers.amazon.aws.operators.s3.S3CopyObjectOperator)** - Copy S3 objects
- **[S3DeleteObjectsOperator](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/operators/s3/index.html#airflow.providers.amazon.aws.operators.s3.S3DeleteObjectsOperator)** - Delete S3 objects
- **[S3ListOperator](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/operators/s3/index.html#airflow.providers.amazon.aws.operators.s3.S3ListOperator)** - List S3 objects

### AWS Glue
- **[GlueJobOperator](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/operators/glue/index.html#airflow.providers.amazon.aws.operators.glue.GlueJobOperator)** - Run Glue jobs
- **[GlueCrawlerOperator](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/operators/glue/index.html#airflow.providers.amazon.aws.operators.glue.GlueCrawlerOperator)** - Run Glue crawlers
- **[GlueDataQualityOperator](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/operators/glue/index.html#airflow.providers.amazon.aws.operators.glue.GlueDataQualityOperator)** - Data quality checks

### Amazon Redshift
- **[RedshiftDataOperator](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/operators/redshift_data/index.html#airflow.providers.amazon.aws.operators.redshift_data.RedshiftDataOperator)** - Execute Redshift queries
- **[RedshiftCreateClusterOperator](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/operators/redshift_cluster/index.html#airflow.providers.amazon.aws.operators.redshift_cluster.RedshiftCreateClusterOperator)** - Create Redshift clusters

### AWS Lambda
- **[LambdaInvokeFunctionOperator](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/operators/lambda_function/index.html#airflow.providers.amazon.aws.operators.lambda_function.LambdaInvokeFunctionOperator)** - Invoke Lambda functions

### Amazon EC2
- **[EC2StartInstanceOperator](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/operators/ec2/index.html#airflow.providers.amazon.aws.operators.ec2.EC2StartInstanceOperator)** - Start EC2 instances
- **[EC2StopInstanceOperator](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/operators/ec2/index.html#airflow.providers.amazon.aws.operators.ec2.EC2StopInstanceOperator)** - Stop EC2 instances

### AWS Step Functions
- **[StepFunctionStartExecutionOperator](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/operators/step_function/index.html#airflow.providers.amazon.aws.operators.step_function.StepFunctionStartExecutionOperator)** - Start Step Functions executions

## Sensors

### Amazon S3
- **[S3KeySensor](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/sensors/s3/index.html#airflow.providers.amazon.aws.sensors.s3.S3KeySensor)** - Wait for S3 objects

### Amazon SageMaker
- **[SageMakerTrainingSensor](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/sensors/sagemaker/index.html#airflow.providers.amazon.aws.sensors.sagemaker.SageMakerTrainingSensor)** - Monitor training jobs
- **[SageMakerEndpointSensor](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/sensors/sagemaker/index.html#airflow.providers.amazon.aws.sensors.sagemaker.SageMakerEndpointSensor)** - Monitor endpoints

### Amazon EMR
- **[EmrJobFlowSensor](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/sensors/emr/index.html#airflow.providers.amazon.aws.sensors.emr.EmrJobFlowSensor)** - Monitor EMR clusters
- **[EmrStepSensor](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/_api/airflow/providers/amazon/aws/sensors/emr/index.html#airflow.providers.amazon.aws.sensors.emr.EmrStepSensor)** - Monitor EMR steps

## Usage Example

```python
from airflow import DAG
from airflow.providers.amazon.aws.operators.sagemaker import SageMakerTrainingOperator
from airflow.providers.amazon.aws.operators.s3 import S3CopyObjectOperator

dag = DAG('ml_pipeline', schedule_interval='@daily')

train_model = SageMakerTrainingOperator(
    task_id='train_model',
    config={...},
    dag=dag
)

copy_results = S3CopyObjectOperator(
    task_id='copy_results',
    source_bucket_key='model/output',
    dest_bucket_key='production/model',
    dag=dag
)

train_model >> copy_results
```

## Resources

- [Apache Airflow AWS Provider Documentation](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/)
- [SageMaker Unified Studio User Guide](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/userguide/)
