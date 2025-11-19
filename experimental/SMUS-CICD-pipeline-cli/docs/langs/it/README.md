# SMUS CI/CD Pipeline CLI

**Automatizza il deployment di applicazioni dati tra gli ambienti SageMaker Unified Studio**

Distribuisci DAG Airflow, notebook Jupyter e workflow ML dallo sviluppo alla produzione con sicurezza. Creato per data scientist, data engineer, ML engineer e sviluppatori di app GenAI che lavorano con team DevOps.

**Si adatta alla tua strategia di deployment:** Che tu utilizzi branch git (basato su branch), artefatti versionati (basato su bundle), tag git (basato su tag) o deployment diretto - questa CLI supporta il tuo workflow. Definisci la tua applicazione una volta, distribuiscila a modo tuo.

---

## Perché SMUS CI/CD CLI?

✅ **Livello di Astrazione AWS** - La CLI incapsula tutta la complessità di AWS analytics, ML e SMUS - i team DevOps non chiamano mai direttamente le API AWS  
✅ **Separazione delle Responsabilità** - I team di dati definiscono COSA distribuire (manifest.yaml), i team DevOps definiscono COME e QUANDO (workflow CI/CD)  
✅ **Workflow CI/CD Generici** - Lo stesso workflow funziona per Glue, SageMaker, Bedrock, QuickSight o qualsiasi combinazione di servizi AWS  
✅ **Distribuzione con Sicurezza** - Test e validazione automatizzati prima della produzione  
✅ **Gestione Multi-Ambiente** - Test → Prod con configurazione specifica per ambiente  
✅ **Infrastruttura come Codice** - Manifest delle applicazioni con controllo di versione e distribuzioni riproducibili  
✅ **Workflow Event-Driven** - Attivazione automatica dei workflow tramite EventBridge alla distribuzione  

---

## Avvio Rapido

**Installa dai sorgenti:**
```bash
git clone https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker.git
cd Unified-Studio-for-Amazon-Sagemaker/experimental/SMUS-CICD-pipeline-cli
pip install -e .
```

**Distribuisci la tua prima applicazione:**
```bash
# Valida la configurazione
smus-cli describe --manifest manifest.yaml --connect

# Crea il bundle di distribuzione (opzionale)
smus-cli bundle --manifest manifest.yaml

# Distribuisci nell'ambiente di test
smus-cli deploy --targets test --manifest manifest.yaml

# Esegui i test di validazione
smus-cli test --manifest manifest.yaml --targets test
```

**Guardalo in azione:** [Live GitHub Actions Example](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/actions/runs/17631303500)

---

## Per Chi È Questo?

### 👨‍💻 Team di Data (Data Scientist, Data Engineer, Sviluppatori di App GenAI)
**Ti concentri su:** La tua applicazione - cosa distribuire, dove distribuire e come funziona  
**Definisci:** Il manifest dell'applicazione (`manifest.yaml`) con il tuo codice, workflow e configurazioni  
**Non devi conoscere:** Pipeline CI/CD, GitHub Actions, automazione del deployment  

→ **[Guida Rapida](docs/getting-started/quickstart.md)** - Distribuisci la tua prima applicazione in 10 minuti  

**Include esempi per:**
- Data Engineering (Glue, Notebooks, Athena)
- ML Workflows (SageMaker, Notebooks)
- Applicazioni GenAI (Bedrock, Notebooks)

**Azioni Bootstrap - Automatizza le Attività Post-Deployment:**

Definisci azioni nel tuo manifest che vengono eseguite automaticamente dopo il deployment:
- Attiva workflow immediatamente (nessuna esecuzione manuale necessaria)
- Aggiorna le dashboard QuickSight con i dati più recenti
- Configura le connessioni MLflow per il tracciamento degli esperimenti
- Recupera i log per la validazione
- Emetti eventi per attivare processi a valle

Esempio:
```yaml
bootstrap:
  actions:
    - type: workflow.run
      workflowName: etl_pipeline
      wait: true
    - type: quicksight.refresh_dataset
      refreshScope: IMPORTED
```

