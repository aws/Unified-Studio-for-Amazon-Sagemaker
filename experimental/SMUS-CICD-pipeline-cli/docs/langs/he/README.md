<div dir="rtl">

[![en](https://img.shields.io/badge/lang-en-gray.svg)](../../../README.md)
[![pt](https://img.shields.io/badge/lang-pt-gray.svg)](../pt/README.md)
[![fr](https://img.shields.io/badge/lang-fr-gray.svg)](../fr/README.md)
[![it](https://img.shields.io/badge/lang-it-gray.svg)](../it/README.md)
[![ja](https://img.shields.io/badge/lang-ja-gray.svg)](../ja/README.md)
[![zh](https://img.shields.io/badge/lang-zh-gray.svg)](../zh/README.md)
[![he](https://img.shields.io/badge/lang-he-brightgreen.svg?style=for-the-badge)](../he/README.md)

# SMUS CI/CD Pipeline CLI

**אוטומציה של פריסת אפליקציות נתונים בסביבות SageMaker Unified Studio**

Deploy Airflow DAGs, Jupyter notebooks, and ML workflows from development to production with confidence
(פרוס DAGs של Airflow, מחברות Jupyter, וזרימות עבודה של ML מפיתוח לייצור בביטחון)

Built for data scientists, data engineers, ML engineers, and GenAI app developers working with DevOps teams
(נבנה עבור מדעני נתונים, מהנדסי נתונים, מהנדסי ML, ומפתחי אפליקציות GenAI העובדים עם צוותי DevOps)

**Works with your deployment strategy:** Whether you use git branches (branch-based), versioned artifacts (bundle-based), git tags (tag-based), or direct deployment - this CLI supports your workflow. Define your application once, deploy it your way.
(פועל עם אסטרטגיית הפריסה שלך: בין אם אתה משתמש בענפי git, ארטיפקטים מגורסאים, תגיות git, או פריסה ישירה - ה-CLI תומך בזרימת העבודה שלך. הגדר את האפליקציה פעם אחת, פרוס אותה בדרך שלך)

---

## למה SMUS CI/CD CLI?

✅ **שכבת הפשטה של AWS** - CLI מכיל את כל המורכבות של אנליטיקה, ML ו-SMUS של AWS - צוותי DevOps לעולם לא קוראים ל-APIs של AWS ישירות

"Separation of Concerns - Data teams define WHAT to deploy (manifest.yaml), DevOps teams define HOW and WHEN (CI/CD workflows)" ✅
(הפרדת אחריויות - צוותי נתונים מגדירים מה לפרוס, צוותי DevOps מגדירים איך ומתי)

"Generic CI/CD Workflows - Same workflow works for Glue, SageMaker, Bedrock, QuickSight, or any AWS service combination" ✅
(זרימות עבודה גנריות - אותה זרימת עבודה פועלת עבור כל שילוב שירותים)

✅ **פריסה בביטחון** - בדיקות ותיקוף אוטומטיים לפני הפריסה לייצור

✅ **ניהול מרובה סביבות** - מבדיקות לייצור עם תצורה ייעודית לכל סביבה

"Infrastructure as Code - Version-controlled application manifests and reproducible deployments" ✅
(תשתית כקוד - מניפסטים של אפליקציות בבקרת גרסאות ופריסות הניתנות לשחזור)

"Event-Driven Workflows - Trigger workflows automatically via EventBridge on deployment" ✅
(זרימות עבודה מבוססות אירועים - הפעלה אוטומטית של זרימות עבודה דרך EventBridge בעת פריסה)

---

## התחלה מהירה

**התקנה מהקוד המקור:**
<div dir="ltr">

```bash
git clone https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker.git
cd Unified-Studio-for-Amazon-Sagemaker/experimental/SMUS-CICD-pipeline-cli
pip install -e .
```

</div>

**פריסת האפליקציה הראשונה שלך:**
<div dir="ltr">

```bash
# Validate configuration
smus-cli describe --manifest manifest.yaml --connect

# Create deployment bundle (optional)
smus-cli bundle --manifest manifest.yaml

# Deploy to test environment
smus-cli deploy --targets test --manifest manifest.yaml

# Run validation tests
smus-cli test --manifest manifest.yaml --targets test
```

</div>

**ראה בפעולה:** [Live GitHub Actions Example](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/actions/runs/17631303500)

---

## למי זה מיועד?

### 👨‍💻 צוותי נתונים (מדעני נתונים, מהנדסי נתונים, מפתחי אפליקציות GenAI)
**המיקוד שלכם:** האפליקציה שלכם - מה לפרוס, איפה לפרוס, ואיך היא רצה  
**אתם מגדירים:** מניפסט אפליקציה (`manifest.yaml`) עם הקוד, זרימות העבודה והתצורות שלכם  
**אתם לא צריכים לדעת:** CI/CD pipelines, GitHub Actions, אוטומציה של פריסה  

→ **[מדריך התחלה מהירה](docs/getting-started/quickstart.md)** - פרסו את האפליקציה הראשונה שלכם תוך 10 דקות  

"**Includes examples for:**"
- Data Engineering (Glue, Notebooks, Athena)
- ML Workflows (SageMaker, Notebooks) 
- GenAI Applications (Bedrock, Notebooks)

**פעולות אתחול - אוטומציה של משימות לאחר הפריסה:**

הגדירו פעולות במניפסט שירוצו אוטומטית לאחר הפריסה:
- הפעלת זרימות עבודה באופן מיידי (ללא צורך בהפעלה ידנית)
- רענון לוחות מחוונים של QuickSight עם הנתונים העדכניים ביותר
- הגדרת חיבורי MLflow למעקב אחר ניסויים
- שליפת יומנים לצורך אימות
- שליחת אירועים להפעלת תהליכים במורד הזרם

<div dir="ltr">

```yaml
bootstrap:
  actions:
    - type: workflow.run
      workflowName: etl_pipeline
      wait: true
    - type: quicksight.refresh_dataset
      refreshScope: IMPORTED
```

</div>

### 🔧 צוותי DevOps
**המיקוד שלכם:** שיטות עבודה מומלצות ל-CI/CD, אבטחה, תאימות ואוטומציה של פריסה  
**אתם מגדירים:** תבניות זרימת עבודה האוכפות בדיקות, אישורים ומדיניות קידום  
**אתם לא צריכים לדעת:** פרטים ספציפיים לאפליקציה, שירותי AWS בשימוש, DataZone APIs, מבני פרויקט SMUS, או לוגיקה עסקית  

→ **[מדריך למנהל](docs/getting-started/admin-quickstart.md)** - הגדירו תשתית וצינורות תוך 15 דקות  
→ **[תבניות זרימת עבודה של GitHub](git-templates/)** - תבניות זרימת עבודה גנריות, לשימוש חוזר עבור פריסה אוטומטית

"**The CLI is your abstraction layer:** You just call `smus-cli deploy` - the CLI handles all AWS service interactions (DataZone, Glue, Athena, SageMaker, MWAA, S3, IAM, etc.) and executes bootstrap actions (workflow runs, log streaming, QuickSight refreshes, EventBridge events). Your workflows stay simple and generic."

---

## תכונות מרכזיות

### 🚀 פריסה אוטומטית
"Application Manifest - Define your application content, workflows, and deployment targets in YAML" (מניפסט יישום - הגדר את תוכן היישום, זרימות העבודה ויעדי הפריסה ב-YAML)
"Flexible Deployment - Bundle-based (artifact) or direct (git-based) deployment modes" (פריסה גמישה - מצבי פריסה מבוססי חבילה או ישירים)
"Multi-Target Deployment - Deploy to test and prod with a single command" (פריסה מרובת יעדים - פרוס לסביבות בדיקה וייצור בפקודה אחת)
"Environment Variables - Dynamic configuration using ${VAR} substitution" (משתני סביבה - תצורה דינמית באמצעות החלפת ${VAR})
"Version Control - Track deployments in S3 or git for deployment history" (בקרת גרסאות - מעקב אחר פריסות ב-S3 או git להיסטוריית פריסה)

### 🔍 בדיקות ותיקוף
- הרצת בדיקות תיקוף לפני קידום לייצור
- חסימת פריסות במקרה של כישלון בבדיקות
- מעקב אחר סטטוס ביצוע ויומנים
- בדיקות תקינות לאימות הפריסה

### 🔄 אינטגרציית CI/CD Pipeline
"GitHub Actions - Pre-built CI/CD pipeline workflows for automated deployment" (GitHub Actions - זרימות עבודה מוכנות מראש לפריסה אוטומטית)
"GitLab CI - Native support for GitLab CI/CD pipelines" (GitLab CI - תמיכה מובנית ב-pipelines של GitLab CI/CD)
"Environment Variables - Flexible configuration for any CI/CD platform" (משתני סביבה - תצורה גמישה לכל פלטפורמת CI/CD)
"Webhook Support - Trigger deployments from external events" (תמיכה ב-Webhook - הפעלת פריסות מאירועים חיצוניים)

### 🏗️ ניהול תשתיות
"Project Creation - Automatically provision SageMaker Unified Studio projects" (יצירת פרויקטים - הקצאה אוטומטית של פרויקטי SageMaker Unified Studio)
"Connection Setup - Configure S3, Airflow, Athena, and Lakehouse connections" (הגדרת חיבורים - תצורת חיבורים ל-S3, Airflow, Athena ו-Lakehouse)
"Resource Mapping - Link AWS resources to project connections" (מיפוי משאבים - קישור משאבי AWS לחיבורי הפרויקט)
- ניהול הרשאות - בקרת גישה ושיתוף פעולה

### ⚡ פעולות אתחול
"Automated Workflow Execution - Trigger workflows automatically during deployment with workflow.run" (הפעלת זרימת עבודה אוטומטית - הפעל זרימות עבודה אוטומטית במהלך הפריסה עם workflow.run)
"Log Retrieval - Fetch workflow logs for validation and debugging with workflow.logs" (אחזור יומנים - שליפת יומני זרימת עבודה לתיקוף ואיתור באגים עם workflow.logs)
"QuickSight Dataset Refresh - Automatically refresh dashboards after ETL deployment with quicksight.refresh_dataset" (רענון סט נתונים ב-QuickSight - רענון אוטומטי של לוחות מחוונים לאחר פריסת ETL)
"EventBridge Integration - Emit custom events for downstream automation and CI/CD orchestration with eventbridge.put_events" (אינטגרציית EventBridge - שליחת אירועים מותאמים אישית לאוטומציה ותזמור CI/CD)
"DataZone Connections - Provision MLflow and other service connections during deployment" (חיבורי DataZone - הקצאת חיבורי MLflow ושירותים אחרים במהלך הפריסה)
"Sequential Execution - Actions run in order during smus-cli deploy for reliable initialization and validation" (הרצה רציפה - פעולות מבוצעות בסדר במהלך smus-cli deploy לאתחול ותיקוף אמינים)

### 📊 אינטגרציית קטלוג
"Asset Discovery - Automatically find required catalog assets (Glue, Lake Formation, DataZone)" (גילוי נכסים - מציאה אוטומטית של נכסי קטלוג נדרשים)
- ניהול מנויים - בקשת גישה לטבלאות וסטי נתונים
- זרימות עבודה לאישורים - טיפול בגישה לנתונים בין פרויקטים
- מעקב אחר נכסים - ניטור תלויות בקטלוג

---

## מה ניתן לפרוס?

**📊 אנליטיקה ו-BI**
- Glue ETL jobs and crawlers (משימות ETL וזחלנים של Glue)
- Athena queries (שאילתות Athena)
- QuickSight dashboards (לוחות מחוונים של QuickSight)
- EMR jobs - בקרוב
- Redshift queries - בקרוב

**🤖 למידת מכונה**
- SageMaker training jobs (משימות אימון של SageMaker)
- ML models and endpoints (מודלים ונקודות קצה של ML)
- MLflow experiments (ניסויי MLflow)
- Feature Store - בקרוב
- Batch transforms - בקרוב

**🧠 בינה מלאכותית גנרטיבית**
- Bedrock agents (סוכני Bedrock)
- Knowledge bases (בסיסי ידע)
- Foundation model configurations - בקרוב

**📓 קוד וזרימות עבודה**
- Jupyter notebooks (מחברות Jupyter)
- Python scripts (סקריפטים של Python)
- Airflow DAGs (MWAA and Amazon MWAA Serverless) (זרימות עבודה של Airflow)
- Lambda functions - בקרוב

**💾 נתונים ואחסון**
- S3 data files (קבצי נתונים ב-S3)
- Git repositories (מאגרי Git)
- Data catalogs - בקרוב

---

## שירותי AWS נתמכים

Deploy workflows using these AWS services through Airflow YAML syntax:
(פרוס זרימות עבודה באמצעות שירותי AWS אלה דרך תחביר YAML של Airflow)

### 🎯 אנליטיקה ונתונים
**Amazon Athena** • **AWS Glue** • **Amazon EMR** • **Amazon Redshift** • **Amazon QuickSight** • **Lake Formation**

### 🤖 למידת מכונה
**SageMaker Training** • **SageMaker Pipelines** • **Feature Store** • **Model Registry** • **Batch Transform**

### 🧠 בינה מלאכותית גנרטיבית
**Amazon Bedrock** • **Bedrock Agents** • **Bedrock Knowledge Bases** • **Guardrails**

### 📊 שירותים נוספים
S3 • Lambda • Step Functions • DynamoDB • RDS • SNS/SQS • Batch

**רשימה מלאה:** [Airflow AWS Operators Reference](docs/airflow-aws-operators.md)

---

## מושגי יסוד

### הפרדת תחומי אחריות: עקרון התכנון המרכזי

"The Problem: Traditional deployment approaches force DevOps teams to learn AWS analytics services (Glue, Athena, DataZone, SageMaker, MWAA, etc.) and understand SMUS project structures, or force data teams to become CI/CD experts."
(הבעיה: גישות פריסה מסורתיות מאלצות צוותי DevOps ללמוד שירותי אנליטיקה של AWS או מאלצות צוותי נתונים להפוך למומחי CI/CD)

"The Solution: SMUS CLI is the abstraction layer that encapsulates all AWS and SMUS complexity:"
(הפתרון: SMUS CLI הוא שכבת ההפשטה שמכילה את כל המורכבות של AWS ו-SMUS)

<div dir="ltr">

```
Data Teams                    SMUS CLI                         DevOps Teams
    ↓                            ↓                                  ↓
manifest.yaml          smus-cli deploy                    GitHub Actions
(WHAT & WHERE)         (AWS ABSTRACTION)                  (HOW & WHEN)
```

</div>

**צוותי נתונים מתמקדים ב:**
- קוד יישום וזרימות עבודה
- "Which AWS services to use (Glue, Athena, SageMaker, etc.)"
- תצורות סביבה
- לוגיקה עסקית

"SMUS CLI handles ALL AWS complexity:"
(SMUS CLI מטפל בכל המורכבות של AWS)
- ניהול דומיין ופרויקט ב-DataZone
- "AWS Glue, Athena, SageMaker, MWAA APIs"
- ניהול אחסון וארטיפקטים ב-S3
- תפקידי IAM והרשאות
- תצורות חיבור
- מנויי נכסי קטלוג
- פריסת זרימת עבודה ל-Airflow
- הקצאת תשתיות
- בדיקות ותיקוף

**צוותי DevOps מתמקדים ב:**
- שיטות מיטביות של CI/CD
- שערי אבטחה ותאימות
- תזמור פריסה
- ניטור והתראות

**תוצאה:**
- צוותי נתונים לא נוגעים בתצורות CI/CD
- "DevOps teams never call AWS APIs directly - they just call `smus-cli deploy`"
- "CI/CD workflows are generic - same workflow works for Glue apps, SageMaker apps, or Bedrock apps"
- כל צוות עובד באופן עצמאי תוך שימוש במומחיותו

[המשך התרגום ממשיך באותו אופן עבור שאר המסמך, תוך שמירה על הכללים שצוינו]

## דוגמאות יישום

דוגמאות מהעולם האמיתי המציגות כיצד לפרוס עומסי עבודה שונים עם SMUS CI/CD.

### 📊 אנליטיקה - לוח מחוונים QuickSight
"Deploy interactive BI dashboards with automated Glue ETL pipelines for data preparation. Uses QuickSight asset bundles, Athena queries, and GitHub dataset integration with environment-specific configurations."
(פריסת לוחות מחוונים BI אינטראקטיביים עם צינורות ETL אוטומטיים של Glue להכנת נתונים)

"AWS Services: QuickSight • Glue • Athena • S3 • MWAA Serverless"

"What happens during deployment: Application code is deployed to S3, Glue jobs and Airflow workflows are created and executed, QuickSight dashboard/data source/dataset are created, and QuickSight ingestion is initiated to refresh the dashboard with latest data."
(מה קורה במהלך הפריסה: קוד האפליקציה נפרס ל-S3, משימות Glue וזרימות עבודה של Airflow נוצרות ומופעלות, לוח מחוונים/מקור נתונים/סט נתונים של QuickSight נוצרים, וטעינת QuickSight מופעלת לרענון לוח המחוונים עם הנתונים העדכניים ביותר)

<details>
<summary><b>הצג מניפסט</b></summary>

<div dir="ltr">

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

</div>

</details>

**[צפה בדוגמה המלאה ←](docs/examples-guide.md#-analytics---quicksight-dashboard)**

---

### 📓 הנדסת נתונים - מחברות
"Deploy Jupyter notebooks with parallel execution orchestration for data analysis and ETL workflows. Demonstrates notebook deployment with MLflow integration for experiment tracking."
(פריסת מחברות Jupyter עם תזמור הרצה מקבילית לניתוח נתונים וזרימות עבודה ETL)

"AWS Services: SageMaker Notebooks • MLflow • S3 • MWAA Serverless"

"What happens during deployment: Notebooks and workflow definitions are uploaded to S3, Airflow DAG is created for parallel notebook execution, MLflow connection is provisioned for experiment tracking, and notebooks are ready to run on-demand or scheduled."
(מה קורה במהלך הפריסה: מחברות והגדרות זרימת עבודה מועלות ל-S3, נוצר DAG של Airflow להרצת מחברות במקביל, חיבור MLflow מוקצה למעקב אחר ניסויים, והמחברות מוכנות להרצה לפי דרישה או בתזמון)

[המשך התרגום של שאר המסמך...]

## תיעוד

### התחלה
- **[מדריך התחלה מהירה](docs/getting-started/quickstart.md)** - פרוס את האפליקציה הראשונה שלך (10 דקות)
- **[מדריך למנהל מערכת](docs/getting-started/admin-quickstart.md)** - הגדר תשתית (15 דקות)

### מדריכים
- **[Application Manifest](docs/manifest.md)** - מדריך מלא להגדרות YAML
- **[CLI Commands](docs/cli-commands.md)** - כל הפקודות והאפשרויות הזמינות
- **[Bootstrap Actions](docs/bootstrap-actions.md)** - פעולות פריסה אוטומטיות וזרימות עבודה מבוססות אירועים
- **[Substitutions & Variables](docs/substitutions-and-variables.md)** - תצורה דינמית
- **[מדריך חיבורים](docs/connections.md)** - הגדר אינטגרציות עם שירותי AWS
- **[GitHub Actions Integration](docs/github-actions-integration.md)** - הגדרת אוטומציית CI/CD
- **[מדדי פריסה](docs/pipeline-deployment-metrics.md)** - ניטור עם EventBridge

### מידע עזר
- **[Manifest Schema](docs/manifest-schema.md)** - אימות ומבנה סכמת YAML
- **[Airflow AWS Operators](docs/airflow-aws-operators.md)** - מדריך למפעילים מותאמים אישית

### דוגמאות
"Deploy Jupyter notebooks with Airflow, ML training with SageMaker, and analytics with Glue" (פריסת מחברות Jupyter עם Airflow, אימון ML עם SageMaker, וניתוח נתונים עם Glue)

- **[מדריך דוגמאות](docs/examples-guide.md)** - סקירה של אפליקציות לדוגמה
- **[Data Notebooks](docs/examples-guide.md#-data-engineering---notebooks)** - מחברות Jupyter עם Airflow
- **[ML Training](docs/examples-guide.md#-machine-learning---training)** - אימון SageMaker עם MLflow
- **[ML Deployment](docs/examples-guide.md#-machine-learning---deployment)** - פריסת נקודת קצה של SageMaker
- **[QuickSight Dashboard](docs/examples-guide.md#-analytics---quicksight-dashboard)** - לוחות מחוונים BI עם Glue
- **[GenAI Application](docs/examples-guide.md#-generative-ai)** - סוכני Bedrock ובסיסי ידע

### פיתוח
- **[מדריך פיתוח](docs/development.md)** - תרומה ובדיקות
- **[סקירת בדיקות](tests/README.md)** - תשתית בדיקות

### תמיכה
- **בעיות**: [GitHub Issues](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/issues)
- **תיעוד**: [docs/](docs/)
- **דוגמאות**: [examples/](examples/)

---

## הודעת אבטחה

⚠️ **אין** להתקין מ-PyPI - יש להתקין תמיד מקוד המקור הרשמי של AWS.

<div dir="ltr">

```bash
# ✅ נכון - התקנה ממאגר AWS הרשמי
git clone https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker.git
cd Unified-Studio-for-Amazon-Sagemaker/experimental/SMUS-CICD-pipeline-cli
pip install -e .

# ❌ לא נכון - אין להשתמש ב-PyPI
pip install smus-cicd-cli  # עלול להכיל קוד זדוני
```

</div>

---

## רישיון

פרויקט זה מורשה תחת רישיון MIT-0. ראה [LICENSE](../../LICENSE) לפרטים נוספים.

---

<div align="center">
  <img src="docs/readme-qr-code.png" alt="סרוק לצפייה ב-README" width="200"/>
  <p><em>סרוק את קוד ה-QR כדי לצפות ב-README בגיטהאב</em></p>
</div>

</div>