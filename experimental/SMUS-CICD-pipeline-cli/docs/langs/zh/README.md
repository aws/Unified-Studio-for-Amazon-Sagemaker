# SMUS CI/CD Pipeline CLI

**自动化部署 SageMaker Unified Studio 环境中的数据应用**

使数据科学家、数据工程师、ML工程师和 GenAI 应用开发人员能够自信地将 Airflow DAG、Jupyter notebooks 和 ML 工作流从开发环境部署到生产环境。与 DevOps 团队协作。

**适用于您的部署策略:** 无论您使用 git 分支(基于分支)、版本化制品(基于 bundle)、git 标签(基于标签)还是直接部署 - 这个 CLI 都支持您的工作流。定义一次应用,按您的方式部署。

---

## 为什么选择 SMUS CI/CD CLI?

✅ **AWS 抽象层** - CLI 封装了所有 AWS 分析、ML 和 SMUS 复杂性 - DevOps 团队无需直接调用 AWS API  
✅ **关注点分离** - 数据团队定义要部署什么(manifest.yaml),DevOps 团队定义如何以及何时部署(CI/CD 工作流)  
✅ **通用 CI/CD 工作流** - 同样的工作流适用于 Glue、SageMaker、Bedrock、QuickSight 或任何 AWS 服务组合  
✅ **自信部署** - 在生产环境之前进行自动化测试和验证  
✅ **多环境管理** - 测试 → 生产环境,具有环境特定配置  
✅ **基础设施即代码** - 版本控制的应用清单和可重现的部署  
✅ **事件驱动工作流** - 通过 EventBridge 在部署时自动触发工作流  

---

## 快速入门

**从源代码安装:**
```bash
git clone https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker.git
cd Unified-Studio-for-Amazon-Sagemaker/experimental/SMUS-CICD-pipeline-cli
pip install -e .
```

**部署您的第一个应用:**
```bash
# 验证配置
smus-cli describe --manifest manifest.yaml --connect

# 创建部署包(可选)
smus-cli bundle --manifest manifest.yaml

# 部署到测试环境
smus-cli deploy --targets test --manifest manifest.yaml

# 运行验证测试
smus-cli test --manifest manifest.yaml --targets test
```

**查看实际效果:** [GitHub Actions 示例](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/actions/runs/17631303500)

---

## 这适合谁?

### 👨‍💻 数据团队(数据科学家、数据工程师、GenAI 应用开发人员)
**您专注于:** 您的应用 - 部署什么、部署到哪里以及如何运行  
**您定义:** 应用清单(`manifest.yaml`)包含您的代码、工作流和配置  
**您不需要了解:** CI/CD pipeline、GitHub Actions、部署自动化  

→ **[快速入门指南](docs/getting-started/quickstart.md)** - 10分钟内部署您的第一个应用  

**包含以下示例:**
- 数据工程(Glue、Notebooks、Athena)  
- ML 工作流(SageMaker、Notebooks)
- GenAI 应用(Bedrock、Notebooks)

**Bootstrap Actions - 自动化部署后任务:**

在清单中定义部署后自动运行的操作:
- 立即触发工作流(无需手动执行)
- 使用最新数据刷新 QuickSight 仪表板
- 为实验跟踪配置 MLflow 连接
- 获取验证日志
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
**您专注于:** CI/CD 最佳实践、安全、合规和部署自动化  
**您定义:** 执行测试、审批和晋升策略的工作流模板  
**您不需要了解:** 应用特定细节、使用的 AWS 服务、DataZone API、SMUS 项目结构或业务逻辑  

→ **[管理员指南](docs/getting-started/admin-quickstart.md)** - 15分钟内配置基础设施和pipeline  
→ **[GitHub 工作流模板](git-templates/)** - 用于自动部署的通用、可重用工作流模板

**CLI 是您的抽象层:** 您只需调用 `smus-cli deploy` - CLI 处理所有 AWS 服务交互(DataZone、Glue、Athena、SageMaker、MWAA、S3、IAM 等)并执行 bootstrap 操作(工作流运行、日志流、QuickSight 刷新、EventBridge 事件)。您的工作流保持简单和通用。

[继续翻译...]