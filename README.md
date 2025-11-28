## Amazon SageMaker Unified Studio

This repository contains utilities for Amazon SageMaker Unified Studio. It is structured as follows: 
- Cloudformation
    - [Templates](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/tree/main/cloudformation) to setup and Create a new Amazon SageMaker Unified domain and project
- Migration 
    - Migrate [Amazon Athena](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/tree/main/migration/athena) and [Amazon EMR](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/tree/main/migration/emr) resources to SageMaker Unified Studio project. 
    - [Bring your own AWS Identity and Access Management (IAM) role](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/tree/main/migration/bring-your-own-role) in SageMaker Unified Studio project.
    - [Bring your own Glue Data Catalog assets](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/tree/main/migration/bring-your-own-gdc-assets) in SageMaker Unified Studio project.
    - [Bring your own S3 tables](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/tree/main/migration/bring-your-own-s3-tables) in SageMaker Unified Studio project.
    - Migrate [Amazon SageMaker AI](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/tree/main/migration/sagemaker-ai) resources to SageMaker Unified Studio project. 
- Experimental CICD Pipeline support. This library supports creation of CICD pipeline using SageMaker Unified Studio that allows bundling and deploying code to different stages of development. 
    - [experimental/SMUS-CICD-pipeline-cli](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/tree/main/experimental/SMUS-CICD-pipeline-cli)


To read more about Amazon SageMaker Unified Studio, please refer to:
- [Administrator Guide](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/adminguide/what-is-sagemaker-unified-studio.html)
- [User guide](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/userguide/what-is-sagemaker-unified-studio.html)

## Links
To learn more about use cases and hands-on instructions about Amazon SageMaker Unified Studio, we recommend to visit following blog posts.

- [Introducing the next generation of Amazon SageMaker: The center for all your data, analytics, and AI](https://aws.amazon.com/blogs/aws/introducing-the-next-generation-of-amazon-sagemaker-the-center-for-all-your-data-analytics-and-ai/): This is the launch news post of Amazon SageMaker Unified Studio.
- [The next generation of Amazon SageMaker: The center for all your data, analytics, and AI](https://aws.amazon.com/blogs/big-data/the-next-generation-of-amazon-sagemaker-the-center-for-all-your-data-analytics-and-ai/): This is the launch news post of Amazon SageMaker Unified Studio.
- [Author visual ETL flows on Amazon SageMaker Unified Studio](https://aws.amazon.com/blogs/big-data/author-visual-etl-flows-on-amazon-sagemaker-unified-studio/): This post describes how to use visual ETL flow.
- [An integrated experience for all your data and AI with Amazon SageMaker Unified Studio](https://aws.amazon.com/blogs/big-data/an-integrated-experience-for-all-your-data-and-ai-with-amazon-sagemaker-unified-studio/): This post describes how to get started for analytics workload.
- [Introducing a new unified data connection experience with Amazon SageMaker Lakehouse unified data connectivity](https://aws.amazon.com/blogs/big-data/introducing-a-new-unified-data-connection-experience-with-amazon-sagemaker-lakehouse-data-connectivity/): This post describes how to create the new Lakehouse connection and use it from different engines.
- [Simplify data access for your enterprise using Amazon SageMaker Lakehouse](https://aws.amazon.com/blogs/big-data/simplify-data-access-for-your-enterprise-using-amazon-sagemaker-lakehouse/): This post describes how to configure federated access.
- [Catalog and govern Amazon Athena federated queries with Amazon SageMaker Lakehouse](https://aws.amazon.com/blogs/big-data/catalog-and-govern-amazon-athena-federated-queries-with-amazon-sagemaker-lakehouse/): This post describes how to configure FGAC (Fine Grained Access Control) through SageMaker Lakehouse.


## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.

