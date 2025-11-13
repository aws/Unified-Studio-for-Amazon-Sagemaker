# Getting Started with SMUS CI/CD CLI

Choose the guide that matches your role:

## 👨‍💻 For Data Teams (Data Scientists, Data Engineers, GenAI App Developers)

**Build and deploy data application bundles**

You want to create deployable data applications with Spark code, Python scripts, Airflow workflows, and notebooks.

→ **[Quick Start Guide](quickstart.md)** (10-15 minutes)

**What you'll learn:**
- Install the CLI
- Create bundle manifests
- Build workflows (Glue, Notebooks, SageMaker, Bedrock)
- Configure multi-environment deployment
- Use variable substitution
- Deploy your data applications

**Includes examples for:**
- Data Engineering with Glue
- Data Engineering with Notebooks
- ML Training with Notebooks + SageMaker
- GenAI with Bedrock + Notebooks

---

## 🔧 For DevOps Teams

**Set up CI/CD pipelines and infrastructure**

You're responsible for configuring CI/CD pipelines (GitHub Actions), managing SageMaker Unified Studio projects, and setting up infrastructure for data teams.

→ **[Admin Quick Start](admin-quickstart.md)** (15-20 minutes)

**What you'll learn:**
- Create projects for dev/test/prod
- Configure connections and resources
- Set up GitHub Actions CI/CD pipelines
- Manage team access
- Configure monitoring and alerts
- Control infrastructure templates

---

## Not Sure Where to Start?

### I want to...

**Build and deploy data applications (bundles)**  
→ [Quick Start Guide](quickstart.md)

**Set up CI/CD pipelines and infrastructure**  
→ [Admin Quick Start](admin-quickstart.md)

**Understand how it works first**  
→ [Bundle Manifest Reference](../bundle-manifest.md)

**See examples**  
→ [Examples](../../examples/)

**Read complete documentation**  
→ [CLI Commands](../cli-commands.md) | [Bundle Manifest](../bundle-manifest.md)

---

## Prerequisites

All guides assume you have:

- ✅ AWS account with appropriate permissions
- ✅ Python 3.8 or later
- ✅ AWS CLI configured
- ✅ Access to SageMaker Unified Studio

**Don't have SageMaker Unified Studio set up?** See the [Admin Quick Start](admin-quickstart.md).

---

## What's Next?

After completing a quick start guide:

1. **Explore Examples** - See [examples/](../../examples/) for real-world scenarios
2. **Read Concepts** - Understand [bundle manifests](../bundle-manifest.md)
3. **Reference Docs** - Check [CLI commands](../cli-commands.md) and [manifest syntax](../bundle-manifest.md)
4. **Set Up CI/CD** - Configure [GitHub Actions](../github-actions-integration.md)

---

## Need Help?

- **Documentation**: Browse [docs/](../)
- **Examples**: Check [examples/](../../examples/)
- **Issues**: [GitHub Issues](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/issues)
- **Contributing**: [Development Guide](../development.md)
