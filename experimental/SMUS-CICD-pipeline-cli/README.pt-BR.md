# SMUS CI/CD Pipeline CLI

**Automatize a implantação de aplicações de dados em ambientes do SageMaker Unified Studio**

Implante DAGs do Airflow, notebooks Jupyter e workflows de ML do desenvolvimento para produção com confiança. Construído para cientistas de dados, engenheiros de dados, engenheiros de ML e desenvolvedores de aplicações GenAI trabalhando com equipes de DevOps.

**Funciona com sua estratégia de implantação:** Seja usando branches git (baseado em branch), artefatos versionados (baseado em bundle), tags git (baseado em tag) ou implantação direta - esta CLI suporta seu workflow. Defina sua aplicação uma vez, implante do seu jeito.

---

## Por que SMUS CI/CD CLI?

✅ **Camada de Abstração AWS** - CLI encapsula toda a complexidade de analytics, ML e SMUS da AWS - equipes de DevOps nunca chamam APIs da AWS diretamente  
✅ **Separação de Responsabilidades** - Equipes de dados definem O QUE implantar (manifest.yaml), equipes de DevOps definem COMO e QUANDO (workflows de CI/CD)  
✅ **Workflows CI/CD Genéricos** - O mesmo workflow funciona para Glue, SageMaker, Bedrock, QuickSight ou qualquer combinação de serviços AWS  
✅ **Implante com Confiança** - Testes automatizados e validação antes da produção  
✅ **Gerenciamento Multi-Ambiente** - Test → Prod com configuração específica por ambiente  
✅ **Infraestrutura como Código** - Manifestos de aplicação versionados e implantações reproduzíveis  
✅ **Workflows Orientados a Eventos** - Acione workflows automaticamente via EventBridge na implantação  

---

## Início Rápido

**Instalar do código fonte:**
```bash
git clone https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker.git
cd Unified-Studio-for-Amazon-Sagemaker/experimental/SMUS-CICD-pipeline-cli
pip install -e .
```

**Implante sua primeira aplicação:**
```bash
# Validar configuração
smus-cli describe --manifest manifest.yaml --connect

# Criar bundle de implantação (opcional)
smus-cli bundle --manifest manifest.yaml

# Implantar no ambiente de teste
smus-cli deploy --targets test --manifest manifest.yaml

# Executar testes de validação
smus-cli test --manifest manifest.yaml --targets test
```

**Veja em ação:** [Exemplo ao Vivo no GitHub Actions](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/actions/runs/17631303500)

---

## Para Quem é Isso?

### 👨‍💻 Equipes de Dados (Cientistas de Dados, Engenheiros de Dados, Desenvolvedores de Apps GenAI)
**Você foca em:** Sua aplicação - o que implantar, onde implantar e como executar  
**Você define:** Manifesto da aplicação (`manifest.yaml`) com seu código, workflows e configurações  
**Você não precisa saber:** Pipelines de CI/CD, GitHub Actions, automação de implantação  

→ **[Guia de Início Rápido](docs/getting-started/quickstart.md)** - Implante sua primeira aplicação em 10 minutos  

**Inclui exemplos para:**
- Engenharia de Dados (Glue, Notebooks, Athena)
- Workflows de ML (SageMaker, Notebooks)
- Aplicações GenAI (Bedrock, Notebooks)

**Bootstrap Actions - Automatize Tarefas Pós-Implantação:**

Defina ações no seu manifesto que executam automaticamente após a implantação:
- Acione workflows imediatamente (sem execução manual necessária)
- Atualize dashboards QuickSight com dados mais recentes
- Provisione conexões MLflow para rastreamento de experimentos
- Busque logs para validação
- Emita eventos para acionar processos downstream

Exemplo:
```yaml
bootstrap:
  actions:
    - type: workflow.run
      workflowName: etl_pipeline
      wait: true
    - type: quicksight.refresh_dataset
      refreshScope: IMPORTED
```

### 🔧 Equipes de DevOps
**Você foca em:** Melhores práticas de CI/CD, segurança, conformidade e automação de implantação  
**Você define:** Templates de workflow que aplicam testes, aprovações e políticas de promoção  
**Você não precisa saber:** Detalhes específicos da aplicação, serviços AWS usados, APIs do DataZone, estruturas de projeto SMUS ou lógica de negócio  

→ **[Guia do Administrador](docs/getting-started/admin-quickstart.md)** - Configure infraestrutura e pipelines em 15 minutos  
→ **[Templates de Workflow GitHub](git-templates/)** - Templates de workflow genéricos e reutilizáveis para implantação automatizada

**A CLI é sua camada de abstração:** Você apenas chama `smus-cli deploy` - a CLI gerencia todas as interações com serviços AWS (DataZone, Glue, Athena, SageMaker, MWAA, S3, IAM, etc.) e executa bootstrap actions (execução de workflows, streaming de logs, atualizações QuickSight, eventos EventBridge). Seus workflows permanecem simples e genéricos.

---
---

## Principais Recursos

### 🚀 Implantação Automatizada
- **Manifesto da Aplicação** - Defina o conteúdo da aplicação, workflows e alvos de implantação em YAML
- **Implantação Flexível** - Modos de implantação baseados em bundle (artefato) ou direto (baseado em git)
- **Implantação Multi-Alvo** - Implante em test e prod com um único comando
- **Variáveis de Ambiente** - Configuração dinâmica usando substituição `${VAR}`
- **Controle de Versão** - Rastreie implantações em S3 ou git para histórico de implantação

### 🔍 Testes e Validação
- **Testes Automatizados** - Execute testes de validação antes de promover para produção
- **Quality Gates** - Bloqueie implantações se os testes falharem
- **Monitoramento de Workflow** - Rastreie status de execução e logs
- **Health Checks** - Verifique a correção da implantação

### 🔄 Integração com Pipeline CI/CD
- **GitHub Actions** - Workflows de pipeline CI/CD pré-construídos para implantação automatizada
- **GitLab CI** - Suporte nativo para pipelines GitLab CI/CD
- **Variáveis de Ambiente** - Configuração flexível para qualquer plataforma CI/CD
- **Suporte a Webhook** - Acione implantações a partir de eventos externos

### 🏗️ Gerenciamento de Infraestrutura
- **Criação de Projeto** - Provisione automaticamente projetos do SageMaker Unified Studio
- **Configuração de Conexão** - Configure conexões S3, Airflow, Athena e Lakehouse
- **Mapeamento de Recursos** - Vincule recursos AWS a conexões de projeto
- **Gerenciamento de Permissões** - Controle acesso e colaboração

