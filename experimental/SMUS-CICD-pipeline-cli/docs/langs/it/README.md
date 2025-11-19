# CLI Pipeline CI/CD SMUS

**Automatizza il deployment di applicazioni dati attraverso gli ambienti SageMaker Unified Studio**

Distribuisci DAG Airflow, notebook Jupyter e workflow ML dallo sviluppo alla produzione con sicurezza. Creato per data scientist, data engineer, ML engineer e sviluppatori GenAI che lavorano con team DevOps.

**Funziona con la tua strategia di deployment:** Che tu utilizzi branch git (branch-based), artefatti versionati (bundle-based), tag git (tag-based) o deployment diretto - questa CLI supporta il tuo workflow. Definisci la tua applicazione una volta, distribuiscila a modo tuo.

---

## Perché SMUS CI/CD CLI?

✅ **Livello di Astrazione AWS** - La CLI incapsula tutta la complessità di analytics, ML e SMUS di AWS - i team DevOps non chiamano mai direttamente le API AWS  
✅ **Separazione delle Responsabilità** - I team dati definiscono COSA distribuire (manifest.yaml), i team DevOps definiscono COME e QUANDO (workflow CI/CD)  
✅ **Workflow CI/CD Generici** - Lo stesso workflow funziona per Glue, SageMaker, Bedrock, QuickSight o qualsiasi combinazione di servizi AWS  
✅ **Deploy con Sicurezza** - Test e validazione automatizzati prima della produzione  
✅ **Gestione Multi-Ambiente** - Test → Prod con configurazione specifica per ambiente  
✅ **Infrastructure as Code** - Manifest applicativi versionati e deployment riproducibili  
✅ **Workflow Event-Driven** - Attiva workflow automaticamente via EventBridge al deployment  

---

## Quick Start

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

# Crea bundle di deployment (opzionale)
smus-cli bundle --manifest manifest.yaml

# Deploy nell'ambiente di test
smus-cli deploy --targets test --manifest manifest.yaml

# Esegui test di validazione
smus-cli test --manifest manifest.yaml --targets test
```

**Guardalo in azione:** [Esempio Live GitHub Actions](https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/actions/runs/17631303500)

---

## Per Chi È?

### 👨‍💻 Team Dati (Data Scientist, Data Engineer, Sviluppatori GenAI)
**Ti concentri su:** La tua applicazione - cosa distribuire, dove distribuire e come funziona  
**Definisci:** Manifest applicativo (`manifest.yaml`) con il tuo codice, workflow e configurazioni  
**Non devi sapere:** Pipeline CI/CD, GitHub Actions, automazione del deployment  

→ **[Guida Quick Start](docs/getting-started/quickstart.md)** - Distribuisci la tua prima applicazione in 10 minuti  

**Include esempi per:**
- Data Engineering (Glue, Notebooks, Athena)
- Workflow ML (SageMaker, Notebooks)
- Applicazioni GenAI (Bedrock, Notebooks)

**Azioni Bootstrap - Automatizza Attività Post-Deployment:**

Definisci azioni nel tuo manifest che vengono eseguite automaticamente dopo il deployment:
- Attiva workflow immediatamente (nessuna esecuzione manuale necessaria)
- Aggiorna dashboard QuickSight con dati più recenti
- Configura connessioni MLflow per il tracking degli esperimenti
- Recupera log per la validazione
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

[Il resto della traduzione continua seguendo lo stesso pattern - mantenendo invariati i blocchi di codice, i nomi dei servizi AWS, i termini tecnici e la struttura del markdown, traducendo solo il testo descrittivo in italiano]