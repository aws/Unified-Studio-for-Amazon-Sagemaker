# Account Pool Factory Documentation

This directory contains all project documentation organized by audience.

## Start Here

### 👥 For Real Deployment (Production/Existing Infrastructure)

**[Org Admin Guide](OrgAdminGuide.md)** - Deploy governance stack in the Org Admin account

**[Domain Admin Guide](DomainAdminGuide.md)** - Deploy infrastructure and manage the pool in the Domain account
- Prerequisites (existing org, domain, OUs)
- Deployment by persona (Org Admin, Domain Admin, Project Creator)
- Common tasks and troubleshooting

### 🧪 For Test Environment Setup (Starting from Scratch)
**[Test Setup Guide](TestSetupGuide.md)** - Create test infrastructure before deployment:
- Create AWS Organization structure
- Create DataZone domain
- Create test accounts
- Prepare environment to match real deployment

### 🔧 For Developers
**[Development Progress](DevelopmentProgress.md)** - Development journey including:
- What's working and what's not
- Experiments and test results
- Key findings and lessons learned
- Technical debt and pending work

### 📋 For Detailed Testing
**[Testing Guide](TestingGuide.md)** - Comprehensive step-by-step testing procedures with:
- Detailed commands and expected outputs
- Verification checklists
- Console verification steps
- Complete troubleshooting guide

## Additional Documentation

### Architecture & Design
- **[../specs/requirements.md](../specs/requirements.md)** - Functional requirements and system architecture
- **[../specs/design.md](../specs/design.md)** - Technical design and API specifications
- **[../specs/tasks.md](../specs/tasks.md)** - Implementation task breakdown

### Project Information
- **[ProjectStructure.md](ProjectStructure.md)** - Directory structure and organization
- **[../config.yaml.template](../config.yaml.template)** - Configuration template

### Status Reports
- **[../ACCOUNT_POOL_SUCCESS.md](../ACCOUNT_POOL_SUCCESS.md)** - Account pool integration success report
- **[../ACCOUNT_POOL_FINDINGS.md](../ACCOUNT_POOL_FINDINGS.md)** - ON_CREATE investigation findings
- **[../IMPLEMENTATION_STATUS.md](../IMPLEMENTATION_STATUS.md)** - Current implementation status

## Quick Navigation

### I want to...
- **Deploy to existing infrastructure**: → [Org Admin Guide](OrgAdminGuide.md) then [Domain Admin Guide](DomainAdminGuide.md)
- **Set up test environment first**: → [Test Setup Guide](TestSetupGuide.md)
- **Understand what works**: → [Development Progress](DevelopmentProgress.md) → Completed Milestones
- **Run detailed tests**: → [Testing Guide](TestingGuide.md)
- **Understand the architecture**: → [Requirements](../specs/requirements.md)
- **See technical details**: → [Design](../specs/design.md)
- **Know what's next**: → [Development Progress](DevelopmentProgress.md) → Pending Work

## Documentation Philosophy

We've separated documentation into four levels:

1. **User Guide**: Real deployment to existing infrastructure (production-ready)
2. **Test Setup Guide**: Create test infrastructure from scratch (for testing/learning)
3. **Development Progress**: What we learned building it (experiments, findings, lessons)
4. **Testing Guide**: How to test every detail (comprehensive procedures)

This keeps deployment docs focused on real use cases while providing clear paths for testing and development.
