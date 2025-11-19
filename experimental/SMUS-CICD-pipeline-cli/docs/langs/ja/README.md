# SMUS CI/CD Pipeline CLI

**SageMaker Unified Studioの環境間でデータアプリケーションのデプロイを自動化**

DevOpsチームと協力してAirflow DAG、Jupyterノートブック、MLワークフローを開発から本番環境へ確実にデプロイ。データサイエンティスト、データエンジニア、MLエンジニア、GenAIアプリ開発者向けに設計。

**あなたのデプロイ戦略に対応:** gitブランチ(ブランチベース)、バージョン管理されたアーティファクト(バンドルベース)、gitタグ(タグベース)、直接デプロイのいずれを使用しても、このCLIはあなたのワークフローをサポートします。アプリケーションを一度定義すれば、好みの方法でデプロイできます。

---

## なぜSMUS CI/CD CLIなのか?

✅ **AWS抽象化レイヤー** - CLIがAWSのアナリティクス、ML、SMUS関連の複雑さをカプセル化 - DevOpsチームが直接AWSのAPIを呼び出す必要なし  
✅ **関心の分離** - データチームは何をデプロイするか(manifest.yaml)を定義、DevOpsチームはどのように・いつデプロイするか(CI/CDワークフロー)を定義  
✅ **汎用CI/CDワークフロー** - Glue、SageMaker、Bedrock、QuickSight、または任意のAWSサービスの組み合わせに同じワークフローが使用可能  
✅ **確実なデプロイ** - 本番環境前の自動テストとバリデーション  
✅ **マルチ環境管理** - 環境固有の設定によるテスト→本番環境への展開  
✅ **Infrastructure as Code** - バージョン管理されたアプリケーションマニフェストと再現可能なデプロイ  
✅ **イベント駆動ワークフロー** - デプロイ時にEventBridgeを介して自動的にワークフローをトリガー  

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

# デプロイバンドルの作成(オプション)
smus-cli bundle --manifest manifest.yaml

# テスト環境へのデプロイ
smus-cli deploy --targets test --manifest manifest.yaml

# 検証テストの実行
smus-cli test --manifest manifest.yaml --targets test
```

**動作の確認:** [GitHub Actionsの実行例](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/actions/runs/17631303500)

---

## 対象ユーザー

### 👨‍💻 データチーム(データサイエンティスト、データエンジニア、GenAIアプリ開発者)
**フォーカス:** アプリケーション - 何をデプロイし、どこにデプロイし、どのように実行するか  
**定義するもの:** アプリケーションマニフェスト(`manifest.yaml`) - コード、ワークフロー、設定を含む  
**知る必要がないもの:** CI/CDパイプライン、GitHub Actions、デプロイの自動化  

→ **[クイックスタートガイド](docs/getting-started/quickstart.md)** - 10分で最初のアプリケーションをデプロイ  

**含まれる例:**
- データエンジニアリング(Glue、ノートブック、Athena)
- MLワークフロー(SageMaker、ノートブック)
- GenAIアプリケーション(Bedrock、ノートブック)

**ブートストラップアクション - デプロイ後のタスクを自動化:**

マニフェストでデプロイ後に自動実行するアクションを定義:
- ワークフローを即座にトリガー(手動実行不要)
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
**フォーカス:** CI/CDのベストプラクティス、セキュリティ、コンプライアンス、デプロイの自動化  
**定義するもの:** テスト、承認、昇格ポリシーを強制するワークフローテンプレート  
**知る必要がないもの:** アプリケーション固有の詳細、使用するAWSサービス、DataZone API、SMUSプロジェクト構造、ビジネスロジック  

→ **[管理者ガイド](docs/getting-started/admin-quickstart.md)** - 15分でインフラストラクチャとパイプラインを設定  
→ **[GitHubワークフローテンプレート](git-templates/)** - 自動デプロイ用の汎用的で再利用可能なワークフローテンプレート

**CLIが抽象化レイヤーとして機能:** `smus-cli deploy`を呼び出すだけ - CLIがすべてのAWSサービスとのやり取り(DataZone、Glue、Athena、SageMaker、MWAA、S3、IAMなど)とブートストラップアクション(ワークフロー実行、ログストリーミング、QuickSightの更新、EventBridgeイベント)を処理します。ワークフローはシンプルで汎用的なままです。

[以下同様に続く - 文字数制限のため省略]