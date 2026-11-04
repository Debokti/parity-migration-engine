# Parity: The Deterministic AI Migration Engine

[![Parity Verification](https://img.shields.io/badge/Parity_Checks-699%2F699_Passed_(100%25)-success?style=for-the-badge&logo=checkmarx)](docs/INTERNAL_AUDIT_REPORT.md)
[![Meta Models](https://img.shields.io/badge/Meta_AI-Llama_3_%2F_Muse-blueviolet?style=for-the-badge&logo=meta)](https://ai.meta.com/)
[![Angular MFE](https://img.shields.io/badge/Target-Angular_17.3_MFE-DD0031?style=for-the-badge&logo=angular)](target-angular/)
[![Legacy Stack](https://img.shields.io/badge/Legacy-Tomcat_9.0.98_%2F_JSP-E67E22?style=for-the-badge&logo=apachetomcat)](legacy-jsp/)

> **Cerebral Valley / Meta Global AI Developer Hackathon — "Push the Frontier" Track**  
> *Transforming mission-critical enterprise legacy monoliths into modern Micro-Frontends while mathematically proving behavioral equivalence.*

---

## 🤖 Tri-Model Enterprise AI Architecture

Parity orchestrates three specialized Meta AI model endpoints across each stage of the modernization lifecycle:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   PARITY TRI-MODEL ORCHESTRATION                                │
├───────────────────────────────┬─────────────────────────────────┬───────────────────────────────┤
│ 1. Spec Extraction & Q&A     │ 2. Modern Component Synthesis   │ 3. Self-Healing Repair        │
│ Meta AI (`muse-spark-1.3`)    │ Fireworks AI (`muse-spark-open`)│ Baseten Enclave (`muse-1026`) │
│ Behavioral contracts & bounds │ Angular 17.3 MFE & Webpack MF   │ Deterministic TypeScript fixes│
└───────────────────────────────┴─────────────────────────────────┴───────────────────────────────┘
```

* **Meta (`muse-spark-1.3`) — Specification & Architect Q&A (`extract`, `ask`)**: Analyzes legacy execution traces, extracts formal `BehaviorSpec` JSON contracts, and powers the hallucination-free AI Architect chat.
* **Fireworks AI (`muse-spark-open`) — Code Synthesis (`migrate`)**: Generates standalone Angular 17.3 Micro-Frontend components, AG Grid table models, and Webpack Module Federation manifests.
* **Baseten Enclave (`meta-models/muse-spark-open-1026`) — Component Repair (`repair`)**: Ingests automated Playwright trace diffs and generates surgical TypeScript/HTML patches to heal behavioral drift.

---

## 🌟 The Core Problem & Closed-Loop Methodology

Enterprises spend over **\$1.5 Trillion** annually maintaining brittle legacy monoliths (Java Servlets, JSPs, Struts, COBOL). Manual and LLM rewrites fail **70% of the time** because generative models hallucinate state transitions, bypass security checks, and cannot mathematically prove behavioral parity.

Parity solves this through a formal **Four-Phase Closed-Loop Methodology**:

```
 ┌────────────────┐     ┌────────────────┐     ┌────────────────┐     ┌────────────────┐
 │   1. CAPTURE   │ ──> │   2. SPECIFY   │ ──> │   3. MIGRATE   │ ──> │    4. PROVE    │
 │ Golden HAR/DOM │     │ BehaviorSpec   │     │ Modern Ng17 MFE│     │ Deterministic  │
 │ Execution Trace│     │ JSON Contract  │     │ Webpack Fed.   │     │ 699/699 Checks │
 └────────────────┘     └────────────────┘     └────────────────┘     └────────────────┘
```

### 1. Capture (Behavioral Ground Truth)
Instruments the legacy application during runtime and captures multi-modal **Golden Execution Traces** (`artifacts/golden-traces/scenario_*.json`), recording HTTP requests, responses, session cookies (`JSESSIONID`), DOM snapshots, and database mutations.

### 2. Specify (Formal Contract Extraction)
Extracts formal `BehaviorSpec` schemas (`contracts/schemas/behavior-spec.v1.json`) locking in domain invariants using `BigDecimal` `ROUND_HALF_UP` financial rules:
* **Advance Cap**:
  $$\text{maxAdvanceable} = \text{round\_half\_up}\left(\sum(\text{selectedInvoices}) \times 0.85, 2\right)$$
* **Discount Fee**:
  $$\text{discountFee} = \text{round\_half\_up}\left(\text{requestedAmount} \times 0.06 \times \frac{\text{tenorDays}}{360}, 2\right)$$
* **Processing Fee**: Fixed $\$50.00$.
* **Net Payout**:
  $$\text{netPayout} = \text{requestedAmount} - \text{discountFee} - \text{processingFee}$$
* **Idempotency Token**: Unique UUID generated on `/review` entry to prevent double-drawdown fraud.

### 3. Migrate (Targeted Angular MFE Generation)
Synthesizes standalone Angular 17.3 components with Module Federation (`target-angular/`):
* **AG Grid Invoice Explorer**: Multi-select invoice ledger with client-side sorting and status filters.
* **Dual-State Attachment Staging**: Visual document staging area with preview modal and staged delete capabilities before final commitment.
* **Maker-Checker Security Lock**: Freezes uploaded files and prevents maker tampering once drawdown enters approval stages.
* **Micro-Frontend (MFE) Coexistence**: Embeds seamlessly into the legacy JSP wrapper via custom element `<scf-drawdown-mfe>` or iframe bridge with bi-directional postMessage sync.

### 4. Prove (Deterministic Replay & Parity Diffing)
Drives headless Playwright browsers through identical user journeys against both legacy and modern targets, normalizing volatile nonces/timestamps and performing strict equivalence diffing.

---

## 🛡️ Enterprise Governance & Security Verification

### 4-Eyes Principle & Separation of Duties (SoD)
Financial regulations require that no single user can create and approve a disbursement:
1. **Creation / Amendment**: Initiated by `maker-1` (`MAKER_1`). Approval stage set to `PENDING_CHECKER_1`.
2. **First Checker Gate**: Must be approved by `CHECKER_1`. Rejects if `actorId == createdBy` or `actorId == amendedBy` with `HTTP 400: Maker cannot act as First Checker`. Advances stage to `PENDING_CHECKER_2`.
3. **Second Checker Gate**: Must be approved by `CHECKER_2`. Rejects if `actorId` matches Maker or Checker 1 with `HTTP 400: Second Checker must be distinct from Maker and First Checker`. Advances status to `APPROVED`.

### Auth-Bridge & Session Synchronization
* Binds legacy `JSESSIONID` cookies to HMAC-SHA256 Bearer tokens via `GET /api/v1/auth/bridge`.
* Continuous keep-alive via `POST /api/v1/auth/heartbeat`, ensuring zero session dropouts during MFE interactions.
* Anti-cache headers (`no-cache, no-store, must-revalidate`) enforced on all mutation endpoints.

---

## ⚡ Quick Start

### Option A: Docker Compose (Recommended)
Launch the entire tri-service ecosystem in one command:
```bash
docker compose up --build
```

| Service | Port | Description |
| :--- | :---: | :--- |
| **Legacy Tomcat Monolith** | [`http://localhost:8080`](http://localhost:8080) | Java 17 / Embedded Tomcat 9 / H2 Database |
| **Migrated Angular MFE** | [`http://localhost:4200`](http://localhost:4200) | Angular 17.3, AG Grid, Webpack Module Federation |
| **Parity Control Center GUI** | [`http://localhost:8501`](http://localhost:8501) | Browser GUI, AI Architect Chat, Live Verifier |

### Option B: Bare-Metal Setup

#### 1. Legacy Java Tomcat Server
```bash
cd legacy-jsp

# Start the server (1-click script):
# On Windows:      .\start_backend.bat
# On Linux/macOS:  ./start_backend.sh

# Or start via raw Java:
# Windows (PowerShell / CMD - semicolon ';'): java -cp "target/classes;target/lib/*" com.scf.config.ServerMain
# Linux / macOS (terminal - colon ':'):       java -cp "target/classes:target/lib/*" com.scf.config.ServerMain
# Server running on http://localhost:8080
```

#### 2. Migrated Angular Target
```bash
cd target-angular
npm install
npm start
# Server running on http://localhost:4200
```

#### 3. Parity Engine & Control Center GUI
```bash
cd parity-engine
python3 -m venv .venv
# On Windows: .\.venv\Scripts\activate  |  On macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Launch the Parity Control Center GUI:
python parity_cli.py gui --host 0.0.0.0 --port 8501 --open
```

### Option C: 1-Click Verification Script (Zero Setup)
Replays the full 6-scenario verification suite and queries the Meta AI Architect in a single command without Docker:
* **macOS / Linux:** `./run_demo.sh` (or `bash run_demo.sh`)
* **Windows (PowerShell):** `.\run_demo.ps1`

---

## 🖥️ Parity Control Center GUI (`:8501`)

The Control Center provides an all-in-one browser interface for migration observability:
* **Architect Chat**: Conversational AI interface grounded directly in `drawdown-spec.json` and golden traces.
* **Verify Studio**: 1-click Playwright replay and diff inspector across all 6 scenarios with pass/fail scorecards.
* **Extract**: Synthesizes formal `BehaviorSpec` JSON contracts from recorded traces.
* **Migrate**: Generates modern Angular components and Module Federation configs.
* **Repair**: Self-healing feedback loop generating atomic fixes for behavioral discrepancies.
* **Context**: Telemetry view displaying active Meta model providers and live scenario check totals.

---

## 💻 Parity CLI Reference

All workflows are fully scriptable for CI/CD pipelines:

| Command | Usage | Description |
| :--- | :--- | :--- |
| `extract` | `python parity-engine/parity_cli.py extract [--trace TRACE]` | Extract BehaviorSpec from legacy trace |
| `migrate` | `python parity-engine/parity_cli.py migrate [--spec SPEC]` | Generate modern Angular MFE components |
| `verify` | `python parity-engine/parity_cli.py verify --scenario <name>`| Deterministic Playwright replay & diff |
| `repair` | `python parity-engine/parity_cli.py repair --diff DIFF` | Generate TypeScript repair from diff report |
| `ask` | `python parity-engine/parity_cli.py ask "<question>"` | Grounded technical Q&A with AI Architect |
| `gui` | `python parity-engine/parity_cli.py gui [--port 8501]` | Launch the browser Control Center GUI |

---

## 📊 Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Legacy Stack** | Java 17, Apache Tomcat 9.0.98 (Embedded), Javax Servlet/JSP, H2 In-Memory DB, Maven |
| **Modern Target** | Angular 17.3, TypeScript 5.4, AG Grid 31, Webpack Module Federation, RxJS |
| **Parity Engine** | Python 3.11+, Playwright Chromium, Meta Llama 3 / Muse Models, Pytest |
| **Control Center GUI**| Embedded Dark/Light SPA, Vanilla JS (zero external CDN dependencies) |
| **Containers & CI** | Docker, Docker Compose, Multi-stage builds |

---

## 📚 Audit & Verification Proof

For the complete scenario-by-scenario verification matrix and compliance proofs:
👉 **[Read the Full Verification & Governance Proof Report (699/699 Checks)](docs/INTERNAL_AUDIT_REPORT.md)**

---

## 📄 License & Hackathon Submission

Developed for the **Cerebral Valley / Meta Global AI Developer Hackathon (2026)**.  
MIT License.