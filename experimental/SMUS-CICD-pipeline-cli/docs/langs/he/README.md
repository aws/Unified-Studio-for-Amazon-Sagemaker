# SMUS CI/CD Pipeline CLI

**אוטומציה של פריסת אפליקציות נתונים בסביבות SageMaker Unified Studio**

פרוס DAGs של Airflow, מחברות Jupyter, ו-workflows של ML מפיתוח לייצור בביטחון מלא. נבנה עבור מדעני נתונים, מהנדסי נתונים, מהנדסי ML, ומפתחי אפליקציות GenAI העובדים עם צוותי DevOps.

**עובד עם אסטרטגיית הפריסה שלך:** בין אם אתה משתמש בענפי git (מבוסס-branch), ארטיפקטים מגורסאים (מבוסס-bundle), תגיות git (מבוסס-tag), או פריסה ישירה - ה-CLI הזה תומך ב-workflow שלך. הגדר את האפליקציה שלך פעם אחת, פרוס אותה בדרך שלך.

---

## למה SMUS CI/CD CLI?

✅ **שכבת הפשטה של AWS** - CLI מכיל את כל המורכבות של אנליטיקה, ML ו-SMUS של AWS - צוותי DevOps לעולם לא קוראים ישירות ל-API של AWS  
✅ **הפרדת תחומי אחריות** - צוותי נתונים מגדירים מה לפרוס (manifest.yaml), צוותי DevOps מגדירים איך ומתי (CI/CD workflows)  
✅ **תהליכי CI/CD גנריים** - אותו workflow עובד עבור Glue, SageMaker, Bedrock, QuickSight, או כל שילוב של שירותי AWS  
✅ **פריסה בביטחון** - בדיקות ותיקוף אוטומטיים לפני הפריסה לייצור  
✅ **ניהול מרובה סביבות** - מבדיקות → לייצור עם תצורה ספציפית לכל סביבה  
✅ **תשתית כקוד** - manifest של אפליקציות בבקרת גרסאות ופריסות הניתנות לשחזור  
✅ **תהליכי workflow מונעי אירועים** - הפעלת workflows באופן אוטומטי דרך EventBridge בעת פריסה  

---

## התחלה מהירה

**התקנה מהמקור:**
```bash
git clone https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker.git
cd Unified-Studio-for-Amazon-Sagemaker/experimental/SMUS-CICD-pipeline-cli
pip install -e .
```

**פריסת האפליקציה הראשונה שלך:**
```bash
# אימות הגדרות
smus-cli describe --manifest manifest.yaml --connect

# יצירת bundle לפריסה (אופציונלי)
smus-cli bundle --manifest manifest.yaml

# פריסה לסביבת בדיקות
smus-cli deploy --targets test --manifest manifest.yaml

# הרצת בדיקות תיקוף
smus-cli test --manifest manifest.yaml --targets test
```

**ראה בפעולה:** [Live GitHub Actions Example](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/actions/runs/17631303500)

---

## למי זה מיועד?

### 👨‍💻 צוותי נתונים (מדעני נתונים, מהנדסי נתונים, מפתחי אפליקציות GenAI)
**אתם מתמקדים ב:** האפליקציה שלכם - מה לפרוס, איפה לפרוס, ואיך היא רצה  
**אתם מגדירים:** manifest של האפליקציה (`manifest.yaml`) עם הקוד, workflow-ים, והתצורות שלכם  
**אתם לא צריכים לדעת:** pipeline-ים של CI/CD, GitHub Actions, אוטומציה של פריסה  

→ **[מדריך התחלה מהירה](docs/getting-started/quickstart.md)** - פרסו את האפליקציה הראשונה שלכם תוך 10 דקות  

**כולל דוגמאות עבור:**
- הנדסת נתונים (Glue, Notebooks, Athena)
- workflow-ים של ML (SageMaker, Notebooks)
- אפליקציות GenAI (Bedrock, Notebooks)

**פעולות Bootstrap - אוטומציה של משימות לאחר הפריסה:**

הגדירו פעולות ב-manifest שירוצו אוטומטית לאחר הפריסה:
- הפעלת workflow-ים מיידית (ללא צורך בהפעלה ידנית)
- רענון לוחות מחוונים של QuickSight עם הנתונים העדכניים ביותר
- הגדרת חיבורי MLflow למעקב אחר ניסויים
- שליפת לוגים לאימות
- שליחת אירועים להפעלת תהליכים במורד הזרם