### 🔧 Team DevOps
**Ti concentri su:** Best practice CI/CD, sicurezza, conformità e automazione del deployment  
**Definisci:** Template di workflow che impongono test, approvazioni e politiche di promozione  
**Non devi conoscere:** Dettagli specifici dell'applicazione, servizi AWS utilizzati, API DataZone, strutture dei progetti SMUS o logica di business  

→ **[Guida Amministratore](docs/getting-started/admin-quickstart.md)** - Configura infrastruttura e pipeline in 15 minuti  
→ **[Template Workflow GitHub](git-templates/)** - Template di workflow generici e riutilizzabili per il deployment automatizzato

**La CLI è il tuo livello di astrazione:** Devi solo chiamare `smus-cli deploy` - la CLI gestisce tutte le interazioni con i servizi AWS (DataZone, Glue, Athena, SageMaker, MWAA, S3, IAM, ecc.) ed esegue le azioni bootstrap (esecuzioni workflow, streaming dei log, aggiornamenti QuickSight, eventi EventBridge). I tuoi workflow rimangono semplici e generici.

---

## Funzionalità Principali

### 🚀 Deployment Automatizzato
- **Application Manifest** - Definisci i contenuti dell'applicazione, i workflow e i target di deployment in YAML
- **Deployment Flessibile** - Modalità di deployment basate su bundle (artifact) o dirette (basate su git)
- **Deployment Multi-Target** - Distribuisci in test e prod con un singolo comando
- **Environment Variables** - Configurazione dinamica usando la sostituzione `${VAR}`
- **Version Control** - Traccia i deployment in S3 o git per la cronologia delle distribuzioni

### 🔍 Test e Validazione
- **Test Automatizzati** - Esegui test di validazione prima della promozione in produzione
- **Quality Gates** - Blocca i deployment se i test falliscono
- **Workflow Monitoring** - Traccia lo stato di esecuzione e i log
- **Health Checks** - Verifica la correttezza del deployment

### 🔄 Integrazione CI/CD Pipeline
- **GitHub Actions** - Workflow CI/CD pipeline precostruiti per il deployment automatizzato
- **GitLab CI** - Supporto nativo per pipeline CI/CD GitLab
- **Environment Variables** - Configurazione flessibile per qualsiasi piattaforma CI/CD
- **Webhook Support** - Attiva i deployment da eventi esterni

### 🏗️ Gestione Infrastruttura
- **Project Creation** - Provisioning automatico dei progetti SageMaker Unified Studio
- **Connection Setup** - Configura connessioni S3, Airflow, Athena e Lakehouse
- **Resource Mapping** - Collega risorse AWS alle connessioni del progetto
- **Permission Management** - Controlla accesso e collaborazione

### ⚡ Bootstrap Actions
- **Automated Workflow Execution** - Attiva workflow automaticamente durante il deployment con `workflow.run` (usa `trailLogs: true` per lo streaming dei log e attendi il completamento)
- **Log Retrieval** - Recupera i log del workflow per validazione e debug con `workflow.logs`
- **QuickSight Dataset Refresh** - Aggiorna automaticamente le dashboard dopo il deployment ETL con `quicksight.refresh_dataset`
- **EventBridge Integration** - Emetti eventi personalizzati per automazione downstream e orchestrazione CI/CD con `eventbridge.put_events`
- **DataZone Connections** - Provisioning di connessioni MLflow e altri servizi durante il deployment
- **Sequential Execution** - Le azioni vengono eseguite in ordine durante `smus-cli deploy` per un'inizializzazione e validazione affidabile

### 📊 Integrazione Catalog
- **Asset Discovery** - Trova automaticamente gli asset catalog necessari (Glue, Lake Formation, DataZone)
- **Subscription Management** - Richiedi accesso a tabelle e dataset
- **Approval Workflows** - Gestisci l'accesso ai dati tra progetti
- **Asset Tracking** - Monitora le dipendenze del catalog

---

