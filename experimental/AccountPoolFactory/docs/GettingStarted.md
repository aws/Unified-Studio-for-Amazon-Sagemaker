# Getting Started with Account Pool Factory

## What Has Been Created

The Account Pool Factory project structure and specifications are now complete. Here's what you have:

### 1. Project Structure
```
experimental/AccountPoolFactory/
├── specs/
│   ├── requirements.md    ✅ Complete - Functional requirements
│   ├── design.md          ✅ Complete - Technical design
│   └── tasks.md           ✅ Complete - Implementation tasks
├── templates/
│   ├── cloudformation/    📝 Ready for implementation
│   ├── cdk/              📝 Future support
│   └── terraform/        📝 Future support
├── src/                  📝 Ready for implementation
├── tests/                📝 Ready for implementation
├── examples/             📝 Ready for implementation
└── scripts/              📝 Ready for implementation
```

### 2. Specifications

#### Requirements Document (`specs/requirements.md`)
Defines the complete functional and non-functional requirements:
- User stories with acceptance criteria
- Architecture overview with Mermaid diagrams
- Configuration parameters (all customer-configurable)
- Control Tower and DataZone integration details
- Account setup steps based on existing CloudFormation templates
- Success metrics and risk mitigation

#### Design Document (`specs/design.md`)
Provides the technical architecture and implementation details:
- System architecture across 3 account types
- Data model (DynamoDB schema)
- API specifications for all Lambda functions
- CloudFormation template designs (CF1, CF2, CF3)
- Workflow sequences with detailed steps
- Security design (IAM roles, encryption)
- Monitoring and observability strategy
- Performance considerations and optimization
- Disaster recovery procedures

#### Tasks Document (`specs/tasks.md`)
Breaks down implementation into 16 phases with 200+ actionable tasks:
- Phase 1: CloudFormation templates (CF1, CF2, CF3)
- Phase 2: Lambda function implementation
- Phase 3: Integration and testing
- Phase 4: Documentation and examples
- Phase 5: Production readiness
- Estimated timeline: 8-12 weeks

### 3. Key Architecture Components

#### Three Account Types
1. **Organization Admin Account (CF1)**
   - AWS Control Tower Account Factory
   - EventBridge rules for account lifecycle events
   - Cross-account IAM role for Domain account

2. **Domain Account (CF2)**
   - DataZone domain with custom account pool
   - 4 Lambda functions (Provider, Manager, Creator, Orchestrator)
   - DynamoDB tables for pool state
   - CloudWatch dashboard and alarms
   - Step Functions for orchestration

3. **Project Accounts (CF3 - StackSet)**
   - DataZone domain association via AWS RAM
   - 17 enabled blueprints (configurable)
   - IAM roles for project operations
   - CloudTrail, VPC (optional), baseline security

#### Four Lambda Functions
1. **Account Provider**: DataZone custom account pool handler
2. **Pool Manager**: Monitors and replenishes the pool
3. **Account Creator**: Triggers Control Tower account creation
4. **Setup Orchestrator**: Deploys CF3 to new accounts

### 4. Configuration Philosophy

All operational parameters are customer-configurable with working defaults:
- Pool sizes (min, max, replenishment threshold)
- Account naming and email conventions
- Organizational Unit placement
- Blueprint selection (17 available)
- IAM roles and policies
- VPC and networking (optional)
- Monitoring and alerting thresholds

## Next Steps

### Immediate Actions

1. **Review the Specifications**
   - Read `specs/requirements.md` to understand what we're building
   - Read `specs/design.md` to understand how we're building it
   - Review `specs/tasks.md` to see the implementation plan

2. **Validate with Stakeholders**
   - Confirm the architecture meets your needs
   - Verify configuration parameters are sufficient
   - Ensure blueprint selection covers your use cases

3. **Prepare for Implementation**
   - Set up development environment
   - Create test AWS accounts (Org Admin, Domain, Project)
   - Configure AWS Control Tower in test environment
   - Create test DataZone domain

### Implementation Approach

You have two options:

#### Option A: Follow the Task List
Work through `specs/tasks.md` sequentially:
1. Start with Phase 1: CF1 template
2. Move to CF2 template
3. Implement CF3 template
4. Build Lambda functions
5. Test and deploy

#### Option B: Use Kiro Spec Workflow
Let Kiro help you implement the tasks:
```bash
# From the project root
kiro spec execute experimental/AccountPoolFactory
```

This will:
- Guide you through each task
- Generate code based on the design
- Run tests automatically
- Track progress

### Quick Start Commands

```bash
# Navigate to project directory
cd experimental/AccountPoolFactory

# Review specifications
cat specs/requirements.md
cat specs/design.md
cat specs/tasks.md

# Start implementation (when ready)
# Begin with CF1 template
cd templates/cloudformation/01-org-admin
# Create org-admin-setup.yaml based on design.md section 4.1
```

## Key Design Decisions

### 1. CloudFormation First
- Primary IaC tool: CloudFormation
- Future support: CDK and Terraform
- Reason: Widest compatibility, no additional dependencies

### 2. Three-Template Architecture
- **CF1**: Org Admin setup (one-time)
- **CF2**: Domain account setup (one-time)
- **CF3**: Project account setup (deployed via StackSet to each account)

### 3. Asynchronous Pool Replenishment
- Pool Manager runs every 5 minutes
- Replenishment happens in background
- Projects never wait for account creation

### 4. State Machine in DynamoDB
- Account states: PROVISIONING → CONFIGURING → AVAILABLE → ASSIGNED
- Atomic state transitions prevent race conditions
- GSIs for efficient queries

### 5. Comprehensive Monitoring
- CloudWatch metrics for all operations
- Dashboard for pool health visualization
- Alarms for critical conditions
- SNS notifications for operators

## Configuration Examples

### Minimal Configuration
```yaml
MinimumPoolSize: 3
MaximumPoolSize: 10
AccountNamePrefix: "test-project-"
EnabledBlueprints: "LakehouseCatalog,Tooling,MLExperiments"
CreateVPC: false
```

### Production Configuration
```yaml
MinimumPoolSize: 10
MaximumPoolSize: 50
ReplenishmentThreshold: 15
AccountNamePrefix: "prod-datazone-"
EnabledBlueprints: "all"
CreateVPC: true
VPCCidr: "10.0.0.0/16"
EnableDetailedMonitoring: true
```

## Important Considerations

### Prerequisites
- AWS Control Tower must be configured
- DataZone domain must exist
- Appropriate IAM permissions for deployment
- Service quotas sufficient for pool size

### Cost Factors
- AWS accounts (no direct cost, but resources within)
- Lambda invocations (~$0.20 per 1M requests)
- DynamoDB storage and requests (~$1-5/month)
- CloudWatch logs and metrics (~$5-10/month)
- StackSet operations (minimal)

### Timeline
- Design and planning: ✅ Complete
- Implementation: 8-12 weeks (estimated)
- Testing: Included in implementation phases
- Production deployment: 1-2 weeks

## Questions?

Refer to:
- `specs/requirements.md` - What we're building
- `specs/design.md` - How we're building it
- `specs/tasks.md` - Step-by-step implementation
- `README.md` - Project overview
- `PROJECT_STRUCTURE.md` - Directory structure

## Ready to Start?

1. Review all specification documents
2. Set up your development environment
3. Create test AWS accounts
4. Start with Phase 1, Task 1.1 in `specs/tasks.md`
5. Or use Kiro to help: `kiro spec execute experimental/AccountPoolFactory`

Good luck! 🚀