### ⚡ Bootstrap Actions
- **Execução Automatizada de Workflow** - Acione workflows automaticamente durante a implantação
- **Recuperação de Logs** - Busque logs de workflow para validação e depuração
- **Atualização de Dataset QuickSight** - Atualize automaticamente dashboards após implantação ETL
- **Integração EventBridge** - Emita eventos customizados para automação downstream e orquestração CI/CD
- **Conexões DataZone** - Provisione conexões MLflow e outros serviços durante a implantação
- **Execução Sequencial** - Ações executam em ordem antes da implantação da aplicação para inicialização confiável

### 📊 Integração com Catálogo
- **Descoberta de Assets** - Encontre automaticamente assets de catálogo necessários (Glue, Lake Formation, DataZone)
- **Gerenciamento de Assinaturas** - Solicite acesso a tabelas e datasets
- **Workflows de Aprovação** - Gerencie acesso a dados entre projetos
- **Rastreamento de Assets** - Monitore dependências de catálogo

---

## O Que Você Pode Implantar?

**📊 Analytics & BI**
- Jobs e crawlers ETL do Glue
- Queries do Athena
- Dashboards QuickSight
- Jobs EMR (futuro)
- Queries Redshift (futuro)

**🤖 Machine Learning**
- Jobs de treinamento SageMaker
- Modelos e endpoints ML
- Experimentos MLflow
- Feature Store (futuro)
- Batch transforms (futuro)

**🧠 Generative AI**
- Agentes Bedrock
- Knowledge bases
- Configurações de modelos de fundação (futuro)

**📓 Código e Workflows**
- Notebooks Jupyter
- Scripts Python
- DAGs Airflow (MWAA e Amazon MWAA Serverless)
- Funções Lambda (futuro)

**💾 Dados e Armazenamento**
- Arquivos de dados S3
- Repositórios Git
- Catálogos de dados (futuro)

---

## Serviços AWS Suportados

Implante workflows usando estes serviços AWS através da sintaxe YAML do Airflow:

### 🎯 Analytics & Dados
**Amazon Athena** • **AWS Glue** • **Amazon EMR** • **Amazon Redshift** • **Amazon QuickSight** • **Lake Formation**

### 🤖 Machine Learning  
**SageMaker Training** • **SageMaker Pipelines** • **Feature Store** • **Model Registry** • **Batch Transform**

### 🧠 Generative AI
**Amazon Bedrock** • **Bedrock Agents** • **Bedrock Knowledge Bases** • **Guardrails**

### 📊 Serviços Adicionais
S3 • Lambda • Step Functions • DynamoDB • RDS • SNS/SQS • Batch

**Veja lista completa:** [Referência de Operadores AWS do Airflow](docs/airflow-aws-operators.md)

---

## Conceitos Principais

### Separação de Responsabilidades: O Princípio de Design Chave

**O Problema:** Abordagens tradicionais de implantação forçam equipes de DevOps a aprender serviços de analytics AWS (Glue, Athena, DataZone, SageMaker, MWAA, etc.) e entender estruturas de projeto SMUS, ou forçam equipes de dados a se tornarem especialistas em CI/CD.

**A Solução:** SMUS CLI é a camada de abstração que encapsula toda a complexidade AWS e SMUS:

```
Equipes de Dados              SMUS CLI                    Equipes de DevOps
    ↓                            ↓                              ↓
manifest.yaml          smus-cli deploy                  GitHub Actions
(O QUE & ONDE)         (ABSTRAÇÃO AWS)                  (COMO & QUANDO)
```

**Equipes de dados focam em:**
- Código da aplicação e workflows
- Quais serviços AWS usar (Glue, Athena, SageMaker, etc.)
- Configurações de ambiente
- Lógica de negócio

**SMUS CLI gerencia TODA a complexidade AWS:**
- Gerenciamento de domínio e projeto DataZone
- APIs AWS Glue, Athena, SageMaker, MWAA
- Gerenciamento de armazenamento e artefatos S3
- Roles e permissões IAM
- Configurações de conexão
- Assinaturas de assets de catálogo
- Implantação de workflow no Airflow
- Provisionamento de infraestrutura
- Testes e validação

**Equipes de DevOps focam em:**
- Melhores práticas de CI/CD (testes, aprovações, notificações)
- Gates de segurança e conformidade
- Orquestração de implantação
- Monitoramento e alertas

**Resultado:** 
- Equipes de dados nunca tocam em configs de CI/CD
- **Equipes de DevOps nunca chamam APIs AWS diretamente** - apenas chamam `smus-cli deploy`
- **Workflows CI/CD são genéricos** - o mesmo workflow funciona para apps Glue, SageMaker ou Bedrock
- Ambas as equipes trabalham independentemente usando sua expertise

---

### Manifesto da Aplicação
Um arquivo YAML declarativo (`manifest.yaml`) que define sua aplicação de dados:
- **Detalhes da aplicação** - Nome, versão, descrição
- **Conteúdo** - Código de repositórios git, dados/modelos de armazenamento, dashboards QuickSight
- **Workflows** - DAGs Airflow para orquestração e automação
- **Stages** - Onde implantar (ambientes dev, test, prod)
- **Configuração** - Configurações específicas por ambiente, conexões e ações de bootstrap

**Criado e mantido por equipes de dados.** Define **o que** implantar e **onde**. Não requer conhecimento de CI/CD.

### Aplicação
Sua carga de trabalho de dados/analytics sendo implantada:
- DAGs Airflow e scripts Python
- Notebooks Jupyter e arquivos de dados
- Modelos ML e código de treinamento
- Pipelines ETL e transformações
- Agentes GenAI e servidores MCP
- Configurações de modelos de fundação

### Stage
Um ambiente de implantação (dev, test, prod) mapeado para um projeto do SageMaker Unified Studio:
- Configuração de domínio e região
- Nome e configurações do projeto
- Conexões de recursos (S3, Airflow, Athena, Glue)
- Parâmetros específicos do ambiente
- Mapeamento opcional de branch para implantações baseadas em git

### Workflow
Lógica de orquestração que executa sua aplicação. Workflows servem dois propósitos:

**1. Tempo de implantação:** Criar recursos AWS necessários durante a implantação
- Provisionar infraestrutura (buckets S3, databases, roles IAM)
- Configurar conexões e permissões
- Configurar monitoramento e logging

**2. Runtime:** Executar pipelines contínuos de dados e ML
- Execução agendada (diária, horária, etc.)
- Triggers orientados a eventos (uploads S3, chamadas API)
- Processamento e transformações de dados
- Treinamento e inferência de modelos

