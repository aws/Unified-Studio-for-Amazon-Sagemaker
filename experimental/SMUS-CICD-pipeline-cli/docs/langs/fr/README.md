# SMUS CI/CD Pipeline CLI

**Automatisez le déploiement d'applications de données dans les environnements SageMaker Unified Studio**

Déployez des DAGs Airflow, des notebooks Jupyter et des workflows ML du développement à la production en toute confiance. Conçu pour les data scientists, les data engineers, les ingénieurs ML et les développeurs d'applications GenAI travaillant avec les équipes DevOps.

**Fonctionne avec votre stratégie de déploiement :** Que vous utilisiez des branches git (basé sur les branches), des artefacts versionnés (basé sur les bundles), des tags git (basé sur les tags) ou un déploiement direct - cette CLI supporte votre workflow. Définissez votre application une fois, déployez-la à votre manière.

---

## Pourquoi SMUS CI/CD CLI ?

✅ **Couche d'Abstraction AWS** - La CLI encapsule toute la complexité AWS analytics, ML et SMUS - les équipes DevOps n'appellent jamais directement les APIs AWS  
✅ **Séparation des Préoccupations** - Les équipes data définissent QUOI déployer (manifest.yaml), les équipes DevOps définissent COMMENT et QUAND (workflows CI/CD)  
✅ **Workflows CI/CD Génériques** - Le même workflow fonctionne pour Glue, SageMaker, Bedrock, QuickSight ou toute combinaison de services AWS  
✅ **Déployez en Confiance** - Tests automatisés et validation avant la production  
✅ **Gestion Multi-Environnement** - Test → Prod avec configuration spécifique par environnement  
✅ **Infrastructure as Code** - Manifestes d'application versionnés et déploiements reproductibles  
✅ **Workflows Événementiels** - Déclenchez des workflows automatiquement via EventBridge lors du déploiement  

---

## Démarrage Rapide

**Installer depuis les sources :**
```bash
git clone https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker.git
cd Unified-Studio-for-Amazon-Sagemaker/experimental/SMUS-CICD-pipeline-cli
pip install -e .
```

**Déployez votre première application :**
```bash
# Valider la configuration
smus-cli describe --manifest manifest.yaml --connect

# Créer un bundle de déploiement (optionnel)
smus-cli bundle --manifest manifest.yaml

# Déployer sur l'environnement de test
smus-cli deploy --targets test --manifest manifest.yaml

# Exécuter les tests de validation
smus-cli test --manifest manifest.yaml --targets test
```

**Voir en action :** [Exemple GitHub Actions en Direct](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/actions/runs/17631303500)

---