## Cosa Puoi Distribuire?

**📊 Analytics & BI**
- Job e crawler Glue ETL
- Query Athena
- Dashboard QuickSight
- Job EMR (futuro)
- Query Redshift (futuro)

**🤖 Machine Learning**
- Job di training SageMaker
- Modelli ML ed endpoint
- Esperimenti MLflow
- Feature Store (futuro)
- Trasformazioni batch (futuro)

**🧠 Intelligenza Artificiale Generativa**
- Agenti Bedrock
- Basi di conoscenza
- Configurazioni di modelli foundation (futuro)

**📓 Codice & Workflow**
- Notebook Jupyter
- Script Python
- DAG Airflow (MWAA e Amazon MWAA Serverless)
- Funzioni Lambda (futuro)

**💾 Dati & Archiviazione**
- File dati S3
- Repository Git
- Cataloghi dati (futuro)

---

## Servizi AWS Supportati

Distribuisci workflow utilizzando questi servizi AWS attraverso la sintassi YAML di Airflow:

### 🎯 Analytics & Dati
**Amazon Athena** • **AWS Glue** • **Amazon EMR** • **Amazon Redshift** • **Amazon QuickSight** • **Lake Formation**

### 🤖 Machine Learning
**SageMaker Training** • **SageMaker Pipelines** • **Feature Store** • **Model Registry** • **Batch Transform**

### 🧠 Intelligenza Artificiale Generativa
**Amazon Bedrock** • **Bedrock Agents** • **Bedrock Knowledge Bases** • **Guardrails**

### 📊 Servizi Aggiuntivi
S3 • Lambda • Step Functions • DynamoDB • RDS • SNS/SQS • Batch

**Vedi lista completa:** [Airflow AWS Operators Reference](docs/airflow-aws-operators.md)

---

## Concetti Fondamentali

### Separazione delle Responsabilità: Il Principio Chiave di Design

**Il Problema:** Gli approcci tradizionali al deployment costringono i team DevOps a imparare i servizi analytics AWS (Glue, Athena, DataZone, SageMaker, MWAA, ecc.) e comprendere le strutture dei progetti SMUS, o costringono i team di dati a diventare esperti di CI/CD.

**La Soluzione:** SMUS CLI è il livello di astrazione che incapsula tutta la complessità AWS e SMUS:

```
Team di Dati                   SMUS CLI                         Team DevOps
    ↓                            ↓                                  ↓
manifest.yaml          smus-cli deploy                    GitHub Actions
(COSA & DOVE)         (ASTRAZIONE AWS)                   (COME & QUANDO)
```

**I team di dati si concentrano su:**
- Codice applicativo e workflow
- Quali servizi AWS utilizzare (Glue, Athena, SageMaker, ecc.)
- Configurazioni dell'ambiente
- Logica di business

**SMUS CLI gestisce TUTTA la complessità AWS:**
- Gestione di domini e progetti DataZone
- API di AWS Glue, Athena, SageMaker, MWAA
- Gestione dello storage S3 e degli artifact
- Ruoli e permessi IAM
- Configurazioni delle connessioni
- Sottoscrizioni agli asset del catalogo
- Deployment dei workflow su Airflow
- Provisioning dell'infrastruttura
- Test e validazione

**I team DevOps si concentrano su:**
- Best practice CI/CD (test, approvazioni, notifiche)
- Controlli di sicurezza e conformità
- Orchestrazione del deployment
- Monitoraggio e alerting

**Risultato:**
- I team di dati non toccano mai le configurazioni CI/CD
- **I team DevOps non chiamano mai direttamente le API AWS** - chiamano solo `smus-cli deploy`
- **I workflow CI/CD sono generici** - lo stesso workflow funziona per app Glue, app SageMaker o app Bedrock
- Entrambi i team lavorano indipendentemente usando le proprie competenze

---

