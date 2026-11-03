# Parity Migration Engine: User & Operator Guide

**Audience:** Hackathon Evaluators, DevOps Engineers, and Enterprise Architects  
**Repository:** `Debokti/parity-migration-engine`  

---

## 1. Quick Start (Zero to Parity in 2 Minutes)

### Prerequisites
* **Python 3.11+**
* **Java 17 JDK & Maven 3.9+** (or use Docker)
* **Node.js 18+ & npm 9+**
* **Google Chrome / Playwright Chromium**

### Environment Configuration
Copy the template and verify your Meta model or provider key:
```bash
cp .env.example .env
```
*(Deterministic verification functions offline without any external keys. LLM keys are only required for the interactive Architect Chat and code synthesis).*

---

## 2. Running via Docker Compose (Recommended)

To launch the complete tri-service architecture in one command:
```bash
docker compose up --build
```

**Services Started:**
* **Legacy Tomcat Server**: `http://localhost:8080`
* **Modern Angular MFE**: `http://localhost:4200`
* **Parity Control Center GUI**: `http://localhost:8501`

---

## 3. Running Locally on Bare Metal

### Terminal 1: Launch Legacy Java Tomcat Server
```bash
cd legacy-jsp
mvn clean package
java -jar target/legacy-jsp-jar-with-dependencies.jar
# Server running on http://localhost:8080
```

### Terminal 2: Launch Target Angular Modern Application
```bash
cd target-angular
npm install
npm start
# Server running on http://localhost:4200
```

### Terminal 3: Launch Parity Engine & Control Center GUI
```bash
cd parity-engine
python -m venv .venv
# Windows: .\.venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Launch the browser Control Center GUI:
python parity_cli.py gui --host 0.0.0.0 --port 8501 --open
```

---

## 4. Control Center GUI Usability Guide

Open your browser to **`http://localhost:8501`**. The Control Center provides 6 distinct workspaces:

```
[Parity Control Center]   [Provider: meta (muse-spark-1.3)]   [Theme: Dark/Light]
--------------------------------------------------------------------------------
[Architect Chat]  [Verify]  [Extract]  [Migrate]  [Repair]  [Context]
```

### 4.1 Architect Chat (`#v-chat`)
* **What it does**: Ask deep architecture, regulatory compliance, or code modernization questions.
* **Grounding Guarantee**: Responses are strictly grounded in `drawdown-spec.json`, parity test reports, and golden-trace digests.
* **Quick Chips**: Click any prompt chip to immediately ask about:
  * *JSESSIONID <-> Bearer token synchronization*
  * *Overall Parity Scorecard across Scenarios 1-6*
  * *4-Eyes Maker/Checker governance proofs*

### 4.2 Verify Studio (`#v-verify`)
* **What it does**: Deterministically replays golden traces against the live Angular application and executes the diffing engine in real time.
* **How to use**:
  1. Select a scenario from the dropdown (e.g. `scenario_6 (Governance)`).
  2. Click **Run Verification** (or toggle **Run all 6 scenarios**).
  3. Inspect the live scorecard: PASS / FAIL status, match percentage, and expandable trace diff logs.

### 4.3 Extract (`#v-extract`)
* **What it does**: Synthesizes a formal `BehaviorSpec` contract from recorded legacy HTTP and DOM traces.
* Click **Extract Spec** to view the resulting JSON schema mapping domain invariants.

### 4.4 Migrate (`#v-migrate`)
* **What it does**: Generates modern Angular components directly from a `BehaviorSpec`.
* Click **Generate Components** to view the generated component files, templates, and Module Federation manifests.

### 4.5 Repair (`#v-repair`)
* **What it does**: Automated feedback loop. Reads discrepancy logs from a failed verify run and generates an atomic TypeScript/HTML patch to fix the modern component.

### 4.6 Context (`#v-context`)
* **What it does**: Audit and observability view displaying active Meta model providers, scenario digests, and coexistence build evidence.

---

## 5. Parity CLI Reference

All GUI functionality is accessible via the CLI for CI/CD automation:

```bash
# Display help and subcommands
python parity_cli.py --help

# Replay and verify Scenario 1 (Standard Flow)
python parity_cli.py verify --scenario scenario_1

# Replay and verify Scenario 6 (4-Eyes Governance)
python parity_cli.py verify --scenario scenario_6

# Ask the AI Architect a question via terminal
python parity_cli.py ask "Explain the 4-eyes principle and how it works"

# Extract contract specification from golden trace
python parity_cli.py extract --trace ../artifacts/golden-traces/scenario_1.json

# Launch the Web GUI Control Center
python parity_cli.py gui --port 8501
```

---

## 6. Troubleshooting & Diagnostics

| Symptom | Cause | Solution |
| :--- | :--- | :--- |
| **Port 8501 already in use** | Zombie Python process from previous run | Run `Stop-Process -Name python` (PowerShell) or `fuser -k 8501/tcp` (Linux). |
| **Playwright viewport error** | Target element scrolled out of viewport | Ensure latest CSS is loaded (`target-angular/src/app/drawdown/drawdown.component.css`). |
| **Backend reset failed during verify** | Legacy Tomcat server is not running | Ensure `localhost:8080` is up (`mvn exec:java` or Docker). |
| **MFE popup blocked** | Browser popup blocker enabled | Allow popups for `localhost:8080` in Chrome settings. |
