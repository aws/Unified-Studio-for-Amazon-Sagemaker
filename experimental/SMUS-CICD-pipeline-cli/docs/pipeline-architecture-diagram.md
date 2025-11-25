# SMUS CI/CD Pipeline Architecture

← [Back to Main README](../README.md)


## Pipeline Architecture Diagram

```mermaid
graph TB
    subgraph "Local CI/CD Dev Environment"
        DEVOPS[DevOps Users]
        PIPELINE_DEF[Pipeline Definitions]
        DEVOPS --- PIPELINE_DEF
    end
    
    subgraph "SageMaker Unified Studio Environment"
        DEV_PROJ[Dev Project]
        TEST_PROJ[Test Project]
        PROD_PROJ[Production Project]
    end
    
    subgraph "CI/CD Pipeline"
        CICD[CI/CD Pipeline Engine]
        DEPLOY_TEST[Deploy to Test]
        DEPLOY_PROD[Deploy to Production]
        CICD --- DEPLOY_TEST
        CICD --- DEPLOY_PROD
    end
    
    subgraph "Repositories"
        GIT_REPO[Git Repository<br/>Pipelines]
        BUNDLE_REPO[Bundle Repository]
    end
    
    %% Connections
    PIPELINE_DEF --> GIT_REPO
    PIPELINE_DEF --> BUNDLE_REPO
    PIPELINE_DEF --> DEV_PROJ
    
    BUNDLE_REPO --> CICD
    DEPLOY_TEST --> TEST_PROJ
    DEPLOY_PROD --> PROD_PROJ
    
    %% Styling
    classDef localStyle fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef smusStyle fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    classDef cicdStyle fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef repoStyle fill:#fff3e0,stroke:#ef6c00,stroke-width:2px
    
    class DEVOPS,PIPELINE_DEF localStyle
    class DEV_PROJ,TEST_PROJ,PROD_PROJ smusStyle
    class CICD,DEPLOY_TEST,DEPLOY_PROD cicdStyle
    class GIT_REPO,BUNDLE_REPO repoStyle
```

## Key Components

### 1. Local CI/CD Dev Environment
- **DevOps Users**: Engineers developing and managing pipelines
- **Pipeline Definitions**: YAML manifests and configuration files
- **Connected to**: Git repositories and bundle storage

### 2. SageMaker Unified Studio Environment  
- **Dev Project**: Development and experimentation
- **Test Project**: Integration testing and validation
- **Production Project**: Live production deployment

### 3. CI/CD Pipeline
- **CI/CD Pipeline Engine**: Automated deployment orchestration
- **Deploy to Test**: Automated test environment deployment
- **Deploy to Production**: Automated production deployment
- **Source**: Bundle repository

### 4. Repositories
- **Git Repository (Pipelines)**: Version control for pipeline definitions
- **Bundle Repository**: Packaged deployment artifacts

## Workflow
1. DevOps users create pipeline definitions locally
2. Definitions are committed to Git repository
3. Bundles are created and stored in bundle repository
4. Dev project receives direct deployments for development
5. CI/CD pipeline pulls bundles and deploys to test and production projects