דוגמה:
```yaml
bootstrap:
  actions:
    - type: workflow.run
      workflowName: etl_pipeline
      wait: true
    - type: quicksight.refresh_dataset
      refreshScope: IMPORTED
```

### 🔧 צוותי DevOps
**אתם מתמקדים ב:** שיטות מיטביות של CI/CD, אבטחה, תאימות ואוטומציה של פריסה  
**אתם מגדירים:** תבניות workflow שאוכפות בדיקות, אישורים ומדיניות קידום  
**אתם לא צריכים לדעת:** פרטים ספציפיים לאפליקציה, שירותי AWS בשימוש, DataZone APIs, מבני פרויקט SMUS, או לוגיקה עסקית  

→ **[מדריך למנהל מערכת](docs/getting-started/admin-quickstart.md)** - הגדירו תשתית ו-pipeline-ים תוך 15 דקות  
→ **[תבניות GitHub Workflow](git-templates/)** - תבניות workflow גנריות, לשימוש חוזר עבור פריסה אוטומטית

**ה-CLI הוא שכבת ההפשטה שלכם:** אתם פשוט קוראים ל-`smus-cli deploy` - ה-CLI מטפל בכל האינטראקציות עם שירותי AWS (DataZone, Glue, Athena, SageMaker, MWAA, S3, IAM, וכו') ומבצע פעולות bootstrap (הרצות workflow, הזרמת לוגים, רענוני QuickSight, אירועי EventBridge). ה-workflow-ים שלכם נשארים פשוטים וגנריים.

---

## תכונות מפתח

### 🚀 פריסה אוטומטית
- **Application Manifest** - הגדרת תוכן האפליקציה, workflow ויעדי פריסה ב-YAML
- **פריסה גמישה** - מצבי פריסה מבוססי bundle (ארטיפקט) או ישירים (מבוססי git)
- **פריסה מרובת יעדים** - פריסה לסביבות בדיקה וייצור בפקודה אחת
- **משתני סביבה** - תצורה דינמית באמצעות החלפת `${VAR}`
- **בקרת גרסאות** - מעקב אחר פריסות ב-S3 או git להיסטוריית פריסה

### 🔍 בדיקות ותיקוף
- **בדיקות אוטומטיות** - הרצת בדיקות תיקוף לפני קידום לייצור
- **שערי איכות** - חסימת פריסות אם הבדיקות נכשלות
- **ניטור workflow** - מעקב אחר סטטוס ביצוע ולוגים
- **בדיקות תקינות** - אימות נכונות הפריסה

### 🔄 אינטגרציית pipeline CI/CD
- **GitHub Actions** - workflow מובנים מראש ל-pipeline CI/CD לפריסה אוטומטית
- **GitLab CI** - תמיכה מובנית ב-pipeline של GitLab CI/CD
- **משתני סביבה** - תצורה גמישה לכל פלטפורמת CI/CD
- **תמיכה ב-Webhook** - הפעלת פריסות מאירועים חיצוניים

### 🏗️ ניהול תשתיות
- **יצירת פרויקטים** - הקמה אוטומטית של פרויקטי SageMaker Unified Studio
- **הגדרת חיבורים** - תצורת חיבורים ל-S3, Airflow, Athena ו-Lakehouse
- **מיפוי משאבים** - קישור משאבי AWS לחיבורי הפרויקט
- **ניהול הרשאות** - שליטה בגישה ושיתוף פעולה

### ⚡ פעולות אתחול
- **הרצת workflow אוטומטית** - הפעלת workflow אוטומטית במהלך פריסה עם `workflow.run` (השתמש ב-`trailLogs: true` להזרמת לוגים והמתנה להשלמה)
- **אחזור לוגים** - שליפת לוגי workflow לתיקוף ודיבוג עם `workflow.logs`
- **רענון Dataset ב-QuickSight** - רענון אוטומטי של לוחות מחוונים לאחר פריסת ETL עם `quicksight.refresh_dataset`
- **אינטגרציית EventBridge** - שליחת אירועים מותאמים אישית לאוטומציה ותזמור CI/CD עם `eventbridge.put_events`
- **חיבורי DataZone** - הקמת חיבורי MLflow ושירותים אחרים במהלך הפריסה
- **הרצה רציפה** - פעולות רצות בסדר במהלך `smus-cli deploy` לאתחול ותיקוף אמינים

### 📊 אינטגרציית קטלוג
- **גילוי נכסים** - מציאה אוטומטית של נכסי קטלוג נדרשים (Glue, Lake Formation, DataZone)
- **ניהול מנויים** - בקשת גישה לטבלאות ומאגרי נתונים
- **תהליכי אישור** - טיפול בגישה לנתונים בין פרויקטים
- **מעקב נכסים** - ניטור תלויות קטלוג

---

## מה אפשר לפרוס?

**📊 אנליטיקה ו-BI**
- משימות וסורקים של Glue ETL
- שאילתות Athena
- לוחות מחוונים של QuickSight
- משימות EMR (בעתיד)
- שאילתות Redshift (בעתיד)

**🤖 למידת מכונה**
- משימות אימון של SageMaker
- מודלים ונקודות קצה של ML
- ניסויי MLflow
- Feature Store (בעתיד)
- טרנספורמציות אצווה (בעתיד)

**🧠 בינה מלאכותית גנרטיבית**
- סוכני Bedrock
- מאגרי ידע
- תצורות מודל בסיס (בעתיד)

**📓 קוד ו-workflow**
- מחברות Jupyter
- סקריפטים של Python
- DAGs של Airflow (MWAA ו-Amazon MWAA Serverless)
- פונקציות Lambda (בעתיד)

**💾 נתונים ואחסון**
- קבצי נתונים של S3
- מאגרי Git
- קטלוגי נתונים (בעתיד)

---

## שירותי AWS נתמכים

פריסת workflows באמצעות שירותי AWS אלה דרך תחביר YAML של Airflow:

### 🎯 אנליטיקה ונתונים
**Amazon Athena** • **AWS Glue** • **Amazon EMR** • **Amazon Redshift** • **Amazon QuickSight** • **Lake Formation**

### 🤖 למידת מכונה
**SageMaker Training** • **SageMaker Pipelines** • **Feature Store** • **Model Registry** • **Batch Transform**

### 🧠 בינה מלאכותית גנרטיבית
**Amazon Bedrock** • **Bedrock Agents** • **Bedrock Knowledge Bases** • **Guardrails**

### 📊 שירותים נוספים
S3 • Lambda • Step Functions • DynamoDB • RDS • SNS/SQS • Batch

**ראה רשימה מלאה:** [Airflow AWS Operators Reference](docs/airflow-aws-operators.md)

---

## מושגי יסוד

### הפרדת תחומי אחריות: עקרון התכנון המרכזי

**הבעיה:** גישות פריסה מסורתיות מאלצות צוותי DevOps ללמוד שירותי אנליטיקה של AWS (Glue, Athena, DataZone, SageMaker, MWAA וכו') ולהבין מבני פרויקט SMUS, או מאלצות צוותי נתונים להפוך למומחי CI/CD.

**הפתרון:** SMUS CLI הוא שכבת ההפשטה שמכילה את כל המורכבות של AWS ו-SMUS:

```
Data Teams                    SMUS CLI                         DevOps Teams
    ↓                            ↓                                  ↓
manifest.yaml          smus-cli deploy                    GitHub Actions
(מה ואיפה)            (הפשטת AWS)                        (איך ומתי)
```

**צוותי נתונים מתמקדים ב:**
- קוד יישום ו-workflow
- אילו שירותי AWS לשימוש (Glue, Athena, SageMaker וכו')
- תצורות סביבה
- לוגיקה עסקית

**SMUS CLI מטפל בכל מורכבות AWS:**
- ניהול דומיין ופרויקט DataZone
- AWS Glue, Athena, SageMaker, MWAA APIs
- ניהול אחסון ו-artifact ב-S3
- תפקידי והרשאות IAM
- הגדרות חיבור
- מנויי נכסי קטלוג
- פריסת workflow ל-Airflow
- הקצאת תשתית
- בדיקה ותיקוף

**צוותי DevOps מתמקדים ב:**
- שיטות מיטביות של CI/CD (בדיקות, אישורים, התראות)
- שערי אבטחה ותאימות
- תזמור פריסה
- ניטור והתראות

**תוצאה:**
- צוותי נתונים לעולם לא נוגעים בהגדרות CI/CD
- **צוותי DevOps לעולם לא קוראים ל-API של AWS ישירות** - הם פשוט קוראים ל-`smus-cli deploy`
- **תהליכי CI/CD הם גנריים** - אותו workflow עובד עבור יישומי Glue, יישומי SageMaker, או יישומי Bedrock
- שני הצוותים עובדים באופן עצמאי תוך שימוש במומחיות שלהם

---

### Application Manifest
קובץ YAML הצהרתי (`manifest.yaml`) המגדיר את יישום הנתונים שלך:
- **פרטי יישום** - שם, גרסה, תיאור
- **תוכן** - קוד ממאגרי git, נתונים/מודלים מאחסון, לוחות מחוונים של QuickSight
- **Workflows** - DAGs של Airflow לתזמור ואוטומציה
- **Stages** - לאן לפרוס (סביבות dev, test, prod)
- **תצורה** - הגדרות ספציפיות לסביבה, חיבורים ופעולות אתחול

**נוצר ומנוהל על ידי צוותי נתונים.** מגדיר **מה** לפרוס ו**איפה**. לא נדרש ידע ב-CI/CD.

### Application
עומס העבודה של הנתונים/אנליטיקה שמתפרס:
- DAGs של Airflow וסקריפטים של Python
- מחברות Jupyter וקבצי נתונים
- מודלים ML וקוד אימון
- צינורות ETL וטרנספורמציות
- סוכני GenAI ושרתי MCP
- הגדרות מודל בסיס

### Stage
סביבת פריסה (dev, test, prod) הממופה לפרויקט SageMaker Unified Studio:
- תצורת דומיין ואזור
- שם פרויקט והגדרות
- חיבורי משאבים (S3, Airflow, Athena, Glue)
- פרמטרים ספציפיים לסביבה
- מיפוי ענף אופציונלי לפריסות מבוססות git

### Workflow
לוגיקת תזמור המבצעת את היישום שלך. ל-Workflows יש שתי מטרות:

**1. זמן פריסה:** יצירת משאבי AWS נדרשים במהלך הפריסה
- הקצאת תשתית (דליי S3, מסדי נתונים, תפקידי IAM)
- הגדרת חיבורים והרשאות
- הגדרת ניטור ורישום

**2. זמן ריצה:** הפעלת צינורות נתונים ו-ML מתמשכים
- הפעלה מתוזמנת (יומית, שעתית וכו')
- טריגרים מבוססי אירועים (העלאות S3, קריאות API)
- עיבוד נתונים וטרנספורמציות
- אימון והסקת מודלים

Workflows מוגדרים כ-DAGs של Airflow (גרפים מכוונים אציקליים) בפורמט YAML. תומך ב-[MWAA (Managed Workflows for Apache Airflow)](https://aws.amazon.com/managed-workflows-for-apache-airflow/) ו-[Amazon MWAA Serverless](https://aws.amazon.com/blogs/big-data/introducing-amazon-mwaa-serverless/) ([מדריך למשתמש](https://docs.aws.amazon.com/mwaa/latest/mwaa-serverless-userguide/what-is-mwaa-serverless.html)).

### CI/CD Automation
תהליכי GitHub Actions (או מערכות CI/CD אחרות) המאוטמטים פריסה:
- **נוצר ומנוהל על ידי צוותי DevOps**
- מגדיר **איך** ו**מתי** לפרוס
- מריץ בדיקות ושערי איכות
- מנהל קידום בין יעדים
- אוכף מדיניות אבטחה ותאימות
- דוגמה: `.github/workflows/deploy.yml`

**תובנה מרכזית:** צוותי DevOps יוצרים תהליכים גנריים, לשימוש חוזר שעובדים עבור כל יישום. הם לא צריכים לדעת אם היישום משתמש ב-Glue, SageMaker, או Bedrock - ה-CLI מטפל בכל האינטראקציות עם שירותי AWS. התהליך פשוט קורא ל-`smus-cli deploy` וה-CLI עושה את השאר.

### מצבי פריסה

**מבוסס-Bundle (Artifact):** יצירת ארכיון מגורסה → פריסת ארכיון לשלבים
- טוב עבור: מעקב ביקורת, יכולת שחזור, תאימות
- פקודה: `smus-cli bundle` ואז `smus-cli deploy --manifest app.tar.gz`

**ישיר (מבוסס-Git):** פריסה ישירה מהמקורות ללא artifacts ביניים
- טוב עבור: תהליכים פשוטים יותר, איטרציה מהירה, git כמקור האמת
- פקודה: `smus-cli deploy --manifest manifest.yaml --stage test`

שני המצבים עובדים עם כל שילוב של מקורות אחסון ו-git.

---

### איך הכל עובד יחד

```
1. צוות נתונים                2. צוות DevOps                 3. SMUS CLI (ההפשטה)
   ↓                               ↓                              ↓
יוצר manifest.yaml             יוצר תהליך גנרי               התהליך קורא:
- משימות Glue                  - בדיקה במיזוג                 smus-cli deploy --manifest manifest.yaml
- אימון SageMaker              - אישור לפרודקשן                 ↓
- שאילתות Athena               - סריקות אבטחה                CLI מטפל בכל מורכבות AWS:
- מיקומי S3                    - כללי התראה                  - DataZone APIs
                                                              - Glue/Athena/SageMaker APIs
                               עובד עבור כל יישום!           - פריסת MWAA
                               לא נדרש ידע ב-AWS!            - ניהול S3
                                                              - תצורת IAM
                                                              - הקצאת תשתית
                                                                ↓
                                                              הצלחה!
```

**היופי:**
- צוותי נתונים לעולם לא לומדים GitHub Actions
- **צוותי DevOps לעולם לא קוראים ל-API של AWS** - ה-CLI מכיל את כל המורכבות של אנליטיקה, ML ו-SMUS של AWS
- תהליכי CI/CD הם פשוטים: פשוט קוראים ל-`smus-cli deploy`
- אותו תהליך עובד עבור כל יישום, ללא קשר לשירותי AWS בשימוש

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


## תיעוד

### התחלה
- **[מדריך התחלה מהירה](docs/getting-started/quickstart.md)** - פריסת האפליקציה הראשונה שלך (10 דקות)
- **[מדריך למנהל מערכת](docs/getting-started/admin-quickstart.md)** - הגדרת תשתית (15 דקות)

### מדריכים
- **[manifest אפליקציה](docs/manifest.md)** - מדריך מלא להגדרות YAML
- **[פקודות CLI](docs/cli-commands.md)** - כל הפקודות והאפשרויות הזמינות
- **[פעולות Bootstrap](docs/bootstrap-actions.md)** - פעולות פריסה אוטומטיות ו-workflow מבוססי אירועים
- **[החלפות ומשתנים](docs/substitutions-and-variables.md)** - תצורה דינמית
- **[מדריך חיבורים](docs/connections.md)** - הגדרת אינטגרציות שירותי AWS
- **[אינטגרציית GitHub Actions](docs/github-actions-integration.md)** - הגדרת אוטומציית CI/CD
- **[מדדי פריסה](docs/pipeline-deployment-metrics.md)** - ניטור עם EventBridge

### מידע עזר
- **[סכמת Manifest](docs/manifest-schema.md)** - אימות ומבנה סכמת YAML
- **[Airflow AWS Operators](docs/airflow-aws-operators.md)** - מדריך operators מותאמים אישית

### דוגמאות
- **[מדריך דוגמאות](docs/examples-guide.md)** - סקירה של אפליקציות לדוגמה
- **[מחברות נתונים](docs/examples-guide.md#-data-engineering---notebooks)** - מחברות Jupyter עם Airflow
- **[אימון ML](docs/examples-guide.md#-machine-learning---training)** - אימון SageMaker עם MLflow
- **[פריסת ML](docs/examples-guide.md#-machine-learning---deployment)** - פריסת נקודת קצה של SageMaker
- **[לוח מחוונים QuickSight](docs/examples-guide.md#-analytics---quicksight-dashboard)** - לוחות מחוונים BI עם Glue
- **[אפליקציית GenAI](docs/examples-guide.md#-generative-ai)** - סוכני Bedrock ובסיסי ידע

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

```bash
# ✅ נכון - התקנה ממאגר AWS הרשמי
git clone https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker.git
cd Unified-Studio-for-Amazon-Sagemaker/experimental/SMUS-CICD-pipeline-cli
pip install -e .

# ❌ לא נכון - אין להשתמש ב-PyPI
pip install smus-cicd-cli  # עלול להכיל קוד זדוני
```

---

## רישיון

פרויקט זה מורשה תחת רישיון MIT-0. ראה [LICENSE](../../LICENSE) לפרטים נוספים.