### Manifest dell'Applicazione
Un file YAML dichiarativo (`manifest.yaml`) che definisce la tua applicazione dati:
- **Dettagli applicazione** - Nome, versione, descrizione
- **Contenuto** - Codice da repository git, dati/modelli dallo storage, dashboard QuickSight
- **Workflow** - DAG Airflow per orchestrazione e automazione
- **Stage** - Dove effettuare il deployment (ambienti dev, test, prod)
- **Configurazione** - Impostazioni specifiche per ambiente, connessioni e azioni di bootstrap

**Creato e gestito dai team di dati.** Definisce **cosa** deployare e **dove**. Non richiede conoscenze CI/CD.

### Applicazione
Il tuo carico di lavoro dati/analytics da deployare:
- DAG Airflow e script Python
- Notebook Jupyter e file di dati
- Modelli ML e codice di training
- Pipeline ETL e trasformazioni
- Agenti GenAI e server MCP
- Configurazioni dei modelli foundation

### Stage
Un ambiente di deployment (dev, test, prod) mappato a un progetto SageMaker Unified Studio:
- Configurazione di dominio e regione
- Nome e impostazioni del progetto
- Connessioni alle risorse (S3, Airflow, Athena, Glue)
- Parametri specifici per ambiente
- Mapping opzionale dei branch per deployment basati su git

### Workflow
Logica di orchestrazione che esegue la tua applicazione. I workflow servono a due scopi:

**1. Durante il deployment:** Creare le risorse AWS necessarie durante il deployment
- Provisioning dell'infrastruttura (bucket S3, database, ruoli IAM)
- Configurazione di connessioni e permessi
- Configurazione di monitoraggio e logging

**2. Durante l'esecuzione:** Eseguire pipeline dati e ML continuative
- Esecuzione programmata (giornaliera, oraria, ecc.)
- Trigger basati su eventi (upload S3, chiamate API)
- Elaborazione e trasformazione dati
- Training e inferenza dei modelli

