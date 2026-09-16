RentGuard
=========

> **An end-to-end RAG + MLOps platform for Indian rental-law Q&A and clause-risk classification.**

Ingest 270+ legal PDFs → embed with multilingual embeddings → retrieve with jurisdiction awareness → answer with citation verification → classify clauses by risk → ship it all through CI/CD to Kubernetes with full observability.

[https://github.com/jhav1643/rentguard/actions/workflows/test.yml/badge.svg](https://github.com/jhav1643/rentguard/actions/workflows/test.yml/badge.svg)[https://github.com/jhav1643/rentguard/actions/workflows/security-scan.yaml/badge.svg](https://github.com/jhav1643/rentguard/actions/workflows/security-scan.yaml/badge.svg)[https://img.shields.io/badge/python-3.11-blue.svg](https://img.shields.io/badge/python-3.11-blue.svg)[https://img.shields.io/badge/License-MIT-yellow.svg](https://img.shields.io/badge/License-MIT-yellow.svg)

Table of Contents
-----------------

*   What is RentGuard?
    
*   Architecture
    
*   The Complete Flow
    
*   Technology Stack
    
*   Repository Layout
    
*   Docker Compose Services
    
*   CI/CD Pipeline
    
*   Observability
    
*   Quick Start
    
*   Environment Variables
    
*   Development Workflow
    
*   Model Evaluation
    
*   Kubernetes Deployment
    
*   Security Posture
    
*   Roadmap
    

What is RentGuard?
------------------

RentGuard solves two problems for tenants, landlords, and legal-aid teams in India:

1.  **"What does the law say about X in my city?"** — A RAG pipeline that reads the actual statutes, retrieves the relevant clauses, and generates an answer with citations you can verify.
    
2.  **"Is this lease clause risky?"** — A trained classifier that scores clauses (High / Medium / Low risk) so a non-lawyer can spot unfair terms before signing.
    

The project is deliberately **full-lifecycle**: it covers ingestion, embeddings, vector search, agent orchestration, model training, model registry, API serving, a chat UI, containerization, CI/CD, Kubernetes deployment, and observability — all in one repo. It's a reference implementation of what "shipping ML to production" actually looks like, not a notebook.

Architecture
------------

text

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML                          `┌─────────────────────────────────────┐                            │        React + Vite Frontend        │                            │   http://localhost:8080 (nginx)     │                            └──────────────────┬──────────────────┘                                               │  /api/chat                                               ▼                            ┌─────────────────────────────────────┐                            │         backend_api  :5001          │                            │   Flask · LangGraph · Prometheus    │                            └───────┬──────────────────┬──────────┘                                    │                  │                          in-process│                  │in-process                                    ▼                  ▼                   ┌───────────────────────┐   ┌─────────────────────┐                   │  agent_orchestrator   │   │  classifier_service │                   │  (LangGraph state)    │   │  (MLflow champion)  │                   └───────────┬───────────┘   └──────────┬──────────┘                               │                          │                               ▼                          ▼                   ┌───────────────────────┐   ┌─────────────────────┐                   │   rag_api  :5000      │   │   MLflow  :5002     │                   │  Retrieval + Rerank   │   │  Registry + Alias   │                   └───────────┬───────────┘   └─────────────────────┘                               │                               ▼                   ┌───────────────────────┐                   │  ChromaDB (persisted) │                   │  data/vectorstore/    │                   └───────────────────────┘                               ▲                               │  writes                   ┌───────────────────────┐                   │  ingestion (batch)    │                   │  272 PDFs → 1,106 chunks│                   └───────────────────────┘    ┌──────────────────────────────────────────────────────────────┐    │  Observability:  Prometheus :9090  →  Grafana :3000          │    │  Custom metrics: retrieval latency, empty-retrieval rate,    │    │  LLM tokens, citation-check pass/fail, HTTP 5xx              │    └──────────────────────────────────────────────────────────────┘`

The Complete Flow
-----------------

### 1\. Ingestion (batch, runs once)

text

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   data/raw/delhi/*.pdf        │        ▼  PyMuPDF / docx2txt ──► clean text        │        ▼  RecursiveCharacterTextSplitter ──► 499 chunks        │        ▼  BAAI/bge-m3 embeddings (HF Inference API, batched by 64)        │        ▼  ChromaDB persistent store ──► data/vectorstore/chroma   `

Each chunk carries metadata: source, page, jurisdiction, doc\_type. Jurisdiction metadata is what enables city-aware retrieval later.

### 2\. Classification (batch, runs once)

text

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   data/labeled/*.csv (923 labeled clauses)        │        ▼  Embeddings + 4 numeric features + 7 flag features ──► 1,053-dim matrix        │        ▼  Stratified split: 646 train / 138 val / 139 test        │        ▼  Train LR vs Gradient Boosting ──► LR wins (val macro-F1 0.73)        │        ▼  MLflow registry: rentguard-risk-classifier v1        │        ▼  Champion alias set ──► models:/rentguard-risk-classifier@champion   `

Evaluation metrics (metrics/eval\_metrics.json) are DVC-tracked so the CI promotion gate can diff candidate vs champion.

### 3\. Query-Time RAG (live, per request)

text

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   User question + jurisdiction        │        ▼  rag_api.retrieve()  ──► Chroma similarity search, jurisdiction filter        │        ▼  Top-K chunks (with metadata)        │        ▼  Citation check ──► is each source cited in the answer?  (pass/fail metric)        │        ▼  LLM (OpenAI / Groq / Aion) ──► grounded answer        │        ▼  Response: { answer, sources[], citation_check, jurisdiction }   `

If zero chunks are retrieved (e.g., unknown jurisdiction), rag\_retrieval\_empty\_total increments — that's the alert that would have caught the jurisdiction='delhi' bug in seconds instead of hours.

### 4\. Serving

*   **RAG API** (:5000) — retrieval + citation check
    
*   **Backend API** (:5001) — agent orchestration, classifier inference, /chat endpoint
    
*   **Frontend** (:8080) — React SPA served by nginx, /api/\* reverse-proxied to backend
    

Technology Stack
----------------

LayerTechnologyWhere used**Language**Python 3.11, JavaScript (ES2020+)All services / frontend**LLM orchestration**LangChain, LangGraphagent\_orchestrator, backend\_api**Embeddings**BAAI/bge-m3 via HF Inference APIservices/common/embedder.py**Vector DB**ChromaDB (persistent, local)services/ingestion/vectorstore.py**RAG eval**RAGAS 0.1.16, datasets, pandastests/rag\_eval/run\_rag\_eval.py**Classical ML**scikit-learn, joblibservices/classifier\_service/training/**Experiment tracking**MLflow 3.x + SQLite backendmlflow/ volume**Data versioning**DVCdvc.yaml, dvc.lock**Backend**Flask 3.1, Gunicornservices/rag\_api, services/backend\_api**Metrics**prometheus\_flask\_exporter, prometheus\_clientBoth Flask apps**Frontend**React 18, Vite 5, nginx 1.27frontend/**Containers**Docker, Docker Compose (profiles)Root docker-compose.yml**Orchestration**Kubernetes (EKS), Helm 3.16infra/helm/\***CI/CD**GitHub Actions (OIDC → AWS).github/workflows/**Registry**Amazon ECR (SHA-only tags)build-push.yml**Observability**Prometheus 2.54, Grafana 11.2infra/observability/**Security**Trivy, pip-audit, gitleaks, GitHub SARIFsecurity-scan.yaml

Repository Layout
-----------------

text

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   rentguard/  ├── services/  │   ├── ingestion/            # PDF → chunks → embeddings → Chroma  │   ├── classifier_service/   # feature engineering, training, MLflow registration  │   ├── rag_api/              # retrieval + citation API (:5000)  │   ├── backend_api/          # agent + classifier API (:5001)  │   ├── agent_orchestrator/   # LangGraph state machine  │   └── common/               # shared embedder, clause splitter  │  ├── frontend/                 # React SPA (Vite) + nginx container  │   ├── src/  │   ├── Dockerfile  │   └── nginx.conf  │  ├── tests/  │   ├── unit/                 # pytest smoke tests  │   └── rag_eval/             # RAGAS harness + golden dataset  │  ├── infra/  │   ├── helm/                 # per-service Helm charts  │   │   ├── backend_api/  │   │   ├── rag_api/  │   │   ├── ingestion/  │   │   └── classifier_service/  │   ├── observability/        # prometheus.yml, alerts.yml, grafana provisioning  │   └── terraform/            # EKS + IAM + ECR (gitignored state)  │  ├── ci-cd/  │   ├── eval/                 # thresholds.yaml, gate scripts  │   ├── runbooks/             # rollback, promotion, failed-deploy  │   └── reports/              # gitignored  │  ├── .github/workflows/        # test, build-push, deploy, security, rag-eval-gate  ├── data/                     # gitignored: raw, processed, features, vectorstore  ├── metrics/                  # eval outputs (DVC-tracked)  ├── mlflow/                   # gitignored: SQLite tracking store  ├── docker-compose.yml  ├── dvc.yaml  ├── requirements.txt  └── README.md   `

Docker Compose Services
-----------------------

The Compose file separates **batch jobs** from **live services** using profiles.

ServiceProfilePortPurposeingestionsetup—Load PDFs → Chroma (runs once, exits)classifier\_servicesetup—Train + register classifier (runs once, exits)rag\_apidefault5000Retrieval + citation APIbackend\_apidefault5001Chat + classifier APImlflowdefault5002Tracking server + registry UIfrontenddefault8080React + nginxprometheusdefault9090Metrics storegrafanadefault3000Dashboards

CI/CD Pipeline
--------------

Seven workflows, all under .github/workflows/:

WorkflowTriggerWhat it doestest.ymlpush, PRruff lint + pytestbuild-push.ymlpush to mainMatrix-builds 6 images, pushes SHA-tagged to ECR via OIDCdeploy.ymlafter build-pushHelm upgrade to EKS with --atomic rollbacksecurity-scan.yamlpush, PRTrivy fs + image, pip-audit, gitleaks → SARIF to GitHub Securityrag-eval-gate.yamlPR + nightlyRuns RAGAS, fails on threshold regressionmodel-eval-gate.ymlPRValidates candidate classifier against absolute thresholdsmodel-promotion-gate.yamlmanualBootstrap CI test before flipping champion alias

**Key design choices:**

*   **OIDC, not long-lived AWS keys.** IAM role trusts repo:jhav1643/rentguard:\*.
    
*   **SHA-only tags.** No :latest. Every image is traceable to a commit.
    
*   **Eval gates are blocking.** A RAG quality drop fails the PR, not the deploy.
    
*   **\--atomic deploys.** Failed rollout auto-reverts to the last good revision.
    

Observability
-------------

Custom Prometheus metrics emitted by both Flask apps:

MetricTypeWhy it existsrag\_retrieval\_latency\_secondsHistogramp50/p95 retrieval latencyrag\_retrieval\_empty\_totalCounterRetrieval returned zero chunks — **this is the alert that would have caught the delhi bug**llm\_tokens\_total{model,type}CounterPrompt/completion token spendcitation\_check\_total{status}CounterPass/fail on citation verificationbackend\_requests\_total{endpoint,status}CounterHTTP 5xx spike detection

Grafana dashboard **RentGuard Overview** shows all of the above plus active alerts. Six alert rules in infra/observability/alerts.yml cover: empty retrieval, high latency, citation failures, 5xx spikes, and service-down for both APIs.

Quick Start
-----------

### Prerequisites

*   Docker Desktop (Windows/macOS) or Docker Engine (Linux)
    
*   8 GB RAM minimum, 12 GB recommended
    
*   An .env file with the variables listed below
    

### 1\. Clone and configure

bash

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   git clone https://github.com/jhav1643/rentguard.git  cd rentguard  cp .env.example .env  # edit .env — fill in HF_TOKEN, OPENAI_API_KEY (or AION_API_KEY), BACKEND_API_KEY   `

### 2\. Run the one-time batch jobs

bash

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   docker compose --profile setup run --rm ingestion  docker compose --profile setup run --rm classifier_service   `

The first run embeds 270+ PDFs (a few minutes). The classifier job trains and registers the model with the champion alias.

### 3\. Start the live stack

bash

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   docker compose up -d   `

Wait for healthchecks:

bash

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   docker compose ps   `

All services should show Up (healthy).

### 4\. Open

ServiceURLLoginFrontend[http://localhost:8080](http://localhost:8080/)—Backend API[http://localhost:5001](http://localhost:5001/)—RAG API[http://localhost:5000](http://localhost:5000/)—MLflow[http://localhost:5002](http://localhost:5002/)—Prometheus[http://localhost:9090](http://localhost:9090/)—Grafana[http://localhost:3000](http://localhost:3000/)admin / admin

### 5\. Test a query

bash

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   curl -X POST http://localhost:5001/chat \    -H "Content-Type: application/json" \    -H "X-API-Key: $BACKEND_API_KEY" \    -d '{"question":"What are the grounds for eviction in Delhi?","jurisdiction":"delhi"}'   `

### 6\. Shut down

bash

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   docker compose down              # stop, keep volumes  docker compose down -v           # stop, remove volumes (destroys MLflow + Grafana state)   `

Environment Variables
---------------------

.env at the repo root:

env

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   # Embeddings (Hugging Face)  EMBEDDING_TOKEN=hf_...  HF_TOKEN=hf_...  MODEL_NAME=BAAI/bge-m3  # LLM provider — pick one  OPENAI_API_KEY=sk-...  RAG_LLM_MODEL=gpt-4o-mini  BACKEND_LLM_MODEL=gpt-4o-mini  # Alternative: Aion Labs (used for RAGAS judge)  AION_API_KEY=...  AION_MODEL_NAME=aion-labs/aion-2.0  AION_BASE_URL=https://api.aionlabs.ai/v1  # Auth  BACKEND_API_KEY=change_me_to_a_long_random_string  # MLflow  MLFLOW_TRACKING_URI=http://mlflow:5000  MLFLOW_EXPERIMENT_NAME=classifier  # Grafana  GRAFANA_USER=admin  GRAFANA_PASSWORD=change_me  # App  APP_ENV=development  LOG_LEVEL=INFO   `

**Never commit .env.** It's gitignored. Rotate any key that has ever been pasted into a terminal, chat, or issue.

Development Workflow
--------------------

### Run a single service locally

bash

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   docker compose up -d --build backend_api  docker compose logs -f backend_api   `

### Frontend dev server (hot reload)

bash

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   cd frontend  npm install  npm run dev          # http://localhost:5173, /api proxied to backend   `

### Rebuild only what changed

bash

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   docker compose up -d --build rag_api backend_api   `

The Dockerfiles use --mount=type=cache,target=/root/.cache/pip, so rebuilds after the first are ~2–4 minutes instead of 30+.

### Run tests

bash

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   pytest -q  ruff check .   `

### Validate Helm charts locally

bash

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   helm lint infra/helm/backend_api  helm template rentguard-backend-api infra/helm/backend_api \    -f infra/helm/backend_api/values-prod.yaml \    --set image.repository=example.com/rentguard-backend-api \    --set image.tag=test   `

### Validate Compose config

bash

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   docker compose config -q   `

Model Evaluation
----------------

### Classifier

Metrics from the last training run (metrics/eval\_metrics.json):

SplitMacro-F1AccuracyValidation0.7303—Test0.59670.6115

The val→test drop is driven by the High Risk class (val 0.74 → test 0.59) on a 20-example test slice. The promotion gate requires a **bootstrap 95% CI** improvement over the current champion before flipping the alias, precisely so single-number val scores don't drive promotion.

### RAG

RAGAS metrics scored against a golden set:

*   faithfulness — is the answer grounded in the retrieved context?
    
*   answer\_relevancy — does the answer address the question?
    
*   context\_precision / context\_recall — retrieval quality
    
*   p95\_latency\_ms — end-to-end latency budget
    

Thresholds live in ci-cd/eval/thresholds.yaml; regressions fail the PR.

Kubernetes Deployment
---------------------

Four independent Helm charts under infra/helm/. Each has its own values-prod.yaml for environment-specific overrides.

bash

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   # Configure kubectl for your EKS cluster  aws eks update-kubeconfig --name --region   # Deploy each service  helm upgrade --install rentguard-backend-api infra/helm/backend_api \    -f infra/helm/backend_api/values-prod.yaml \    --set image.repository=$ECR_REGISTRY/rentguard-backend-api \    --set image.tag=$GIT_SHA \    --namespace rentguard --atomic --timeout 10m   `

\--atomic means a failed rollout automatically reverts. In CI, the same command runs inside deploy.yml.

Security Posture
----------------

*   **Secrets never in source.** .env is gitignored; API keys read via os.getenv(); a startup check fails fast if BACKEND\_API\_KEY is unset (fail-closed auth, not fail-open).
    
*   **OIDC to AWS.** No long-lived IAM keys in GitHub.
    
*   **Image scanning on every build.** Trivy fs + image, pip-audit, gitleaks, all uploading SARIF to GitHub Security tab.
    
*   **Non-root containers** where the base image permits.
    
*   **Read-only volume mounts** for code and data in production compose (:ro).
    
*   **RFC 1123 compliance** for all Helm-rendered K8s object names.
    

Roadmap
-------

*   OCR pipeline for scanned PDFs (272 loaded, only 2 produced text — the rest are image-only)
    
*   Streaming responses via SSE (currently whole-answer)
    
*   Query cache for repeated questions
    
*   Fine-tune the classifier on a larger labeled set (target 0.75+ test macro-F1)
    
*   Multi-tenant auth (currently single shared API key)
    
*   Load testing with k6 to establish real p95 latency numbers at QPS
    
*   CloudWatch log shipping for EKS