Workflows são definidos como DAGs Airflow (Directed Acyclic Graphs) em formato YAML. Suporta [MWAA (Managed Workflows for Apache Airflow)](https://aws.amazon.com/managed-workflows-for-apache-airflow/) e [Amazon MWAA Serverless](https://aws.amazon.com/blogs/big-data/introducing-amazon-mwaa-serverless/) ([Guia do Usuário](https://docs.aws.amazon.com/mwaa/latest/mwaa-serverless-userguide/what-is-mwaa-serverless.html)).

### Automação CI/CD
Workflows do GitHub Actions (ou outros sistemas CI/CD) que automatizam a implantação:
- **Criado e mantido por equipes de DevOps**
- Define **como** e **quando** implantar
- Executa testes e quality gates
- Gerencia promoção entre targets
- Aplica políticas de segurança e conformidade
- Exemplo: `.github/workflows/deploy.yml`

**Insight chave:** Equipes de DevOps criam workflows genéricos e reutilizáveis que funcionam para QUALQUER aplicação. Eles não precisam saber se o app usa Glue, SageMaker ou Bedrock - a CLI gerencia todas as interações com serviços AWS. O workflow apenas chama `smus-cli deploy` e a CLI faz o resto.

### Modos de Implantação

**Baseado em Bundle (Artefato):** Criar arquivo versionado → implantar arquivo nos stages
- Bom para: trilhas de auditoria, capacidade de rollback, conformidade
- Comando: `smus-cli bundle` depois `smus-cli deploy --manifest app.tar.gz`

**Direto (Baseado em Git):** Implantar diretamente das fontes sem artefatos intermediários
- Bom para: workflows mais simples, iteração rápida, git como fonte da verdade
- Comando: `smus-cli deploy --manifest manifest.yaml --stage test`

Ambos os modos funcionam com qualquer combinação de fontes de conteúdo de armazenamento e git.

---

### Como Tudo Funciona Junto

```
1. Equipe de Dados               2. Equipe de DevOps            3. SMUS CLI (A Abstração)
   ↓                                ↓                              ↓
Cria manifest.yaml             Cria workflow genérico         Workflow chama:
- Jobs Glue                    - Teste no merge               smus-cli deploy --manifest manifest.yaml
- Treinamento SageMaker        - Aprovação para prod            ↓
- Queries Athena               - Scans de segurança           CLI gerencia TODA complexidade AWS:
- Localizações S3              - Regras de notificação        - APIs DataZone
                                                              - APIs Glue/Athena/SageMaker
                               Funciona para QUALQUER app!    - Implantação MWAA
                               Sem conhecimento AWS!          - Gerenciamento S3
                                                              - Configuração IAM
                                                              - Provisionamento de infraestrutura
                                                                ↓
                                                              Sucesso!
```

**A beleza:** 
- Equipes de dados nunca aprendem GitHub Actions
- **Equipes de DevOps nunca chamam APIs AWS** - a CLI encapsula toda a complexidade de analytics, ML e SMUS da AWS
- Workflows CI/CD são simples: apenas chame `smus-cli deploy`
- O mesmo workflow funciona para QUALQUER aplicação, independente dos serviços AWS usados

---

## Aplicações de Exemplo

Exemplos do mundo real mostrando como implantar diferentes tipos de cargas de trabalho com SMUS CI/CD.

### 📊 Analytics - Dashboard QuickSight
Implante dashboards BI interativos com pipelines ETL Glue automatizados para preparação de dados. Usa asset bundles QuickSight, queries Athena e integração com dataset GitHub com configurações específicas por ambiente.

**Serviços AWS:** QuickSight • Glue • Athena • S3 • MWAA Serverless

**O que acontece durante a implantação:** Código da aplicação é implantado no S3, jobs Glue e workflows Airflow são criados e executados, dashboard/data source/dataset QuickSight são criados, e ingestão QuickSight é iniciada para atualizar o dashboard com dados mais recentes.

<details>
<summary><b>Ver Manifesto</b></summary>

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

**[Ver Exemplo Completo →](docs/examples-guide.md#-analytics---quicksight-dashboard)**

---

### 📓 Engenharia de Dados - Notebooks
Implante notebooks Jupyter com orquestração de execução paralela para análise de dados e workflows ETL. Demonstra implantação de notebooks com integração MLflow para rastreamento de experimentos.

**Serviços AWS:** SageMaker Notebooks • MLflow • S3 • MWAA Serverless

**O que acontece durante a implantação:** Notebooks e definições de workflow são enviados para S3, DAG Airflow é criado para execução paralela de notebooks, conexão MLflow é provisionada para rastreamento de experimentos, e notebooks estão prontos para executar sob demanda ou agendados.

<details>
<summary><b>Ver Manifesto</b></summary>

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

**[Ver Exemplo Completo →](docs/examples-guide.md#-data-engineering---notebooks)**

---

### 🤖 Machine Learning - Treinamento
Treine modelos ML com SageMaker usando o [SageMaker SDK](https://sagemaker.readthedocs.io/) e imagens [SageMaker Distribution](https://github.com/aws/sagemaker-distribution/tree/main/src). Rastreie experimentos com MLflow e automatize pipelines de treinamento com configurações específicas por ambiente.

**Serviços AWS:** SageMaker Training • MLflow • S3 • MWAA Serverless

**O que acontece durante a implantação:** Código de treinamento e definições de workflow são enviados para S3 com compressão, DAG Airflow é criado para orquestração de treinamento, conexão MLflow é provisionada para rastreamento de experimentos, e jobs de treinamento SageMaker são criados e executados usando imagens SageMaker Distribution.

<details>
<summary><b>Ver Manifesto</b></summary>

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

**[Ver Exemplo Completo →](docs/examples-guide.md#-machine-learning---training)**

---

### 🤖 Machine Learning - Implantação
Implante modelos ML treinados como endpoints de inferência em tempo real do SageMaker. Usa SageMaker SDK para configuração de endpoint e imagens [SageMaker Distribution](https://github.com/aws/sagemaker-distribution/tree/main/src) para serving.

**Serviços AWS:** SageMaker Endpoints • S3 • MWAA Serverless

**O que acontece durante a implantação:** Artefatos de modelo, código de implantação e definições de workflow são enviados para S3, DAG Airflow é criado para orquestração de implantação de endpoint, configuração e modelo de endpoint SageMaker são criados, e o endpoint de inferência é implantado e pronto para servir previsões.

<details>
<summary><b>Ver Manifesto</b></summary>

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

**[Ver Exemplo Completo →](docs/examples-guide.md#-machine-learning---deployment)**

---

### 🧠 Generative AI
Implante aplicações GenAI com agentes e knowledge bases Bedrock. Demonstra workflows RAG (Retrieval Augmented Generation) com implantação automatizada de agentes e testes.

**Serviços AWS:** Amazon Bedrock • S3 • MWAA Serverless

**O que acontece durante a implantação:** Configuração de agente e definições de workflow são enviadas para S3, DAG Airflow é criado para orquestração de implantação de agente, agentes e knowledge bases Bedrock são configurados, e a aplicação GenAI está pronta para inferência e testes.

<details>
<summary><b>Ver Manifesto</b></summary>

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

**[Ver Exemplo Completo →](docs/examples-guide.md#-generative-ai)**

---

**[Ver Todos os Exemplos com Passo a Passo Detalhado →](docs/examples-guide.md)**

---

## Por que SMUS CI/CD CLI?

✅ **Camada de Abstração AWS** - CLI encapsula toda a complexidade de analytics, ML e SMUS da AWS - equipes de DevOps nunca chamam APIs da AWS diretamente  
✅ **Separação de Responsabilidades** - Equipes de dados definem O QUE implantar (manifest.yaml), equipes de DevOps definem COMO e QUANDO (workflows de CI/CD)  
✅ **Workflows CI/CD Genéricos** - O mesmo workflow funciona para Glue, SageMaker, Bedrock, QuickSight ou qualquer combinação de serviços AWS  
✅ **Implante com Confiança** - Testes automatizados e validação antes da produção  
✅ **Gerenciamento Multi-Ambiente** - Test → Prod com configuração específica por ambiente  
✅ **Infraestrutura como Código** - Manifestos de aplicação versionados e implantações reproduzíveis  
✅ **Workflows Orientados a Eventos** - Acione workflows automaticamente via EventBridge na implantação  

---

## Início Rápido

**Instalar do código fonte:**
```bash
git clone https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker.git
cd Unified-Studio-for-Amazon-Sagemaker/experimental/SMUS-CICD-pipeline-cli
pip install -e .
```

**Implante sua primeira aplicação:**
```bash
# Validar configuração
smus-cli describe --manifest manifest.yaml --connect

# Criar bundle de implantação (opcional)
smus-cli bundle --manifest manifest.yaml

# Implantar no ambiente de teste
smus-cli deploy --targets test --manifest manifest.yaml

# Executar testes de validação
smus-cli test --manifest manifest.yaml --targets test
```

**Veja em ação:** [Exemplo ao Vivo no GitHub Actions](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/actions/runs/17631303500)

---

## Para Quem é Isso?

### 👨‍💻 Equipes de Dados (Cientistas de Dados, Engenheiros de Dados, Desenvolvedores de Apps GenAI)
**Você foca em:** Sua aplicação - o que implantar, onde implantar e como executar  
**Você define:** Manifesto da aplicação (`manifest.yaml`) com seu código, workflows e configurações  
**Você não precisa saber:** Pipelines de CI/CD, GitHub Actions, automação de implantação  

→ **[Guia de Início Rápido](docs/getting-started/quickstart.md)** - Implante sua primeira aplicação em 10 minutos  

**Inclui exemplos para:**
- Engenharia de Dados (Glue, Notebooks, Athena)
- Workflows de ML (SageMaker, Notebooks)
- Aplicações GenAI (Bedrock, Notebooks)

**Bootstrap Actions - Automatize Tarefas Pós-Implantação:**

Defina ações no seu manifesto que executam automaticamente após a implantação:
- Acione workflows imediatamente (sem execução manual necessária)
- Atualize dashboards QuickSight com dados mais recentes
- Provisione conexões MLflow para rastreamento de experimentos
- Busque logs para validação
- Emita eventos para acionar processos downstream

Exemplo:
```yaml
bootstrap:
  actions:
    - type: workflow.run
      workflowName: etl_pipeline
      wait: true
    - type: quicksight.refresh_dataset
      refreshScope: IMPORTED
```

### 🔧 Equipes de DevOps
**Você foca em:** Melhores práticas de CI/CD, segurança, conformidade e automação de implantação  
**Você define:** Templates de workflow que aplicam testes, aprovações e políticas de promoção  
**Você não precisa saber:** Detalhes específicos da aplicação, serviços AWS usados, APIs do DataZone, estruturas de projeto SMUS ou lógica de negócio  

→ **[Guia do Administrador](docs/getting-started/admin-quickstart.md)** - Configure infraestrutura e pipelines em 15 minutos  
→ **[Templates de Workflow GitHub](git-templates/)** - Templates de workflow genéricos e reutilizáveis para implantação automatizada

**A CLI é sua camada de abstração:** Você apenas chama `smus-cli deploy` - a CLI gerencia todas as interações com serviços AWS (DataZone, Glue, Athena, SageMaker, MWAA, S3, IAM, etc.) e executa bootstrap actions (execução de workflows, streaming de logs, atualizações QuickSight, eventos EventBridge). Seus workflows permanecem simples e genéricos.

---
---

## Principais Recursos

### 🚀 Implantação Automatizada
- **Manifesto da Aplicação** - Defina o conteúdo da aplicação, workflows e alvos de implantação em YAML
- **Implantação Flexível** - Modos de implantação baseados em bundle (artefato) ou direto (baseado em git)
- **Implantação Multi-Alvo** - Implante em test e prod com um único comando
- **Variáveis de Ambiente** - Configuração dinâmica usando substituição `${VAR}`
- **Controle de Versão** - Rastreie implantações em S3 ou git para histórico de implantação

### 🔍 Testes e Validação
- **Testes Automatizados** - Execute testes de validação antes de promover para produção
- **Quality Gates** - Bloqueie implantações se os testes falharem
- **Monitoramento de Workflow** - Rastreie status de execução e logs
- **Health Checks** - Verifique a correção da implantação

### 🔄 Integração com Pipeline CI/CD
- **GitHub Actions** - Workflows de pipeline CI/CD pré-construídos para implantação automatizada
- **GitLab CI** - Suporte nativo para pipelines GitLab CI/CD
- **Variáveis de Ambiente** - Configuração flexível para qualquer plataforma CI/CD
- **Suporte a Webhook** - Acione implantações a partir de eventos externos

### 🏗️ Gerenciamento de Infraestrutura
- **Criação de Projeto** - Provisione automaticamente projetos do SageMaker Unified Studio
- **Configuração de Conexão** - Configure conexões S3, Airflow, Athena e Lakehouse
- **Mapeamento de Recursos** - Vincule recursos AWS a conexões de projeto
- **Gerenciamento de Permissões** - Controle acesso e colaboração

### ⚡ Bootstrap Actions
- **Execução Automatizada de Workflow** - Acione workflows automaticamente durante a implantação
- **Recuperação de Logs** - Busque logs de workflow para validação e depuração
- **Atualização de Dataset QuickSight** - Atualize automaticamente dashboards após implantação ETL
- **Integração EventBridge** - Emita eventos customizados para automação downstream e orquestração CI/CD
- **Conexões DataZone** - Provisione conexões MLflow e outros serviços durante a implantação
- **Execução Sequencial** - Ações executam em ordem antes da implantação da aplicação para inicialização confiável

### 📊 Integração com Catálogo
- **Descoberta de Assets** - Encontre automaticamente assets de catálogo necessários (Glue, Lake Formation, DataZone)
- **Gerenciamento de Assinaturas** - Solicite acesso a tabelas e datasets
- **Workflows de Aprovação** - Gerencie acesso a dados entre projetos
- **Rastreamento de Assets** - Monitore dependências de catálogo

---

## O Que Você Pode Implantar?

**📊 Analytics & BI**
- Jobs e crawlers ETL do Glue
- Queries do Athena
- Dashboards QuickSight
- Jobs EMR (futuro)
- Queries Redshift (futuro)

**🤖 Machine Learning**
- Jobs de treinamento SageMaker
- Modelos e endpoints ML
- Experimentos MLflow
- Feature Store (futuro)
- Batch transforms (futuro)

**🧠 Generative AI**
- Agentes Bedrock
- Knowledge bases
- Configurações de modelos de fundação (futuro)

**📓 Código e Workflows**
- Notebooks Jupyter
- Scripts Python
- DAGs Airflow (MWAA e Amazon MWAA Serverless)
- Funções Lambda (futuro)

**💾 Dados e Armazenamento**
- Arquivos de dados S3
- Repositórios Git
- Catálogos de dados (futuro)

---

## Serviços AWS Suportados

Implante workflows usando estes serviços AWS através da sintaxe YAML do Airflow:

### 🎯 Analytics & Dados
**Amazon Athena** • **AWS Glue** • **Amazon EMR** • **Amazon Redshift** • **Amazon QuickSight** • **Lake Formation**

### 🤖 Machine Learning  
**SageMaker Training** • **SageMaker Pipelines** • **Feature Store** • **Model Registry** • **Batch Transform**

### 🧠 Generative AI
**Amazon Bedrock** • **Bedrock Agents** • **Bedrock Knowledge Bases** • **Guardrails**

### 📊 Serviços Adicionais
S3 • Lambda • Step Functions • DynamoDB • RDS • SNS/SQS • Batch

**Veja lista completa:** [Referência de Operadores AWS do Airflow](docs/airflow-aws-operators.md)

---

## Conceitos Principais

### Separação de Responsabilidades: O Princípio de Design Chave

**O Problema:** Abordagens tradicionais de implantação forçam equipes de DevOps a aprender serviços de analytics AWS (Glue, Athena, DataZone, SageMaker, MWAA, etc.) e entender estruturas de projeto SMUS, ou forçam equipes de dados a se tornarem especialistas em CI/CD.

**A Solução:** SMUS CLI é a camada de abstração que encapsula toda a complexidade AWS e SMUS:

```
Equipes de Dados              SMUS CLI                    Equipes de DevOps
    ↓                            ↓                              ↓
manifest.yaml          smus-cli deploy                  GitHub Actions
(O QUE & ONDE)         (ABSTRAÇÃO AWS)                  (COMO & QUANDO)
```

**Equipes de dados focam em:**
- Código da aplicação e workflows
- Quais serviços AWS usar (Glue, Athena, SageMaker, etc.)
- Configurações de ambiente
- Lógica de negócio

**SMUS CLI gerencia TODA a complexidade AWS:**
- Gerenciamento de domínio e projeto DataZone
- APIs AWS Glue, Athena, SageMaker, MWAA
- Gerenciamento de armazenamento e artefatos S3
- Roles e permissões IAM
- Configurações de conexão
- Assinaturas de assets de catálogo
- Implantação de workflow no Airflow
- Provisionamento de infraestrutura
- Testes e validação

**Equipes de DevOps focam em:**
- Melhores práticas de CI/CD (testes, aprovações, notificações)
- Gates de segurança e conformidade
- Orquestração de implantação
- Monitoramento e alertas

**Resultado:** 
- Equipes de dados nunca tocam em configs de CI/CD
- **Equipes de DevOps nunca chamam APIs AWS diretamente** - apenas chamam `smus-cli deploy`
- **Workflows CI/CD são genéricos** - o mesmo workflow funciona para apps Glue, SageMaker ou Bedrock
- Ambas as equipes trabalham independentemente usando sua expertise

---

### Manifesto da Aplicação
Um arquivo YAML declarativo (`manifest.yaml`) que define sua aplicação de dados:
- **Detalhes da aplicação** - Nome, versão, descrição
- **Conteúdo** - Código de repositórios git, dados/modelos de armazenamento, dashboards QuickSight
- **Workflows** - DAGs Airflow para orquestração e automação
- **Stages** - Onde implantar (ambientes dev, test, prod)
- **Configuração** - Configurações específicas por ambiente, conexões e ações de bootstrap

**Criado e mantido por equipes de dados.** Define **o que** implantar e **onde**. Não requer conhecimento de CI/CD.

### Aplicação
Sua carga de trabalho de dados/analytics sendo implantada:
- DAGs Airflow e scripts Python
- Notebooks Jupyter e arquivos de dados
- Modelos ML e código de treinamento
- Pipelines ETL e transformações
- Agentes GenAI e servidores MCP
- Configurações de modelos de fundação

### Stage
Um ambiente de implantação (dev, test, prod) mapeado para um projeto do SageMaker Unified Studio:
- Configuração de domínio e região
- Nome e configurações do projeto
- Conexões de recursos (S3, Airflow, Athena, Glue)
- Parâmetros específicos do ambiente
- Mapeamento opcional de branch para implantações baseadas em git

### Workflow
Lógica de orquestração que executa sua aplicação. Workflows servem dois propósitos:

**1. Tempo de implantação:** Criar recursos AWS necessários durante a implantação
- Provisionar infraestrutura (buckets S3, databases, roles IAM)
- Configurar conexões e permissões
- Configurar monitoramento e logging

**2. Runtime:** Executar pipelines contínuos de dados e ML
- Execução agendada (diária, horária, etc.)
- Triggers orientados a eventos (uploads S3, chamadas API)
- Processamento e transformações de dados
- Treinamento e inferência de modelos

Workflows são definidos como DAGs Airflow (Directed Acyclic Graphs) em formato YAML. Suporta [MWAA (Managed Workflows for Apache Airflow)](https://aws.amazon.com/managed-workflows-for-apache-airflow/) e [Amazon MWAA Serverless](https://aws.amazon.com/blogs/big-data/introducing-amazon-mwaa-serverless/) ([Guia do Usuário](https://docs.aws.amazon.com/mwaa/latest/mwaa-serverless-userguide/what-is-mwaa-serverless.html)).

### Automação CI/CD
Workflows do GitHub Actions (ou outros sistemas CI/CD) que automatizam a implantação:
- **Criado e mantido por equipes de DevOps**
- Define **como** e **quando** implantar
- Executa testes e quality gates
- Gerencia promoção entre targets
- Aplica políticas de segurança e conformidade
- Exemplo: `.github/workflows/deploy.yml`

**Insight chave:** Equipes de DevOps criam workflows genéricos e reutilizáveis que funcionam para QUALQUER aplicação. Eles não precisam saber se o app usa Glue, SageMaker ou Bedrock - a CLI gerencia todas as interações com serviços AWS. O workflow apenas chama `smus-cli deploy` e a CLI faz o resto.

### Modos de Implantação

**Baseado em Bundle (Artefato):** Criar arquivo versionado → implantar arquivo nos stages
- Bom para: trilhas de auditoria, capacidade de rollback, conformidade
- Comando: `smus-cli bundle` depois `smus-cli deploy --manifest app.tar.gz`

**Direto (Baseado em Git):** Implantar diretamente das fontes sem artefatos intermediários
- Bom para: workflows mais simples, iteração rápida, git como fonte da verdade
- Comando: `smus-cli deploy --manifest manifest.yaml --stage test`

Ambos os modos funcionam com qualquer combinação de fontes de conteúdo de armazenamento e git.

---

### Como Tudo Funciona Junto

```
1. Equipe de Dados               2. Equipe de DevOps            3. SMUS CLI (A Abstração)
   ↓                                ↓                              ↓
Cria manifest.yaml             Cria workflow genérico         Workflow chama:
- Jobs Glue                    - Teste no merge               smus-cli deploy --manifest manifest.yaml
- Treinamento SageMaker        - Aprovação para prod            ↓
- Queries Athena               - Scans de segurança           CLI gerencia TODA complexidade AWS:
- Localizações S3              - Regras de notificação        - APIs DataZone
                                                              - APIs Glue/Athena/SageMaker
                               Funciona para QUALQUER app!    - Implantação MWAA
                               Sem conhecimento AWS!          - Gerenciamento S3
                                                              - Configuração IAM
                                                              - Provisionamento de infraestrutura
                                                                ↓
                                                              Sucesso!
```

**A beleza:** 
- Equipes de dados nunca aprendem GitHub Actions
- **Equipes de DevOps nunca chamam APIs AWS** - a CLI encapsula toda a complexidade de analytics, ML e SMUS da AWS
- Workflows CI/CD são simples: apenas chame `smus-cli deploy`
- O mesmo workflow funciona para QUALQUER aplicação, independente dos serviços AWS usados

---

## Aplicações de Exemplo

Exemplos do mundo real mostrando como implantar diferentes tipos de cargas de trabalho com SMUS CI/CD.

### 📊 Analytics - Dashboard QuickSight
Implante dashboards BI interativos com pipelines ETL Glue automatizados para preparação de dados. Usa asset bundles QuickSight, queries Athena e integração com dataset GitHub com configurações específicas por ambiente.

**Serviços AWS:** QuickSight • Glue • Athena • S3 • MWAA Serverless

**O que acontece durante a implantação:** Código da aplicação é implantado no S3, jobs Glue e workflows Airflow são criados e executados, dashboard/data source/dataset QuickSight são criados, e ingestão QuickSight é iniciada para atualizar o dashboard com dados mais recentes.

**[Ver Exemplo Completo →](docs/examples-guide.md#-analytics---quicksight-dashboard)**

---

### 📓 Engenharia de Dados - Notebooks
Implante notebooks Jupyter com orquestração de execução paralela para análise de dados e workflows ETL. Demonstra implantação de notebooks com integração MLflow para rastreamento de experimentos.

**Serviços AWS:** SageMaker Notebooks • MLflow • S3 • MWAA Serverless

**O que acontece durante a implantação:** Notebooks e definições de workflow são enviados para S3, DAG Airflow é criado para execução paralela de notebooks, conexão MLflow é provisionada para rastreamento de experimentos, e notebooks estão prontos para executar sob demanda ou agendados.

**[Ver Exemplo Completo →](docs/examples-guide.md#-data-engineering---notebooks)**

---

### 🤖 Machine Learning - Treinamento
Treine modelos ML com SageMaker usando o [SageMaker SDK](https://sagemaker.readthedocs.io/) e imagens [SageMaker Distribution](https://github.com/aws/sagemaker-distribution/tree/main/src). Rastreie experimentos com MLflow e automatize pipelines de treinamento com configurações específicas por ambiente.

**Serviços AWS:** SageMaker Training • MLflow • S3 • MWAA Serverless

**O que acontece durante a implantação:** Código de treinamento e definições de workflow são enviados para S3 com compressão, DAG Airflow é criado para orquestração de treinamento, conexão MLflow é provisionada para rastreamento de experimentos, e jobs de treinamento SageMaker são criados e executados usando imagens SageMaker Distribution.

**[Ver Exemplo Completo →](docs/examples-guide.md#-machine-learning---training)**

---

### 🤖 Machine Learning - Implantação
Implante modelos ML treinados como endpoints de inferência em tempo real do SageMaker. Usa SageMaker SDK para configuração de endpoint e imagens [SageMaker Distribution](https://github.com/aws/sagemaker-distribution/tree/main/src) para serving.

**Serviços AWS:** SageMaker Endpoints • S3 • MWAA Serverless

**O que acontece durante a implantação:** Artefatos de modelo, código de implantação e definições de workflow são enviados para S3, DAG Airflow é criado para orquestração de implantação de endpoint, configuração e modelo de endpoint SageMaker são criados, e o endpoint de inferência é implantado e pronto para servir previsões.

**[Ver Exemplo Completo →](docs/examples-guide.md#-machine-learning---deployment)**

---

### 🧠 Generative AI
Implante aplicações GenAI com agentes e knowledge bases Bedrock. Demonstra workflows RAG (Retrieval Augmented Generation) com implantação automatizada de agentes e testes.

**Serviços AWS:** Amazon Bedrock • S3 • MWAA Serverless

**O que acontece durante a implantação:** Configuração de agente e definições de workflow são enviadas para S3, DAG Airflow é criado para orquestração de implantação de agente, agentes e knowledge bases Bedrock são configurados, e a aplicação GenAI está pronta para inferência e testes.

**[Ver Exemplo Completo →](docs/examples-guide.md#-generative-ai)**

---

**[Ver Todos os Exemplos com Passo a Passo Detalhado →](docs/examples-guide.md)**

---

<details>
<summary><h2>📋 Lista de Recursos</h2></summary>

**Legenda:** ✅ Suportado | 🔄 Planejado | 🔮 Futuro

### Infraestrutura Principal
| Recurso | Status | Notas |
|---------|--------|-------|
| Configuração YAML | ✅ | [Guia do Manifesto](docs/manifest.md) |
| Infraestrutura como Código | ✅ | [Comando Deploy](docs/cli-commands.md#deploy) |
| Implantação multi-ambiente | ✅ | [Stages](docs/manifest-schema.md#stages) |
| Ferramenta CLI | ✅ | [Comandos CLI](docs/cli-commands.md) |
| Integração com controle de versão | ✅ | [GitHub Actions](docs/github-actions-integration.md) |

### Implantação e Bundling
| Recurso | Status | Notas |
|---------|--------|-------|
| Bundling de artefatos | ✅ | [Comando Bundle](docs/cli-commands.md#bundle) |
| Implantação baseada em bundle | ✅ | [Comando Deploy](docs/cli-commands.md#deploy) |
| Implantação direta | ✅ | [Comando Deploy](docs/cli-commands.md#deploy) |
| Validação de implantação | ✅ | [Comando Describe](docs/cli-commands.md#describe) |
| Implantação incremental | 🔄 | Upload apenas de arquivos alterados |
| Suporte a rollback | 🔮 | Rollback automatizado |
| Implantação blue-green | 🔮 | Implantações sem downtime |

### Experiência do Desenvolvedor
| Recurso | Status | Notas |
|---------|--------|-------|
| Templates de projeto | 🔄 | `smus-cli init` com templates |
| Inicialização de manifesto | ✅ | [Comando Create](docs/cli-commands.md#create) |
| Configuração interativa | 🔄 | Prompts de configuração guiada |
| Desenvolvimento local | ✅ | [Comandos CLI](docs/cli-commands.md) |
| Extensão VS Code | 🔮 | IntelliSense e validação |

### Configuração
| Recurso | Status | Notas |
|---------|--------|-------|
| Substituição de variáveis | ✅ | [Guia de Substituições](docs/substitutions-and-variables.md) |
| Configuração específica por ambiente | ✅ | [Stages](docs/manifest-schema.md#stages) |
| Gerenciamento de secrets | 🔮 | Integração AWS Secrets Manager |
| Validação de configuração | ✅ | [Schema do Manifesto](docs/manifest-schema.md) |
| Gerenciamento de conexões | ✅ | [Guia de Conexões](docs/connections.md) |

### Recursos e Cargas de Trabalho
| Recurso | Status | Notas |
|---------|--------|-------|
| DAGs Airflow | ✅ | [Workflows](docs/manifest-schema.md#workflows) |
| Notebooks Jupyter | ✅ | [SageMakerNotebookOperator](docs/airflow-aws-operators.md#amazon-sagemaker) |
| Jobs ETL Glue | ✅ | [GlueJobOperator](docs/airflow-aws-operators.md#aws-glue) |
| Queries Athena | ✅ | [AthenaOperator](docs/airflow-aws-operators.md#amazon-athena) |
| Treinamento SageMaker | ✅ | [SageMakerTrainingOperator](docs/airflow-aws-operators.md#amazon-sagemaker) |
| Endpoints SageMaker | ✅ | [SageMakerEndpointOperator](docs/airflow-aws-operators.md#amazon-sagemaker) |
| Dashboards QuickSight | ✅ | [Implantação QuickSight](docs/quicksight-deployment.md) |
| Agentes Bedrock | ✅ | [BedrockInvokeModelOperator](docs/airflow-aws-operators.md#amazon-bedrock) |
| Funções Lambda | 🔄 | [LambdaInvokeFunctionOperator](docs/airflow-aws-operators.md#aws-lambda) |
| Jobs EMR | ✅ | [EmrAddStepsOperator](docs/airflow-aws-operators.md#amazon-emr) |
| Queries Redshift | ✅ | [RedshiftDataOperator](docs/airflow-aws-operators.md#amazon-redshift) |

### Bootstrap Actions
| Recurso | Status | Notas |
|---------|--------|-------|
| Execução de workflow | ✅ | [workflow.run](docs/bootstrap-actions.md#workflowrun---trigger-workflow-execution) |
| Recuperação de logs | ✅ | [workflow.logs](docs/bootstrap-actions.md#workflowlogs---fetch-workflow-logs) |
| Atualização QuickSight | ✅ | [quicksight.refresh_dataset](docs/bootstrap-actions.md#quicksightrefresh_dataset---trigger-dataset-ingestion) |
| Eventos EventBridge | ✅ | [eventbridge.put_events](docs/bootstrap-actions.md#customput_events---emit-custom-events) |
| Conexões DataZone | ✅ | [datazone.create_connection](docs/bootstrap-actions.md) |
| Execução sequencial | ✅ | [Fluxo de Execução](docs/bootstrap-actions.md#execution-flow) |

### Integração CI/CD
| Recurso | Status | Notas |
|---------|--------|-------|
| GitHub Actions | ✅ | [Guia GitHub Actions](docs/github-actions-integration.md) |
| GitLab CI | ✅ | [Comandos CLI](docs/cli-commands.md) |
| Azure DevOps | ✅ | [Comandos CLI](docs/cli-commands.md) |
| Jenkins | ✅ | [Comandos CLI](docs/cli-commands.md) |
| Service principals | ✅ | [Guia GitHub Actions](docs/github-actions-integration.md) |
| Federação OIDC | ✅ | [Guia GitHub Actions](docs/github-actions-integration.md) |

### Testes e Validação
| Recurso | Status | Notas |
|---------|--------|-------|
| Testes unitários | ✅ | [Comando Test](docs/cli-commands.md#test) |
| Testes de integração | ✅ | [Comando Test](docs/cli-commands.md#test) |
| Testes automatizados | ✅ | [Comando Test](docs/cli-commands.md#test) |
| Quality gates | ✅ | [Comando Test](docs/cli-commands.md#test) |
| Monitoramento de workflow | ✅ | [Comando Monitor](docs/cli-commands.md#monitor) |

### Monitoramento e Observabilidade
| Recurso | Status | Notas |
|---------|--------|-------|
| Monitoramento de implantação | ✅ | [Comando Deploy](docs/cli-commands.md#deploy) |
| Monitoramento de workflow | ✅ | [Comando Monitor](docs/cli-commands.md#monitor) |
| Alertas customizados | ✅ | [Métricas de Implantação](docs/pipeline-deployment-metrics.md) |
| Coleta de métricas | ✅ | [Métricas de Implantação](docs/pipeline-deployment-metrics.md) |
| Histórico de implantação | ✅ | [Comando Bundle](docs/cli-commands.md#bundle) |

### Integração com Serviços AWS
| Recurso | Status | Notas |
|---------|--------|-------|
| Amazon MWAA | ✅ | [Workflows](docs/manifest-schema.md#workflows) |
| MWAA Serverless | ✅ | [Workflows](docs/manifest-schema.md#workflows) |
| AWS Glue | ✅ | [Operadores Airflow](docs/airflow-aws-operators.md#aws-glue) |
| Amazon Athena | ✅ | [Operadores Airflow](docs/airflow-aws-operators.md#amazon-athena) |
| SageMaker | ✅ | [Operadores Airflow](docs/airflow-aws-operators.md#amazon-sagemaker) |
| Amazon Bedrock | ✅ | [Operadores Airflow](docs/airflow-aws-operators.md#amazon-bedrock) |
| Amazon QuickSight | ✅ | [Implantação QuickSight](docs/quicksight-deployment.md) |
| DataZone | ✅ | [Schema do Manifesto](docs/manifest-schema.md) |
| EventBridge | ✅ | [Métricas de Implantação](docs/pipeline-deployment-metrics.md) |
| Lake Formation | ✅ | [Guia de Conexões](docs/connections.md) |
| Amazon S3 | ✅ | [Storage](docs/manifest-schema.md#storage) |
| AWS Lambda | 🔄 | [Operadores Airflow](docs/airflow-aws-operators.md#aws-lambda) |
| Amazon EMR | ✅ | [Operadores Airflow](docs/airflow-aws-operators.md#amazon-emr) |
| Amazon Redshift | ✅ | [Operadores Airflow](docs/airflow-aws-operators.md#amazon-redshift) |

### Recursos Avançados
| Recurso | Status | Notas |
|---------|--------|-------|
| Implantação multi-região | ✅ | [Stages](docs/manifest-schema.md#stages) |
| Implantação cross-project | ✅ | [Stages](docs/manifest-schema.md#stages) |
| Gerenciamento de dependências | ✅ | [Operadores Airflow](docs/airflow-aws-operators.md) |
| Assinaturas de catálogo | ✅ | [Schema do Manifesto](docs/manifest-schema.md) |
| Orquestração multi-serviço | ✅ | [Operadores Airflow](docs/airflow-aws-operators.md) |
| Detecção de drift | 🔮 | Detectar drift de configuração |
| Gerenciamento de estado | 🔄 | Rastreamento abrangente de estado |

</details>

---
## Documentação

### Primeiros Passos
- **[Guia de Início Rápido](docs/getting-started/quickstart.md)** - Implante sua primeira aplicação (10 min)
- **[Guia do Administrador](docs/getting-started/admin-quickstart.md)** - Configure infraestrutura (15 min)

### Guias
- **[Manifesto da Aplicação](docs/manifest.md)** - Referência completa de configuração YAML
- **[Comandos CLI](docs/cli-commands.md)** - Todos os comandos e opções disponíveis
- **[Bootstrap Actions](docs/bootstrap-actions.md)** - Ações de implantação automatizadas e workflows orientados a eventos
- **[Substituições e Variáveis](docs/substitutions-and-variables.md)** - Configuração dinâmica
- **[Guia de Conexões](docs/connections.md)** - Configure integrações com serviços AWS
- **[Integração GitHub Actions](docs/github-actions-integration.md)** - Configuração de automação CI/CD
- **[Métricas de Implantação](docs/pipeline-deployment-metrics.md)** - Monitoramento com EventBridge

### Referência
- **[Schema do Manifesto](docs/manifest-schema.md)** - Validação e estrutura do schema YAML
- **[Operadores AWS do Airflow](docs/airflow-aws-operators.md)** - Referência de operadores customizados

### Exemplos
- **[Guia de Exemplos](docs/examples-guide.md)** - Passo a passo de aplicações de exemplo
- **[Data Notebooks](examples/analytic-workflow/data-notebooks/)** - Notebooks Jupyter com Airflow
- **[ML Training](examples/analytic-workflow/ml/training/)** - Treinamento SageMaker com MLflow
- **[ML Deployment](examples/analytic-workflow/ml/deployment/)** - Implantação de endpoint SageMaker
- **[QuickSight Dashboard](examples/analytic-workflow/dashboard-glue-quick/)** - Dashboards BI com Glue
- **[GenAI Application](examples/analytic-workflow/genai/)** - Agentes e knowledge bases Bedrock

### Desenvolvimento
- **[Guia de Desenvolvimento](docs/development.md)** - Contribuindo e testando
- **[Visão Geral de Testes](tests/README.md)** - Infraestrutura de testes

### Suporte
- **Issues**: [GitHub Issues](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/issues)
- **Documentação**: [docs/](docs/)
- **Exemplos**: [examples/](examples/)

---

## Aviso de Segurança

⚠️ **NÃO** instale do PyPI - sempre instale do código fonte oficial da AWS.

```bash
# ✅ Correto - Instalar do repositório oficial da AWS
git clone https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker.git
cd Unified-Studio-for-Amazon-Sagemaker/experimental/SMUS-CICD-pipeline-cli
pip install -e .

# ❌ Errado - Não use PyPI
pip install smus-cicd-cli  # Pode conter código malicioso
```

---

## Licença

Este projeto está licenciado sob a Licença MIT-0. Veja [LICENSE](../../LICENSE) para detalhes.

---

**[English Version](README.md)** | **Versão em Português**

---

