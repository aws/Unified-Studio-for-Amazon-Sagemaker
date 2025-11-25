[![en](https://img.shields.io/badge/lang-en-gray.svg)](../../../README.md)
[![pt](https://img.shields.io/badge/lang-pt-gray.svg)](../pt/README.md)
[![fr](https://img.shields.io/badge/lang-fr-gray.svg)](../fr/README.md)
[![it](https://img.shields.io/badge/lang-it-gray.svg)](../it/README.md)
[![ja](https://img.shields.io/badge/lang-ja-gray.svg)](../ja/README.md)
[![zh](https://img.shields.io/badge/lang-zh-brightgreen.svg?style=for-the-badge)](../zh/README.md)
[![he](https://img.shields.io/badge/lang-he-gray.svg)](../he/README.md)

# SMUS CI/CD Pipeline CLI

← [Back to Main README](../../../README.md)


**自动化部署数据应用到SageMaker Unified Studio环境**

从开发到生产环境，自信地部署Airflow DAGs、Jupyter notebooks和ML workflow。专为与DevOps团队合作的数据科学家、数据工程师、ML工程师和生成式AI应用开发者打造。

**适配您的部署策略：** 无论您使用git分支（基于分支）、版本化制品（基于bundle）、git标签（基于标签）还是直接部署 - 这个CLI都支持您的workflow。只需定义一次应用，按照您的方式部署。

---

## 为什么选择 SMUS CI/CD CLI？

✅ **AWS 抽象层** - CLI 封装了所有 AWS 分析、ML 和 SMUS 的复杂性 - DevOps 团队无需直接调用 AWS API  
✅ **关注点分离** - 数据团队定义需要部署什么(manifest.yaml)，DevOps 团队定义如何以及何时部署(CI/CD workflow)  
✅ **通用 CI/CD Workflows** - 同一个 workflow 适用于 Glue、SageMaker、Bedrock、QuickSight 或任何 AWS 服务组合  
✅ **部署更有信心** - 生产环境前进行自动化测试和验证  
✅ **多环境管理** - 从测试到生产环境，具有环境特定的配置  
✅ **基础设施即代码** - 版本控制的应用 manifest 和可重现的部署  
✅ **事件驱动 Workflow** - 通过 EventBridge 在部署时自动触发 workflow  

---

## 快速入门

**从源代码安装：**
```bash
git clone https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker.git
cd Unified-Studio-for-Amazon-Sagemaker/experimental/SMUS-CICD-pipeline-cli
pip install -e .
```

**部署你的第一个应用：**
```bash
# 验证配置
smus-cli describe --manifest manifest.yaml --connect

# 创建部署 bundle（可选）
smus-cli bundle --manifest manifest.yaml

# 部署到测试环境
smus-cli deploy --targets test --manifest manifest.yaml

# 运行验证测试
smus-cli test --manifest manifest.yaml --targets test
```

**查看运行实例：** [Live GitHub Actions Example](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/actions/runs/17631303500)

---

## 适用对象

### 👨‍💻 数据团队（数据科学家、数据工程师、生成式 AI 应用开发者）
**您专注于:** 您的应用 - 部署什么、部署到哪里以及如何运行  
**您定义:** 应用程序 manifest (`manifest.yaml`) 包含您的代码、workflow 和配置  
**您无需了解:** CI/CD pipeline、GitHub Actions、部署自动化  

→ **[快速入门指南](docs/getting-started/quickstart.md)** - 10分钟内部署您的第一个应用  

**包含以下示例:**
- 数据工程 (Glue, Notebooks, Athena)
- ML Workflow (SageMaker, Notebooks)
- 生成式 AI 应用 (Bedrock, Notebooks)

**Bootstrap Actions - 自动化部署后任务:**

在您的 manifest 中定义部署后自动运行的操作:
- 立即触发 workflow（无需手动执行）
- 使用最新数据刷新 QuickSight 仪表板
- 为实验跟踪配置 MLflow 连接
- 获取日志进行验证
- 发出事件以触发下游流程

示例:
```yaml
bootstrap:
  actions:
    - type: workflow.run
      workflowName: etl_pipeline
      wait: true
    - type: quicksight.refresh_dataset
      refreshScope: IMPORTED
```

### 🔧 DevOps 团队
**您专注于:** CI/CD 最佳实践、安全性、合规性和部署自动化  
**您定义:** 强制执行测试、审批和晋升策略的 workflow 模板  
**您无需了解:** 应用程序具体细节、AWS 服务使用情况、DataZone API、SMUS 项目结构或业务逻辑  

→ **[管理员指南](docs/getting-started/admin-quickstart.md)** - 15分钟内配置基础设施和 pipeline  
→ **[GitHub Workflow 模板](git-templates/)** - 用于自动部署的通用、可重用 workflow 模板

**CLI 是您的抽象层:** 您只需调用 `smus-cli deploy` - CLI 处理所有 AWS 服务交互（DataZone、Glue、Athena、SageMaker、MWAA、S3、IAM 等）并执行 bootstrap actions（workflow 运行、日志流式处理、QuickSight 刷新、EventBridge 事件）。您的 workflow 保持简单和通用。

---

## 主要特点

### 🚀 自动化部署
- **应用程序manifest** - 在YAML中定义应用程序内容、workflow和部署目标
- **灵活部署** - 基于bundle（制品）或直接（基于git）的部署模式
- **多目标部署** - 使用单个命令部署到测试和生产环境
- **环境变量** - 使用`${VAR}`替换实现动态配置
- **版本控制** - 在S3或git中跟踪部署历史

### 🔍 测试和验证
- **自动化测试** - 在升级到生产环境前运行验证测试
- **质量门禁** - 测试失败时阻止部署
- **workflow监控** - 跟踪执行状态和日志
- **健康检查** - 验证部署正确性

### 🔄 CI/CD Pipeline集成
- **GitHub Actions** - 预构建的CI/CD pipeline workflow用于自动部署
- **GitLab CI** - 原生支持GitLab CI/CD pipeline
- **环境变量** - 适用于任何CI/CD平台的灵活配置
- **Webhook支持** - 从外部事件触发部署

### 🏗️ 基础设施管理
- **项目创建** - 自动配置SageMaker Unified Studio项目
- **连接设置** - 配置S3、Airflow、Athena和Lakehouse连接
- **资源映射** - 将AWS资源链接到项目连接
- **权限管理** - 控制访问和协作

### ⚡ 引导动作
- **自动workflow执行** - 使用`workflow.run`在部署期间自动触发workflow（使用`trailLogs: true`来流式传输日志并等待完成）
- **日志获取** - 使用`workflow.logs`获取workflow日志用于验证和调试
- **QuickSight数据集刷新** - 使用`quicksight.refresh_dataset`在ETL部署后自动刷新仪表板
- **EventBridge集成** - 使用`eventbridge.put_events`发出自定义事件用于下游自动化和CI/CD编排
- **DataZone连接** - 在部署期间配置MLflow和其他服务连接
- **顺序执行** - 动作在`smus-cli deploy`期间按顺序运行，确保可靠的初始化和验证

### 📊 目录集成
- **资产发现** - 自动查找所需的目录资产（Glue、Lake Formation、DataZone）
- **订阅管理** - 请求访问表格和数据集
- **审批workflow** - 处理跨项目数据访问
- **资产跟踪** - 监控目录依赖关系

---

## 可以部署什么？

**📊 分析和商业智能**
- Glue ETL 作业和爬虫
- Athena 查询
- QuickSight 仪表板
- EMR 作业（未来）
- Redshift 查询（未来）

**🤖 机器学习**
- SageMaker 训练作业
- ML 模型和端点
- MLflow 实验
- Feature Store（未来）
- 批量转换（未来）

**🧠 生成式 AI**
- Bedrock agents
- 知识库
- 基础模型配置（未来）

**📓 代码和 workflow**
- Jupyter notebooks
- Python 脚本
- Airflow DAGs（MWAA 和 Amazon MWAA Serverless）
- Lambda 函数（未来）

**💾 数据和存储**
- S3 数据文件
- Git 仓库
- 数据目录（未来）

---

## 支持的AWS服务

使用Airflow YAML语法通过以下AWS服务部署workflow：

### 🎯 分析与数据
**Amazon Athena** • **AWS Glue** • **Amazon EMR** • **Amazon Redshift** • **Amazon QuickSight** • **Lake Formation**

### 🤖 机器学习
**SageMaker Training** • **SageMaker Pipelines** • **Feature Store** • **Model Registry** • **Batch Transform**

### 🧠 生成式AI
**Amazon Bedrock** • **Bedrock Agents** • **Bedrock Knowledge Bases** • **Guardrails**

### 📊 其他服务
S3 • Lambda • Step Functions • DynamoDB • RDS • SNS/SQS • Batch

**查看完整列表：** [Airflow AWS Operators Reference](docs/airflow-aws-operators.md)

---

## 核心概念

### 关注点分离：关键设计原则

**问题：**传统部署方法迫使 DevOps 团队学习 AWS 分析服务（Glue、Athena、DataZone、SageMaker、MWAA 等）并理解 SMUS 项目结构，或迫使数据团队成为 CI/CD 专家。

**解决方案：**SMUS CLI 是封装所有 AWS 和 SMUS 复杂性的抽象层：

```
数据团队                      SMUS CLI                         DevOps 团队
    ↓                            ↓                                  ↓
manifest.yaml          smus-cli deploy                    GitHub Actions
(做什么和在哪里)        (AWS 抽象层)                       (如何做和何时做)
```

**数据团队专注于：**
- 应用代码和 workflow
- 使用哪些 AWS 服务（Glue、Athena、SageMaker 等）
- 环境配置
- 业务逻辑

**SMUS CLI 处理所有 AWS 复杂性：**
- DataZone 域和项目管理
- AWS Glue、Athena、SageMaker、MWAA API
- S3 存储和工件管理
- IAM 角色和权限
- 连接配置
- 目录资产订阅
- Workflow 部署到 Airflow
- 基础设施配置
- 测试和验证

**DevOps 团队专注于：**
- CI/CD 最佳实践（测试、审批、通知）
- 安全和合规检查
- 部署编排
- 监控和告警

**结果：**
- 数据团队永远不接触 CI/CD 配置
- **DevOps 团队永远不直接调用 AWS API** - 他们只需调用 `smus-cli deploy`
- **CI/CD workflow 是通用的** - 同样的 workflow 适用于 Glue 应用、SageMaker 应用或 Bedrock 应用
- 两个团队都能独立运用各自的专长工作

---

### 应用 Manifest
一个声明式 YAML 文件（`manifest.yaml`）定义您的数据应用：
- **应用详情** - 名称、版本、描述
- **内容** - 来自 git 仓库的代码、来自存储的数据/模型、QuickSight 仪表板
- **Workflow** - 用于编排和自动化的 Airflow DAG
- **Stage** - 部署位置（开发、测试、生产环境）
- **配置** - 特定环境的设置、连接和引导操作

**由数据团队创建和拥有。**定义**部署什么**和**部署到哪里**。无需 CI/CD 知识。

### 应用
您要部署的数据/分析工作负载：
- Airflow DAG 和 Python 脚本
- Jupyter notebook 和数据文件
- ML 模型和训练代码
- ETL pipeline 和转换
- GenAI 代理和 MCP 服务器
- 基础模型配置

### Stage
映射到 SageMaker Unified Studio 项目的部署环境（开发、测试、生产）：
- 域和区域配置
- 项目名称和设置
- 资源连接（S3、Airflow、Athena、Glue）
- 特定环境的参数
- 基于 git 部署的可选分支映射

### Workflow
执行应用的编排逻辑。Workflow 服务于两个目的：

**1. 部署时：**在部署期间创建所需的 AWS 资源
- 配置基础设施（S3 存储桶、数据库、IAM 角色）
- 配置连接和权限
- 设置监控和日志记录

**2. 运行时：**执行持续的数据和 ML pipeline
- 计划执行（每日、每小时等）
- 事件驱动触发（S3 上传、API 调用）
- 数据处理和转换
- 模型训练和推理

Workflow 以 YAML 格式定义为 Airflow DAG（有向无环图）。支持 [MWAA (Managed Workflows for Apache Airflow)](https://aws.amazon.com/managed-workflows-for-apache-airflow/) 和 [Amazon MWAA Serverless](https://aws.amazon.com/blogs/big-data/introducing-amazon-mwaa-serverless/)（[用户指南](https://docs.aws.amazon.com/mwaa/latest/mwaa-serverless-userguide/what-is-mwaa-serverless.html)）。

### CI/CD 自动化
自动化部署的 GitHub Actions workflow（或其他 CI/CD 系统）：
- **由 DevOps 团队创建和拥有**
- 定义**如何**和**何时**部署
- 运行测试和质量检查
- 管理跨目标的升级
- 执行安全和合规策略
- 示例：`.github/workflows/deploy.yml`

**关键见解：**DevOps 团队创建适用于任何应用的通用、可重用 workflow。他们不需要知道应用是使用 Glue、SageMaker 还是 Bedrock - CLI 处理所有 AWS 服务交互。workflow 只需调用 `smus-cli deploy`，CLI 完成其余工作。

### 部署模式

**基于 bundle（工件）：**创建版本化归档 → 将归档部署到各个 stage
- 适用于：审计跟踪、回滚能力、合规性
- 命令：`smus-cli bundle` 然后 `smus-cli deploy --manifest app.tar.gz`

**直接（基于 Git）：**无中间工件直接从源代码部署
- 适用于：更简单的 workflow、快速迭代、以 git 为真实来源
- 命令：`smus-cli deploy --manifest manifest.yaml --stage test`

两种模式都适用于任何存储和 git 内容源的组合。

---

### 所有组件如何协同工作

```
1. 数据团队                    2. DevOps 团队                 3. SMUS CLI（抽象层）
   ↓                               ↓                              ↓
创建 manifest.yaml          创建通用 workflow               Workflow 调用：
- Glue 作业                  - 合并时测试                    smus-cli deploy --manifest manifest.yaml
- SageMaker 训练            - 生产环境审批                     ↓
- Athena 查询               - 安全扫描                      CLI 处理所有 AWS 复杂性：
- S3 位置                   - 通知规则                      - DataZone API
                                                          - Glue/Athena/SageMaker API
                           适用于任何应用！                  - MWAA 部署
                           无需 AWS 知识！                   - S3 管理
                                                          - IAM 配置
                                                          - 基础设施配置
                                                            ↓
                                                          成功！
```

**优点：**
- 数据团队永远不需要学习 GitHub Actions
- **DevOps 团队永远不调用 AWS API** - CLI 封装了所有 AWS 分析、ML 和 SMUS 复杂性
- CI/CD workflow 很简单：只需调用 `smus-cli deploy`
- 同样的 workflow 适用于任何应用，无论使用哪些 AWS 服务

---

## Example Applications

Real-world examples showing how to deploy different workloads with SMUS CI/CD.

### 📊 Analytics - QuickSight Dashboard
Deploy interactive BI dashboards with automated Glue ETL pipelines for data preparation. Uses QuickSight asset bundles, Athena queries, and GitHub dataset integration with environment-specific configurations.

**AWS Services:** QuickSight • Glue • Athena • S3 • MWAA Serverless

**What happens during deployment:** Application code is deployed to S3, Glue jobs and Airflow workflows are created and executed, QuickSight dashboard/data source/dataset are created, and QuickSight ingestion is initiated to refresh the dashboard with latest data.

<details>
<summary><b>View Manifest</b></summary>

```yaml
applicationName: IntegrationTestETLWorkflow

content:
  storage:
    - name: dashboard-glue-quick
      connectionName: default.s3_shared
      include: [dashboard-glue-quick]
  
  git:
    - repository: covid-19-dataset
      url: https://github.com/datasets/covid-19.git
  
  quicksight:
    - dashboardId: sample-dashboard
      assetBundle: quicksight/sample-dashboard.qs
      owners:
        - arn:aws:quicksight:${DEV_DOMAIN_REGION:us-east-2}:*:user/default/Admin/*
  
  workflows:
    - workflowName: covid_dashboard_glue_quick_pipeline
      connectionName: default.workflow_serverless

stages:
  test:
    domain:
      region: us-east-2
    project:
      name: test-marketing
      owners:
        - Eng1
        - arn:aws:iam::${AWS_ACCOUNT_ID}:role/GitHubActionsRole-SMUS-CLI-Tests
    environment_variables:
      S3_PREFIX: test
      GRANT_TO: Admin,service-role/aws-quicksight-service-role-v0
    bootstrap:
      actions:
        - type: workflow.logs
          workflowName: covid_dashboard_glue_quick_pipeline
          live: true
          lines: 10000
        - type: quicksight.refresh_dataset
          refreshScope: IMPORTED
          ingestionType: FULL_REFRESH
          wait: false
    deployment_configuration:
      quicksight:
        overrideParameters:
          ResourceIdOverrideConfiguration:
            PrefixForAllResources: deployed-{stage.name}-covid-
```

</details>

**[View Full Example →](docs/examples-guide.md#-analytics---quicksight-dashboard)**

---

### 📓 Data Engineering - Notebooks
Deploy Jupyter notebooks with parallel execution orchestration for data analysis and ETL workflows. Demonstrates notebook deployment with MLflow integration for experiment tracking.

**AWS Services:** SageMaker Notebooks • MLflow • S3 • MWAA Serverless

**What happens during deployment:** Notebooks and workflow definitions are uploaded to S3, Airflow DAG is created for parallel notebook execution, MLflow connection is provisioned for experiment tracking, and notebooks are ready to run on-demand or scheduled.

<details>
<summary><b>View Manifest</b></summary>

```yaml
applicationName: IntegrationTestNotebooks

content:
  storage:
    - name: notebooks
      connectionName: default.s3_shared
      include:
        - notebooks/
        - workflows/
      exclude:
        - .ipynb_checkpoints/
        - __pycache__/
  
  workflows:
    - workflowName: parallel_notebooks_execution
      connectionName: default.workflow_serverless

stages:
  test:
    domain:
      region: us-east-1
    project:
      name: test-marketing
      owners:
        - Eng1
        - arn:aws:iam::${AWS_ACCOUNT_ID}:role/GitHubActionsRole-SMUS-CLI-Tests
    environment_variables:
      S3_PREFIX: test
    deployment_configuration:
      storage:
        - name: notebooks
          connectionName: default.s3_shared
          targetDirectory: notebooks/bundle/notebooks
    bootstrap:
      actions:
        - type: datazone.create_connection
          name: mlflow-server
          connection_type: MLFLOW
          properties:
            trackingServerArn: arn:aws:sagemaker:${STS_REGION}:${STS_ACCOUNT_ID}:mlflow-tracking-server/smus-integration-mlflow-use2
            trackingServerName: smus-integration-mlflow-use2
```

</details>

**[View Full Example →](docs/examples-guide.md#-data-engineering---notebooks)**

---

### 🤖 Machine Learning - Training
Train ML models with SageMaker using the [SageMaker SDK](https://sagemaker.readthedocs.io/) and [SageMaker Distribution](https://github.com/aws/sagemaker-distribution/tree/main/src) images. Track experiments with MLflow and automate training pipelines with environment-specific configurations.

**AWS Services:** SageMaker Training • MLflow • S3 • MWAA Serverless

**What happens during deployment:** Training code and workflow definitions are uploaded to S3 with compression, Airflow DAG is created for training orchestration, MLflow connection is provisioned for experiment tracking, and SageMaker training jobs are created and executed using SageMaker Distribution images.

<details>
<summary><b>View Manifest</b></summary>

```yaml
applicationName: IntegrationTestMLTraining

content:
  storage:
    - name: training-code
      connectionName: default.s3_shared
      include: [ml/training/code]
    
    - name: training-workflows
      connectionName: default.s3_shared
      include: [ml/training/workflows]
  
  workflows:
    - workflowName: ml_training_workflow
      connectionName: default.workflow_serverless

stages:
  test:
    domain:
      region: us-east-1
    project:
      name: test-ml-training
      create: true
      owners:
        - Eng1
        - arn:aws:iam::${AWS_ACCOUNT_ID}:role/GitHubActionsRole-SMUS-CLI-Tests
      role:
        arn: arn:aws:iam::${AWS_ACCOUNT_ID}:role/SMUSCICDTestRole
    environment_variables:
      S3_PREFIX: test
    deployment_configuration:
      storage:
        - name: training-code
          connectionName: default.s3_shared
          targetDirectory: ml/bundle/training-code
          compression: gz
        - name: training-workflows
          connectionName: default.s3_shared
          targetDirectory: ml/bundle/training-workflows
    bootstrap:
      actions:
        - type: datazone.create_connection
          name: mlflow-server
          connection_type: MLFLOW
          properties:
            trackingServerArn: arn:aws:sagemaker:${STS_REGION}:${STS_ACCOUNT_ID}:mlflow-tracking-server/smus-integration-mlflow-use2
```

</details>

**[View Full Example →](docs/examples-guide.md#-machine-learning---training)**

---

### 🤖 Machine Learning - Deployment
Deploy trained ML models as SageMaker real-time inference endpoints. Uses SageMaker SDK for endpoint configuration and [SageMaker Distribution](https://github.com/aws/sagemaker-distribution/tree/main/src) images for serving.

**AWS Services:** SageMaker Endpoints • S3 • MWAA Serverless

**What happens during deployment:** Model artifacts, deployment code, and workflow definitions are uploaded to S3, Airflow DAG is created for endpoint deployment orchestration, SageMaker endpoint configuration and model are created, and the inference endpoint is deployed and ready to serve predictions.

<details>
<summary><b>View Manifest</b></summary>

```yaml
applicationName: IntegrationTestMLDeployment

content:
  storage:
    - name: deployment-code
      connectionName: default.s3_shared
      include: [ml/deployment/code]
    
    - name: deployment-workflows
      connectionName: default.s3_shared
      include: [ml/deployment/workflows]
    
    - name: model-artifacts
      connectionName: default.s3_shared
      include: [ml/output/model-artifacts/latest]
  
  workflows:
    - workflowName: ml_deployment_workflow
      connectionName: default.workflow_serverless

stages:
  test:
    domain:
      region: us-east-1
    project:
      name: test-ml-deployment
      create: true
      owners:
        - Eng1
        - arn:aws:iam::${AWS_ACCOUNT_ID}:role/GitHubActionsRole-SMUS-CLI-Tests
      role:
        arn: arn:aws:iam::${AWS_ACCOUNT_ID}:role/SMUSCICDTestRole
    environment_variables:
      S3_PREFIX: test
    deployment_configuration:
      storage:
        - name: deployment-code
          connectionName: default.s3_shared
          targetDirectory: ml/bundle/deployment-code
        - name: deployment-workflows
          connectionName: default.s3_shared
          targetDirectory: ml/bundle/deployment-workflows
        - name: model-artifacts
          connectionName: default.s3_shared
          targetDirectory: ml/bundle/model-artifacts
```

</details>

**[View Full Example →](docs/examples-guide.md#-machine-learning---deployment)**

---

### 🧠 Generative AI
Deploy GenAI applications with Bedrock agents and knowledge bases. Demonstrates RAG (Retrieval Augmented Generation) workflows with automated agent deployment and testing.

**AWS Services:** Amazon Bedrock • S3 • MWAA Serverless

**What happens during deployment:** Agent configuration and workflow definitions are uploaded to S3, Airflow DAG is created for agent deployment orchestration, Bedrock agents and knowledge bases are configured, and the GenAI application is ready for inference and testing.

<details>
<summary><b>View Manifest</b></summary>

```yaml
applicationName: IntegrationTestGenAIWorkflow

content:
  storage:
    - name: agent-code
      connectionName: default.s3_shared
      include: [genai/job-code]
    
    - name: genai-workflows
      connectionName: default.s3_shared
      include: [genai/workflows]
  
  workflows:
    - workflowName: genai_dev_workflow
      connectionName: default.workflow_serverless

stages:
  test:
    domain:
      region: us-east-1
    project:
      name: test-marketing
      owners:
        - Eng1
        - arn:aws:iam::${AWS_ACCOUNT_ID}:role/GitHubActionsRole-SMUS-CLI-Tests
    environment_variables:
      S3_PREFIX: test
    deployment_configuration:
      storage:
        - name: agent-code
          connectionName: default.s3_shared
          targetDirectory: genai/bundle/agent-code
        - name: genai-workflows
          connectionName: default.s3_shared
          targetDirectory: genai/bundle/workflows
```

</details>

**[View Full Example →](docs/examples-guide.md#-generative-ai)**

---

**[See All Examples with Detailed Walkthroughs →](docs/examples-guide.md)**

---

---

<details>
<summary><h2>📋 Feature Checklist</h2></summary>

**Legend:** ✅ Supported | 🔄 Planned | 🔮 Future

### Core Infrastructure
| Feature | Status | Notes |
|---------|--------|-------|
| YAML configuration | ✅ | [Manifest Guide](docs/manifest.md) |
| Infrastructure as Code | ✅ | [Deploy Command](docs/cli-commands.md#deploy) |
| Multi-environment deployment | ✅ | [Stages](docs/manifest-schema.md#stages) |
| CLI tool | ✅ | [CLI Commands](docs/cli-commands.md) |
| Version control integration | ✅ | [GitHub Actions](docs/github-actions-integration.md) |

### Deployment & Bundling
| Feature | Status | Notes |
|---------|--------|-------|
| Artifact bundling | ✅ | [Bundle Command](docs/cli-commands.md#bundle) |
| Bundle-based deployment | ✅ | [Deploy Command](docs/cli-commands.md#deploy) |
| Direct deployment | ✅ | [Deploy Command](docs/cli-commands.md#deploy) |
| Deployment validation | ✅ | [Describe Command](docs/cli-commands.md#describe) |
| Incremental deployment | 🔄 | Upload only changed files |
| Rollback support | 🔮 | Automated rollback |
| Blue-green deployment | 🔮 | Zero-downtime deployments |

### Developer Experience
| Feature | Status | Notes |
|---------|--------|-------|
| Project templates | 🔄 | `smus-cli init` with templates |
| Manifest initialization | ✅ | [Create Command](docs/cli-commands.md#create) |
| Interactive setup | 🔄 | Guided configuration prompts |
| Local development | ✅ | [CLI Commands](docs/cli-commands.md) |
| VS Code extension | 🔮 | IntelliSense and validation |

### Configuration
| Feature | Status | Notes |
|---------|--------|-------|
| Variable substitution | ✅ | [Substitutions Guide](docs/substitutions-and-variables.md) |
| Environment-specific config | ✅ | [Stages](docs/manifest-schema.md#stages) |
| Secrets management | 🔮 | AWS Secrets Manager integration |
| Config validation | ✅ | [Manifest Schema](docs/manifest-schema.md) |
| Connection management | ✅ | [Connections Guide](docs/connections.md) |

### Resources & Workloads
| Feature | Status | Notes |
|---------|--------|-------|
| Airflow DAGs | ✅ | [Workflows](docs/manifest-schema.md#workflows) |
| Jupyter notebooks | ✅ | [SageMakerNotebookOperator](docs/airflow-aws-operators.md#amazon-sagemaker) |
| Glue ETL jobs | ✅ | [GlueJobOperator](docs/airflow-aws-operators.md#aws-glue) |
| Athena queries | ✅ | [AthenaOperator](docs/airflow-aws-operators.md#amazon-athena) |
| SageMaker training | ✅ | [SageMakerTrainingOperator](docs/airflow-aws-operators.md#amazon-sagemaker) |
| SageMaker endpoints | ✅ | [SageMakerEndpointOperator](docs/airflow-aws-operators.md#amazon-sagemaker) |
| QuickSight dashboards | ✅ | [QuickSight Deployment](docs/quicksight-deployment.md) |
| Bedrock agents | ✅ | [BedrockInvokeModelOperator](docs/airflow-aws-operators.md#amazon-bedrock) |
| Lambda functions | 🔄 | [LambdaInvokeFunctionOperator](docs/airflow-aws-operators.md#aws-lambda) |
| EMR jobs | ✅ | [EmrAddStepsOperator](docs/airflow-aws-operators.md#amazon-emr) |
| Redshift queries | ✅ | [RedshiftDataOperator](docs/airflow-aws-operators.md#amazon-redshift) |

### Bootstrap Actions
| Feature | Status | Notes |
|---------|--------|-------|
| Workflow execution | ✅ | [workflow.run](docs/bootstrap-actions.md#workflowrun---trigger-workflow-execution) |
| Log retrieval | ✅ | [workflow.logs](docs/bootstrap-actions.md#workflowlogs---fetch-workflow-logs) |
| QuickSight refresh | ✅ | [quicksight.refresh_dataset](docs/bootstrap-actions.md#quicksightrefresh_dataset---trigger-dataset-ingestion) |
| EventBridge events | ✅ | [eventbridge.put_events](docs/bootstrap-actions.md#customput_events---emit-custom-events) |
| DataZone connections | ✅ | [datazone.create_connection](docs/bootstrap-actions.md) |
| Sequential execution | ✅ | [Execution Flow](docs/bootstrap-actions.md#execution-flow) |

### CI/CD Integration
| Feature | Status | Notes |
|---------|--------|-------|
| GitHub Actions | ✅ | [GitHub Actions Guide](docs/github-actions-integration.md) |
| GitLab CI | ✅ | [CLI Commands](docs/cli-commands.md) |
| Azure DevOps | ✅ | [CLI Commands](docs/cli-commands.md) |
| Jenkins | ✅ | [CLI Commands](docs/cli-commands.md) |
| Service principals | ✅ | [GitHub Actions Guide](docs/github-actions-integration.md) |
| OIDC federation | ✅ | [GitHub Actions Guide](docs/github-actions-integration.md) |

### Testing & Validation
| Feature | Status | Notes |
|---------|--------|-------|
| Unit testing | ✅ | [Test Command](docs/cli-commands.md#test) |
| Integration testing | ✅ | [Test Command](docs/cli-commands.md#test) |
| Automated tests | ✅ | [Test Command](docs/cli-commands.md#test) |
| Quality gates | ✅ | [Test Command](docs/cli-commands.md#test) |
| Workflow monitoring | ✅ | [Monitor Command](docs/cli-commands.md#monitor) |

### Monitoring & Observability
| Feature | Status | Notes |
|---------|--------|-------|
| Deployment monitoring | ✅ | [Deploy Command](docs/cli-commands.md#deploy) |
| Workflow monitoring | ✅ | [Monitor Command](docs/cli-commands.md#monitor) |
| Custom alerts | ✅ | [Deployment Metrics](docs/pipeline-deployment-metrics.md) |
| Metrics collection | ✅ | [Deployment Metrics](docs/pipeline-deployment-metrics.md) |
| Deployment history | ✅ | [Bundle Command](docs/cli-commands.md#bundle) |

### AWS Service Integration
| Feature | Status | Notes |
|---------|--------|-------|
| Amazon MWAA | ✅ | [Workflows](docs/manifest-schema.md#workflows) |
| MWAA Serverless | ✅ | [Workflows](docs/manifest-schema.md#workflows) |
| AWS Glue | ✅ | [Airflow Operators](docs/airflow-aws-operators.md#aws-glue) |
| Amazon Athena | ✅ | [Airflow Operators](docs/airflow-aws-operators.md#amazon-athena) |
| SageMaker | ✅ | [Airflow Operators](docs/airflow-aws-operators.md#amazon-sagemaker) |
| Amazon Bedrock | ✅ | [Airflow Operators](docs/airflow-aws-operators.md#amazon-bedrock) |
| Amazon QuickSight | ✅ | [QuickSight Deployment](docs/quicksight-deployment.md) |
| DataZone | ✅ | [Manifest Schema](docs/manifest-schema.md) |
| EventBridge | ✅ | [Deployment Metrics](docs/pipeline-deployment-metrics.md) |
| Lake Formation | ✅ | [Connections Guide](docs/connections.md) |
| Amazon S3 | ✅ | [Storage](docs/manifest-schema.md#storage) |
| AWS Lambda | 🔄 | [Airflow Operators](docs/airflow-aws-operators.md#aws-lambda) |
| Amazon EMR | ✅ | [Airflow Operators](docs/airflow-aws-operators.md#amazon-emr) |
| Amazon Redshift | ✅ | [Airflow Operators](docs/airflow-aws-operators.md#amazon-redshift) |

### Advanced Features
| Feature | Status | Notes |
|---------|--------|-------|
| Multi-region deployment | ✅ | [Stages](docs/manifest-schema.md#stages) |
| Cross-project deployment | ✅ | [Stages](docs/manifest-schema.md#stages) |
| Dependency management | ✅ | [Airflow Operators](docs/airflow-aws-operators.md) |
| Catalog subscriptions | ✅ | [Manifest Schema](docs/manifest-schema.md) |
| Multi-service orchestration | ✅ | [Airflow Operators](docs/airflow-aws-operators.md) |
| Drift detection | 🔮 | Detect configuration drift |
| State management | 🔄 | Comprehensive state tracking |

</details>

---


## 文档

### 入门指南
- **[快速入门指南](docs/getting-started/quickstart.md)** - 部署你的第一个应用（10分钟）
- **[管理员指南](docs/getting-started/admin-quickstart.md)** - 设置基础设施（15分钟）

### 指南
- **[应用 manifest](docs/manifest.md)** - 完整的YAML配置参考
- **[CLI 命令](docs/cli-commands.md)** - 所有可用的命令和选项
- **[Bootstrap Actions](docs/bootstrap-actions.md)** - 自动化部署操作和事件驱动 workflow
- **[替换和变量](docs/substitutions-and-variables.md)** - 动态配置
- **[连接指南](docs/connections.md)** - 配置 AWS 服务集成
- **[GitHub Actions 集成](docs/github-actions-integration.md)** - CI/CD 自动化设置
- **[部署指标](docs/pipeline-deployment-metrics.md)** - 使用 EventBridge 监控

### 参考
- **[Manifest 模式](docs/manifest-schema.md)** - YAML 模式验证和结构
- **[Airflow AWS Operators](docs/airflow-aws-operators.md)** - 自定义操作符参考

### 示例
- **[示例指南](docs/examples-guide.md)** - 示例应用程序演练
- **[数据笔记本](docs/examples-guide.md#-data-engineering---notebooks)** - 带有 Airflow 的 Jupyter 笔记本
- **[机器学习训练](docs/examples-guide.md#-machine-learning---training)** - 使用 MLflow 的 SageMaker 训练
- **[机器学习部署](docs/examples-guide.md#-machine-learning---deployment)** - SageMaker endpoint 部署
- **[QuickSight 仪表板](docs/examples-guide.md#-analytics---quicksight-dashboard)** - 带有 Glue 的 BI 仪表板
- **[生成式 AI 应用](docs/examples-guide.md#-generative-ai)** - Bedrock agents 和知识库

### 开发
- **[开发指南](docs/development.md)** - 贡献和测试
- **[测试概述](tests/README.md)** - 测试基础设施

### 支持
- **问题**: [GitHub Issues](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/issues)
- **文档**: [docs/](docs/)
- **示例**: [examples/](examples/)

---

## 安全提示

⚠️ **请勿**从PyPI安装 - 始终从AWS官方源代码安装。

```bash
# ✅ 正确 - 从AWS官方仓库安装
git clone https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker.git
cd Unified-Studio-for-Amazon-Sagemaker/experimental/SMUS-CICD-pipeline-cli
pip install -e .

# ❌ 错误 - 不要使用PyPI
pip install smus-cicd-cli  # 可能包含恶意代码
```

---

## 许可证

本项目采用 MIT-0 许可证。详情请参阅 [LICENSE](../../LICENSE)。