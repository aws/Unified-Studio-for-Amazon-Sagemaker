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
