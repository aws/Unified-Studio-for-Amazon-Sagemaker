[![en](https://img.shields.io/badge/lang-en-gray.svg)](../../../README.md)
[![pt](https://img.shields.io/badge/lang-pt-gray.svg)](../pt/README.md)
[![fr](https://img.shields.io/badge/lang-fr-gray.svg)](../fr/README.md)
[![it](https://img.shields.io/badge/lang-it-gray.svg)](../it/README.md)
[![ja](https://img.shields.io/badge/lang-ja-brightgreen.svg?style=for-the-badge)](../ja/README.md)
[![zh](https://img.shields.io/badge/lang-zh-gray.svg)](../zh/README.md)
[![he](https://img.shields.io/badge/lang-he-gray.svg)](../he/README.md)

# SMUS CI/CD Pipeline CLI

← [Back to Main README](../../../README.md)


**SageMaker Unified Studio環境全体でデータアプリケーションのデプロイを自動化**

開発から本番環境まで、Airflow DAG、Jupyterノートブック、MLワークフローを確実にデプロイできます。DevOpsチームと協働するデータサイエンティスト、データエンジニア、MLエンジニア、生成AIアプリ開発者向けに構築されています。

**あなたのデプロイメント戦略に対応：** gitブランチ（ブランチベース）、バージョン管理されたアーティファクト（bundleベース）、gitタグ（タグベース）、直接デプロイのいずれを使用する場合でも、このCLIはあなたのworkflowをサポートします。アプリケーションを一度定義すれば、お好みの方法でデプロイできます。

---

## なぜSMUS CI/CD CLIなのか？

✅ **AWS抽象化レイヤー** - CLIがすべてのAWSアナリティクス、ML、SMUSの複雑さをカプセル化 - DevOpsチームが直接AWSのAPIを呼び出す必要なし  
✅ **関心の分離** - データチームは何をデプロイするか（manifest.yaml）を定義し、DevOpsチームはどのように、いつ（CI/CDワークフロー）を定義  
✅ **汎用CI/CDワークフロー** - 同じワークフローでGlue、SageMaker、Bedrock、QuickSight、または任意のAWSサービスの組み合わせに対応  
✅ **確実なデプロイ** - 本番環境前の自動テストとバリデーション  
✅ **マルチ環境管理** - 環境固有の設定によるテスト→本番環境への展開  
✅ **Infrastructure as Code** - バージョン管理されたアプリケーションmanifestと再現可能なデプロイメント  
✅ **イベント駆動ワークフロー** - EventBridgeを介してデプロイ時に自動的にワークフローをトリガー  

---

## クイックスタート

**ソースからインストール:**
```bash
git clone https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker.git
cd Unified-Studio-for-Amazon-Sagemaker/experimental/SMUS-CICD-pipeline-cli
pip install -e .
```

**最初のアプリケーションをデプロイ:**
```bash
# 設定の検証
smus-cli describe --manifest manifest.yaml --connect

# デプロイメントbundleの作成（オプション）
smus-cli bundle --manifest manifest.yaml

# テスト環境へのデプロイ
smus-cli deploy --targets test --manifest manifest.yaml

# 検証テストの実行
smus-cli test --manifest manifest.yaml --targets test
```

**動作確認:** [Live GitHub Actions Example](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/actions/runs/17631303500)

---

## 対象者

### 👨‍💻 データチーム (データサイエンティスト、データエンジニア、生成AIアプリ開発者)
**フォーカス:** アプリケーション - 何をデプロイし、どこにデプロイし、どのように実行するか  
**定義するもの:** コード、workflow、設定を含むアプリケーションmanifest (`manifest.yaml`)  
**知る必要がないもの:** CI/CDパイプライン、GitHub Actions、デプロイメント自動化  

→ **[クイックスタートガイド](docs/getting-started/quickstart.md)** - 10分で最初のアプリケーションをデプロイ  

**含まれる例:**
- データエンジニアリング (Glue, Notebooks, Athena)
- MLワークフロー (SageMaker, Notebooks)
- 生成AIアプリケーション (Bedrock, Notebooks)

**Bootstrap Actions - デプロイ後のタスクを自動化:**

デプロイ後に自動的に実行されるアクションをmanifestで定義:
- workflowを即時トリガー（手動実行不要）
- QuickSightダッシュボードを最新データで更新
- 実験追跡用のMLflow接続をプロビジョニング
- 検証用のログを取得
- 下流プロセスをトリガーするイベントを発行

例:
```yaml
bootstrap:
  actions:
    - type: workflow.run
      workflowName: etl_pipeline
      wait: true
    - type: quicksight.refresh_dataset
      refreshScope: IMPORTED
```

### 🔧 DevOpsチーム
**フォーカス:** CI/CDのベストプラクティス、セキュリティ、コンプライアンス、デプロイメント自動化  
**定義するもの:** テスト、承認、プロモーションポリシーを強制するworkflowテンプレート  
**知る必要がないもの:** アプリケーション固有の詳細、AWS サービス、DataZone API、SMUSプロジェクト構造、ビジネスロジック  

→ **[管理者ガイド](docs/getting-started/admin-quickstart.md)** - 15分でインフラストラクチャとpipelineを設定  
→ **[GitHub Workflowテンプレート](git-templates/)** - 自動デプロイ用の汎用的で再利用可能なworkflowテンプレート

**CLIが抽象化レイヤー:** `smus-cli deploy`を呼び出すだけ - CLIがすべてのAWSサービスとの連携(DataZone, Glue, Athena, SageMaker, MWAA, S3, IAM等)とbootstrapアクション(workflow実行、ログストリーミング、QuickSight更新、EventBridgeイベント)を処理します。workflowはシンプルで汎用的なままです。

---

## 主な機能

### 🚀 自動デプロイメント
- **アプリケーションマニフェスト** - YAMLでアプリケーションのコンテンツ、workflow、デプロイメント先を定義
- **柔軟なデプロイメント** - bundleベース（アーティファクト）または直接（gitベース）のデプロイメントモード
- **マルチターゲットデプロイメント** - 単一のコマンドでテストと本番環境にデプロイ
- **環境変数** - `${VAR}`置換を使用した動的な設定
- **バージョン管理** - S3またはgitでデプロイメント履歴を追跡

### 🔍 テストと検証
- **自動テスト** - 本番環境への昇格前に検証テストを実行
- **品質ゲート** - テスト失敗時にデプロイメントをブロック
- **workflowモニタリング** - 実行状態とログの追跡
- **ヘルスチェック** - デプロイメントの正確性を確認

### 🔄 CI/CDパイプラインの統合
- **GitHub Actions** - 自動デプロイメント用の事前構築されたCI/CD pipeline workflow
- **GitLab CI** - GitLab CI/CDパイプラインのネイティブサポート
- **環境変数** - あらゆるCI/CDプラットフォームに対応する柔軟な設定
- **Webhookサポート** - 外部イベントからデプロイメントをトリガー

### 🏗️ インフラストラクチャ管理
- **プロジェクト作成** - SageMaker Unified Studioプロジェクトの自動プロビジョニング
- **接続設定** - S3、Airflow、Athena、Lakehouseの接続を構成
- **リソースマッピング** - AWSリソースをプロジェクト接続にリンク
- **権限管理** - アクセスとコラボレーションの制御

### ⚡ ブートストラップアクション
- **自動workflow実行** - `workflow.run`でデプロイメント時にworkflowを自動的にトリガー（`trailLogs: true`でログをストリーミングし完了を待機）
- **ログ取得** - `workflow.logs`で検証とデバッグ用のworkflowログを取得
- **QuickSightデータセット更新** - `quicksight.refresh_dataset`でETLデプロイメント後にダッシュボードを自動更新
- **EventBridge統合** - `eventbridge.put_events`でダウンストリームの自動化とCI/CDオーケストレーション用のカスタムイベントを発行
- **DataZone接続** - デプロイメント時にMLflowなどのサービス接続をプロビジョニング
- **順次実行** - 信頼性の高い初期化と検証のため`smus-cli deploy`時にアクションを順番に実行

### 📊 カタログ統合
- **アセット検出** - 必要なカタログアセット（Glue、Lake Formation、DataZone）を自動的に検出
- **サブスクリプション管理** - テーブルとデータセットへのアクセスをリクエスト
- **承認workflow** - プロジェクト間のデータアクセスを処理
- **アセット追跡** - カタログの依存関係を監視

---

## デプロイ可能なもの

**📊 分析 & BI**
- Glue ETLジョブとクローラー
- Athenaクエリ
- QuickSightダッシュボード
- EMRジョブ（今後対応予定）
- Redshiftクエリ（今後対応予定）

**🤖 機械学習**
- SageMakerトレーニングジョブ
- MLモデルとエンドポイント
- MLflow実験
- Feature Store（今後対応予定）
- バッチ変換（今後対応予定）

**🧠 生成AI**
- Bedrockエージェント
- ナレッジベース
- 基盤モデル設定（今後対応予定）

**📓 コード & ワークフロー**
- Jupyterノートブック
- Pythonスクリプト
- Airflow DAG（MWAAとAmazon MWAA Serverless）
- Lambda関数（今後対応予定）

**💾 データ & ストレージ**
- S3データファイル
- Gitリポジトリ
- データカタログ（今後対応予定）

---

## サポートされているAWSサービス

以下のAWSサービスをAirflow YAMLシンタックスを使用してworkflowをデプロイできます：

### 🎯 分析とデータ
**Amazon Athena** • **AWS Glue** • **Amazon EMR** • **Amazon Redshift** • **Amazon QuickSight** • **Lake Formation**

### 🤖 機械学習
**SageMaker Training** • **SageMaker Pipelines** • **Feature Store** • **Model Registry** • **Batch Transform**

### 🧠 生成AI
**Amazon Bedrock** • **Bedrock Agents** • **Bedrock Knowledge Bases** • **Guardrails**

### 📊 その他のサービス
S3 • Lambda • Step Functions • DynamoDB • RDS • SNS/SQS • Batch

**完全なリストはこちら：** [Airflow AWS Operators Reference](docs/airflow-aws-operators.md)

---

## コアコンセプト

### 関心の分離：重要な設計原則

**問題点:** 従来のデプロイメントアプローチでは、DevOpsチームがAWSアナリティクスサービス(Glue、Athena、DataZone、SageMaker、MWAAなど)とSMUSプロジェクト構造を学ぶ必要があるか、またはデータチームがCI/CDの専門家になる必要がありました。

**解決策:** SMUS CLIは、すべてのAWSとSMUSの複雑さをカプセル化する抽象化レイヤーです：

```
Data Teams                    SMUS CLI                         DevOps Teams
    ↓                            ↓                                  ↓
manifest.yaml          smus-cli deploy                    GitHub Actions
(WHAT & WHERE)         (AWS ABSTRACTION)                  (HOW & WHEN)
```

**データチームの焦点：**
- アプリケーションコードとworkflow
- 使用するAWSサービス(Glue、Athena、SageMakerなど)
- 環境設定
- ビジネスロジック

**SMUS CLIが処理するAWSの複雑さ：**
- DataZoneドメインとプロジェクト管理
- AWS Glue、Athena、SageMaker、MWAA API
- S3ストレージとアーティファクト管理
- IAMロールと権限
- 接続設定
- カタログアセットのサブスクリプション
- AirflowへのWorkflowデプロイ
- インフラストラクチャのプロビジョニング
- テストとバリデーション

**DevOpsチームの焦点：**
- CI/CDのベストプラクティス(テスト、承認、通知)
- セキュリティとコンプライアンスゲート
- デプロイメントのオーケストレーション
- モニタリングとアラート

**結果：**
- データチームはCI/CD設定に触れる必要がない
- **DevOpsチームはAWS APIを直接呼び出さない** - `smus-cli deploy`を呼び出すだけ
- **CI/CD workflowは汎用的** - 同じworkflowがGlueアプリ、SageMakerアプリ、Bedrockアプリで動作
- 両チームが専門知識を活かして独立して作業可能

---

### アプリケーションmanifest
データアプリケーションを定義する宣言的YAMLファイル(`manifest.yaml`)：
- **アプリケーション詳細** - 名前、バージョン、説明
- **コンテンツ** - gitリポジトリからのコード、ストレージからのデータ/モデル、QuickSightダッシュボード
- **Workflow** - オーケストレーションと自動化のためのAirflow DAG
- **ステージ** - デプロイ先(開発、テスト、本番環境)
- **設定** - 環境固有の設定、接続、ブートストラップアクション

**データチームが作成し所有。** デプロイする**内容**と**場所**を定義。CI/CDの知識は不要。

### アプリケーション
デプロイされるデータ/アナリティクスワークロード：
- Airflow DAGとPythonスクリプト
- Jupyterノートブックとデータファイル
- MLモデルとトレーニングコード
- ETLパイプラインと変換
- GenAIエージェントとMCPサーバー
- 基盤モデル設定

### ステージ
SageMaker Unified Studioプロジェクトにマッピングされたデプロイメント環境(開発、テスト、本番)：
- ドメインとリージョン設定
- プロジェクト名と設定
- リソース接続(S3、Airflow、Athena、Glue)
- 環境固有のパラメータ
- gitベースのデプロイメント用のオプションのブランチマッピング

### Workflow
アプリケーションを実行するオーケストレーションロジック。Workflowには2つの目的があります：

**1. デプロイメント時：** デプロイメント中に必要なAWSリソースを作成
- インフラストラクチャのプロビジョニング(S3バケット、データベース、IAMロール)
- 接続と権限の設定
- モニタリングとロギングのセットアップ

**2. ランタイム：** 継続的なデータとMLパイプラインの実行
- スケジュールされた実行(日次、時間単位など)
- イベント駆動トリガー(S3アップロード、API呼び出し)
- データ処理と変換
- モデルトレーニングと推論

WorkflowはYAML形式のAirflow DAG(Directed Acyclic Graph)として定義されます。[MWAA (Managed Workflows for Apache Airflow)](https://aws.amazon.com/managed-workflows-for-apache-airflow/)と[Amazon MWAA Serverless](https://aws.amazon.com/blogs/big-data/introducing-amazon-mwaa-serverless/)([ユーザーガイド](https://docs.aws.amazon.com/mwaa/latest/mwaa-serverless-userguide/what-is-mwaa-serverless.html))をサポートしています。

### CI/CD自動化
デプロイメントを自動化するGitHub Actionsワークフロー(または他のCI/CDシステム)：
- **DevOpsチームが作成し所有**
- デプロイの**方法**と**タイミング**を定義
- テストと品質ゲートを実行
- ターゲット間のプロモーションを管理
- セキュリティとコンプライアンスポリシーを適用
- 例：`.github/workflows/deploy.yml`

**重要な洞察：** DevOpsチームは、どのアプリケーションでも動作する汎用的で再利用可能なworkflowを作成します。アプリがGlue、SageMaker、Bedrockのどれを使用しているかを知る必要はありません - CLIがすべてのAWSサービスとのやり取りを処理します。workflowは単に`smus-cli deploy`を呼び出し、CLIが残りを処理します。

### デプロイメントモード

**バンドルベース(アーティファクト)：** バージョン管理されたアーカイブを作成→アーカイブをステージにデプロイ
- 適している用途：監査証跡、ロールバック機能、コンプライアンス
- コマンド：`smus-cli bundle`その後`smus-cli deploy --manifest app.tar.gz`

**直接(Gitベース)：** 中間アーティファクトなしでソースから直接デプロイ
- 適している用途：シンプルなworkflow、迅速な反復、gitを真実の源として使用
- コマンド：`smus-cli deploy --manifest manifest.yaml --stage test`

両モードは、ストレージとgitコンテンツソースのあらゆる組み合わせで動作します。

---

### すべてがどのように連携するか

```
1. データチーム                 2. DevOpsチーム                3. SMUS CLI (抽象化レイヤー)
   ↓                               ↓                              ↓
manifest.yamlを作成           汎用的なworkflowを作成        Workflowが呼び出し：
- Glueジョブ                   - マージ時のテスト             smus-cli deploy --manifest manifest.yaml
- SageMakerトレーニング        - 本番環境の承認                ↓
- Athenaクエリ                 - セキュリティスキャン        CLIがすべてのAWSの複雑さを処理：
- S3の場所                     - 通知ルール                  - DataZone API
                                                              - Glue/Athena/SageMaker API
                               どのアプリでも動作！          - MWAAデプロイメント
                               AWS知識不要！                 - S3管理
                                                              - IAM設定
                                                              - インフラストラクチャのプロビジョニング
                                                                ↓
                                                              成功！
```

**優れている点：**
- データチームはGitHub Actionsを学ぶ必要がない
- **DevOpsチームはAWS APIを呼び出さない** - CLIがすべてのAWSアナリティクス、ML、SMUSの複雑さをカプセル化
- CI/CD workflowはシンプル：`smus-cli deploy`を呼び出すだけ
- 同じworkflowが、使用するAWSサービスに関係なく、どのアプリケーションでも動作

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


## ドキュメント

### はじめに
- **[クイックスタートガイド](docs/getting-started/quickstart.md)** - 最初のアプリケーションをデプロイ（10分）
- **[管理者ガイド](docs/getting-started/admin-quickstart.md)** - インフラストラクチャのセットアップ（15分）

### ガイド
- **[Application Manifest](docs/manifest.md)** - 完全なYAML設定リファレンス
- **[CLI Commands](docs/cli-commands.md)** - 利用可能なすべてのコマンドとオプション
- **[Bootstrap Actions](docs/bootstrap-actions.md)** - 自動デプロイアクションとイベント駆動workflow
- **[Substitutions & Variables](docs/substitutions-and-variables.md)** - 動的設定
- **[接続ガイド](docs/connections.md)** - AWSサービス統合の設定
- **[GitHub Actions Integration](docs/github-actions-integration.md)** - CI/CD自動化のセットアップ
- **[デプロイメントメトリクス](docs/pipeline-deployment-metrics.md)** - EventBridgeによる監視

### リファレンス
- **[Manifest Schema](docs/manifest-schema.md)** - YAML スキーマ検証と構造
- **[Airflow AWS Operators](docs/airflow-aws-operators.md)** - カスタムオペレーターリファレンス

### 例
- **[サンプルガイド](docs/examples-guide.md)** - サンプルアプリケーションのチュートリアル
- **[データノートブック](docs/examples-guide.md#-data-engineering---notebooks)** - AirflowによるJupyterノートブック
- **[ML トレーニング](docs/examples-guide.md#-machine-learning---training)** - MLflowによるSageMakerトレーニング
- **[ML デプロイメント](docs/examples-guide.md#-machine-learning---deployment)** - SageMakerエンドポイントのデプロイ
- **[QuickSight Dashboard](docs/examples-guide.md#-analytics---quicksight-dashboard)** - GlueによるBIダッシュボード
- **[GenAIアプリケーション](docs/examples-guide.md#-generative-ai)** - Bedrockエージェントとナレッジベース

### 開発
- **[開発ガイド](docs/development.md)** - コントリビューションとテスト
- **[テスト概要](tests/README.md)** - テストインフラストラクチャ

### サポート
- **Issues**: [GitHub Issues](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/issues)
- **ドキュメント**: [docs/](docs/)
- **サンプル**: [examples/](examples/)

---

## セキュリティに関する注意

⚠️ **PyPIからインストールしないでください** - 必ずAWSの公式ソースコードからインストールしてください。

```bash
# ✅ 正しい方法 - AWSの公式リポジトリからインストール
git clone https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker.git
cd Unified-Studio-for-Amazon-Sagemaker/experimental/SMUS-CICD-pipeline-cli
pip install -e .

# ❌ 間違った方法 - PyPIを使用しないでください
pip install smus-cicd-cli  # 悪意のあるコードが含まれている可能性があります
```

---

## ライセンス

このプロジェクトはMIT-0ライセンスの下でライセンスされています。詳細は[LICENSE](../../LICENSE)をご覧ください。