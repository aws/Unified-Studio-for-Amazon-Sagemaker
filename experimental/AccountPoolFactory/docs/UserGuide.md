# Account Pool Factory - User Guide

[← Back to README](../README.md) | [Org Admin Guide](OrgAdminGuide.md) | [Domain Admin Guide](DomainAdminGuide.md) | [Architecture](Architecture.md) | [Security Guide](SecurityGuide.md) | [Testing Guide](TestingGuide.md)

---

This guide has been split into role-specific guides. Go to the one that matches your role:

- **[OrgAdminGuide.md](OrgAdminGuide.md)** — for the person with access to the AWS Organizations management account. Covers deploying the governance stack, what permissions are granted, and how to add new approved StackSets.

- **[DomainAdminGuide.md](DomainAdminGuide.md)** — for the person who manages the DataZone domain and runs the account pool. Covers deployment, configuration, monitoring, and day-to-day operations.

- **[TestingGuide.md](TestingGuide.md)** — for anyone doing end-to-end testing. Covers deployment order, pool seeding, the lifecycle test script, and common failure modes.

## Configuration

Two minimal config files replace the old `config.yaml`:

| File | Account | What to set |
|------|---------|-------------|
| `org-config.yaml` | Org Admin | `region`, `target_ou_name` |
| `domain-config.yaml` | Domain | `region`, `domain_name`, `email_prefix`, `email_domain`, `default_project_owner` |

IDs (domain ID, OU ID, org ID, role ARNs) are resolved automatically by scripts. Copy from the `.template` files.

## Quick Reference

| Task | Guide |
|------|-------|
| Deploy org admin governance stack | OrgAdminGuide |
| Deploy domain account infrastructure | DomainAdminGuide |
| Configure pool size and strategy | DomainAdminGuide |
| Monitor pool health | DomainAdminGuide |
| Handle failed accounts | DomainAdminGuide |
| Run end-to-end lifecycle test | TestingGuide |
| Troubleshoot failures | TestingGuide |