I workflow sono definiti come DAG Airflow (Directed Acyclic Graphs) in formato YAML. Supporta [MWAA (Managed Workflows for Apache Airflow)](https://aws.amazon.com/managed-workflows-for-apache-airflow/) e [Amazon MWAA Serverless](https://aws.amazon.com/blogs/big-data/introducing-amazon-mwaa-serverless/) ([User Guide](https://docs.aws.amazon.com/mwaa/latest/mwaa-serverless-userguide/what-is-mwaa-serverless.html)).

### Automazione CI/CD
Workflow GitHub Actions (o altri sistemi CI/CD) che automatizzano il deployment:
- **Creati e gestiti dai team DevOps**
- Definisce **come** e **quando** deployare
- Esegue test e controlli di qualità
- Gestisce la promozione tra target
- Applica policy di sicurezza e conformità
- Esempio: `.github/workflows/deploy.yml`

**Intuizione chiave:** I team DevOps creano workflow generici e riutilizzabili che funzionano per QUALSIASI applicazione. Non devono sapere se l'app usa Glue, SageMaker o Bedrock - la CLI gestisce tutte le interazioni con i servizi AWS. Il workflow chiama semplicemente `smus-cli deploy` e la CLI fa il resto.

### Modalità di Deployment

**Basato su Bundle (Artifact):** Crea archivio versionato → deploya archivio agli stage
- Vantaggi: tracciabilità, capacità di rollback, conformità
- Comando: `smus-cli bundle` poi `smus-cli deploy --manifest app.tar.gz`

**Diretto (Basato su Git):** Deploya direttamente dai sorgenti senza artifact intermedi
- Vantaggi: workflow più semplici, iterazione rapida, git come fonte di verità
- Comando: `smus-cli deploy --manifest manifest.yaml --stage test`

Entrambe le modalità funzionano con qualsiasi combinazione di storage e sorgenti git.

---

### Come Funziona Tutto Insieme

```
1. Team di Dati                2. Team DevOps                 3. SMUS CLI (L'Astrazione)
   ↓                               ↓                              ↓
Crea manifest.yaml            Crea workflow generico        Il workflow chiama:
- Job Glue                    - Test su merge               smus-cli deploy --manifest manifest.yaml
- Training SageMaker          - Approvazione per prod         ↓
- Query Athena               - Scansioni di sicurezza      La CLI gestisce TUTTA la complessità AWS:
- Posizioni S3               - Regole di notifica          - API DataZone
                                                           - API Glue/Athena/SageMaker
                             Funziona per QUALSIASI app!   - Deployment MWAA
                             Non serve conoscere AWS!      - Gestione S3
                                                           - Configurazione IAM
                                                           - Provisioning infrastruttura
                                                             ↓
                                                           Successo!
```

**La bellezza:**
- I team di dati non imparano mai GitHub Actions
- **I team DevOps non chiamano mai le API AWS** - la CLI incapsula tutta la complessità AWS analytics, ML e SMUS
- I workflow CI/CD sono semplici: basta chiamare `smus-cli deploy`
- Lo stesso workflow funziona per QUALSIASI applicazione, indipendentemente dai servizi AWS utilizzati

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


## Documentazione

### Per Iniziare
- **[Guida Rapida](docs/getting-started/quickstart.md)** - Distribuisci la tua prima applicazione (10 min)
- **[Guida Amministratore](docs/getting-started/admin-quickstart.md)** - Configura l'infrastruttura (15 min)

### Guide
- **[Application Manifest](docs/manifest.md)** - Riferimento completo configurazione YAML
- **[Comandi CLI](docs/cli-commands.md)** - Tutti i comandi e le opzioni disponibili
- **[Bootstrap Actions](docs/bootstrap-actions.md)** - Azioni di deployment automatizzate e workflow basati su eventi
- **[Sostituzioni & Variabili](docs/substitutions-and-variables.md)** - Configurazione dinamica
- **[Guida alle Connessioni](docs/connections.md)** - Configura integrazioni servizi AWS
- **[Integrazione GitHub Actions](docs/github-actions-integration.md)** - Configurazione automazione CI/CD
- **[Metriche di Deployment](docs/pipeline-deployment-metrics.md)** - Monitoraggio con EventBridge

### Riferimenti
- **[Schema Manifest](docs/manifest-schema.md)** - Validazione e struttura schema YAML
- **[Operatori AWS Airflow](docs/airflow-aws-operators.md)** - Riferimento operatori personalizzati

### Esempi
- **[Guida agli Esempi](docs/examples-guide.md)** - Guida agli esempi applicativi
- **[Data Notebooks](docs/examples-guide.md#-data-engineering---notebooks)** - Notebook Jupyter con Airflow
- **[Training ML](docs/examples-guide.md#-machine-learning---training)** - Training SageMaker con MLflow
- **[Deployment ML](docs/examples-guide.md#-machine-learning---deployment)** - Deployment endpoint SageMaker
- **[Dashboard QuickSight](docs/examples-guide.md#-analytics---quicksight-dashboard)** - Dashboard BI con Glue
- **[Applicazione GenAI](docs/examples-guide.md#-generative-ai)** - Agenti Bedrock e basi di conoscenza

### Sviluppo
- **[Guida allo Sviluppo](docs/development.md)** - Contribuire e testing
- **[Panoramica Test](tests/README.md)** - Infrastruttura di testing

### Supporto
- **Problemi**: [GitHub Issues](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/issues)
- **Documentazione**: [docs/](docs/)
- **Esempi**: [examples/](examples/)

---

## Avviso di Sicurezza

⚠️ **NON** installare da PyPI - installare sempre dal codice sorgente ufficiale AWS.

```bash
# ✅ Corretto - Installa dal repository ufficiale AWS
git clone https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker.git
cd Unified-Studio-for-Amazon-Sagemaker/experimental/SMUS-CICD-pipeline-cli
pip install -e .

# ❌ Sbagliato - Non usare PyPI
pip install smus-cicd-cli  # Potrebbe contenere codice malevolo
```

---

## Licenza

Questo progetto è concesso in licenza secondo i termini della Licenza MIT-0. Vedere [LICENSE](../../LICENSE) per i dettagli.