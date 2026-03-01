# Account Pool Factory - Project Structure

This document provides an overview of the project structure created for the Account Pool Factory.

## Directory Tree

```
experimental/AccountPoolFactory/
├── README.md                                    # Main project documentation
├── PROJECT_STRUCTURE.md                         # This file
│
├── docs/                                        # Documentation
│   └── .gitkeep
│
├── specs/                                       # Requirements and design
│   └── requirements.md                          # Functional requirements (already exists)
│
├── templates/                                   # Infrastructure as Code
│   ├── cloudformation/                          # CloudFormation (primary)
│   │   ├── 01-org-admin/                        # CF1: Org Admin setup
│   │   │   └── README.md
│   │   ├── 02-domain-account/                   # CF2: Domain account setup
│   │   │   └── README.md
│   │   └── 03-project-account/                  # CF3: Project account setup
│   │       └── README.md
│   ├── cdk/                                     # AWS CDK (future)
│   │   └── README.md
│   └── terraform/                               # Terraform (future)
│       └── README.md
│
├── src/                                         # Lambda function source code
│   ├── account-provider/                        # DataZone account provider
│   │   └── README.md
│   ├── pool-manager/                            # Pool management
│   │   └── README.md
│   ├── account-creator/                         # Account creation trigger
│   │   └── README.md
│   ├── setup-orchestrator/                      # Account setup orchestration
│   │   └── README.md
│   └── shared/                                  # Shared utilities
│       └── README.md
│
├── tests/                                       # Test suites
│   ├── README.md
│   ├── setup/                                   # Test infrastructure setup
│   │   ├── README.md                            # Test setup documentation
│   │   ├── scripts/                             # Test setup scripts
│   │   │   ├── deploy-organization.sh           # Deploy test org structure
│   │   │   └── validate-organization.sh         # Validate test setup
│   │   └── templates/                           # Test CloudFormation templates
│   │       └── organization-structure.yaml      # Test OU structure
│   ├── unit/                                    # Unit tests
│   ├── integration/                             # Integration tests
│   └── fixtures/                                # Test data and fixtures
│
├── examples/                                    # Example configurations
│   └── README.md
│
└── scripts/                                     # Utility scripts
    └── README.md
```

## Key Components

### 1. Templates (Infrastructure)

**CloudFormation** (Primary - Ready for Implementation)
- `01-org-admin/`: Sets up Control Tower integration in Org Admin account
- `02-domain-account/`: Deploys pool management system in Domain account
- `03-project-account/`: Configures new accounts (deployed as StackSet)

**CDK & Terraform** (Future)
- Placeholder directories with README explaining future support
- Allows customers to choose their preferred IaC tool

### 2. Source Code (Lambda Functions)

Four main Lambda functions:
1. **account-provider**: DataZone custom account pool handler
2. **pool-manager**: Monitors and replenishes the pool
3. **account-creator**: Triggers Control Tower account creation
4. **setup-orchestrator**: Deploys CF3 to new accounts

Plus **shared** utilities for common functionality.

### 3. Documentation

- Main README with project overview
- Per-component READMEs with detailed information
- Specs directory for requirements and design
- Docs directory for additional documentation (to be populated)

### 4. Testing

Comprehensive test structure:
- Unit tests for individual components
- Integration tests for end-to-end workflows
- Fixtures for test data

### 5. Examples

Three example configurations:
- **Minimal**: Quick start, development
- **Production**: Enterprise-ready
- **Custom**: Specialized use cases

### 6. Scripts

Utility scripts for:
- Deployment automation
- Configuration validation
- Resource cleanup
- Pool monitoring
- Testing

## Next Steps

### Immediate (Design Phase)
1. Create `specs/design.md` with technical architecture
2. Create `specs/tasks.md` with implementation breakdown
3. Populate `docs/` with architecture diagrams and guides

### Implementation Phase
1. Implement CloudFormation templates (CF1, CF2, CF3)
2. Implement Lambda functions
3. Create shared utilities
4. Write unit tests
5. Create example configurations
6. Write deployment scripts

### Testing Phase
1. Unit testing
2. Integration testing
3. End-to-end testing
4. Performance testing

### Documentation Phase
1. Architecture documentation
2. Deployment guide
3. Configuration guide
4. Troubleshooting guide
5. API documentation

## Design Principles

### Modularity
- Each component is self-contained
- Clear interfaces between components
- Easy to test and maintain

### Flexibility
- Support multiple IaC tools (CF, CDK, Terraform)
- Configurable parameters
- Customizable templates

### Extensibility
- Easy to add new blueprints
- Support for custom configurations
- Plugin architecture for future enhancements

### Observability
- Comprehensive logging
- CloudWatch metrics
- Monitoring dashboards
- Alerting

### Security
- Least-privilege IAM roles
- Encrypted data at rest
- Audit logging
- Compliance with AWS best practices

## File Naming Conventions

- **CloudFormation**: `kebab-case.yaml`
- **Python**: `snake_case.py`
- **Documentation**: `kebab-case.md`
- **Scripts**: `kebab-case.sh`
- **Configs**: `kebab-case.yaml` or `.json`

## Status

✅ **Completed**: Project structure created
🚧 **In Progress**: Requirements documentation
⏳ **Pending**: Design, implementation, testing

## Contributing

When adding new components:
1. Follow the established directory structure
2. Include a README in each new directory
3. Update this PROJECT_STRUCTURE.md
4. Follow naming conventions
5. Add appropriate documentation

## Questions?

See the main [README.md](README.md) or individual component READMEs for more information.
