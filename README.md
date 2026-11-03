# Parity: The Deterministic AI Migration Engine

[![Parity Verification](https://img.shields.io/badge/Parity_Checks-699%2F699_Passed_(100%25)-success?style=for-the-badge&logo=checkmarx)](docs/INTERNAL_AUDIT_REPORT.md)
[![Meta Models](https://img.shields.io/badge/Meta_AI-Llama_3_%2F_Muse-blueviolet?style=for-the-badge&logo=meta)](https://ai.meta.com/)
[![Angular MFE](https://img.shields.io/badge/Target-Angular_17_MFE-DD0031?style=for-the-badge&logo=angular)](target-angular/)
[![Legacy Stack](https://img.shields.io/badge/Legacy-Tomcat_%2F_JSP-E67E22?style=for-the-badge&logo=apachetomcat)](legacy-jsp/)

> **Cerebral Valley / Meta Global AI Developer Hackathon — "Push the Frontier" Track**  
> *Transforming mission-critical enterprise legacy monoliths into modern Micro-Frontends while mathematically proving behavioral equivalence.*

---

## 🌟 The Vision

Enterprises spend over **\$1.5 Trillion** annually maintaining legacy software (JSP, Java Servlets, COBOL, ASP.NET WebForms). Rewrite initiatives fail **70% of the time** because generative AI assistants hallucinate state transitions, bypass security checks, and cannot prove behavioral parity.

**Parity** bridges the trust chasm. Powered by Meta AI models, Parity introduces a formal **Four-Phase Closed-Loop Methodology** that captures legacy ground truth, synthesizes formal behavior contracts, generates modern Angular Micro-Frontends, and deterministically proves 100% behavioral equivalence.

```
 ┌────────────────┐     ┌────────────────┐     ┌────────────────┐     ┌────────────────┐
 │   1. CAPTURE   │ ──> │   2. SPECIFY   │ ──> │   3. MIGRATE   │ ──> │    4. PROVE    │
 │ Golden HAR/DOM │     │ BehaviorSpec   │     │ Modern Ng17 MFE│     │ Deterministic  │
 │ Execution Trace│     │ JSON Contract  │     │ Webpack Fed.   │     │ 699/699 Checks │
 └────────────────┘     └────────────────┘     └────────────────┘     └────────────────┘
```

---

## 🚀 Key Achievements & Verification Metrics

* **699 / 699 Deterministic Checks Passed (100.0%)**: Comprehensive parity across all 6 enterprise scenarios.
* **Closed-Loop Verification Engine**: Headless Playwright automation comparing network payloads, status codes, DOM assertions, and database states.
* **4-Eyes Governance & Separation of Duties**: Fully verified multi-role approval workflow (`MAKER_1`, `CHECKER_1`, `CHECKER_2`).
* **Cross-Framework Auth Bridge**: Seamless HMAC-Bearer token synchronization with legacy `JSESSIONID` cookie sessions.
* **Parity Control Center GUI**: Zero-dependency browser interface with interactive AI Architect Chat, real-time verification scorecards, and diff inspectors.

---

## ⚡ Quick Start (Docker Compose)

Launch the entire ecosystem with a single command:

```bash
docker compose up --build
```

| Service | Port | Description |
| :--- | :---: | :--- |
| **Legacy Tomcat Monolith** | [`http://localhost:8080`](http://localhost:8080) | Java 17 / Jakarta JSP / H2 Reference Implementation |
| **Migrated Angular MFE** | [`http://localhost:4200`](http://localhost:4200) | Angular 17.3, AG Grid, Webpack Module Federation |
| **Parity Control Center GUI** | [`http://localhost:8501`](http://localhost:8501) | Browser GUI, AI Architect Chat, Live Verifier |

---

## 🛠️ Bare Metal Installation

If running without Docker:

### 1. Legacy Java Tomcat Server
```bash
cd legacy-jsp
mvn clean package
java -jar target/legacy-jsp-jar-with-dependencies.jar
# Running on http://localhost:8080
```

### 2. Migrated Angular Target
```bash
cd target-angular
npm install
npm start
# Running on http://localhost:4200
```

### 3. Parity Engine & Control Center GUI
```bash
cd parity-engine
python -m venv .venv
# Windows: .\.venv\Scripts\activate | Linux: source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Launch the Parity Control Center GUI:
python parity_cli.py gui --open
```

---

## 🖥️ Parity Control Center GUI (`:8501`)

The Control Center provides an end-to-end interface for evaluating migrations:

1. **Architect Chat**: Real-time Q&A powered by Meta models, grounded directly in formal specs and golden-trace digests (zero boilerplate, zero hallucination).
2. **Verify Studio**: 1-click Playwright replay and diff inspector across all 6 scenarios with pass/fail scorecards.
3. **Spec Extractor**: Inspect machine-generated `BehaviorSpec` contracts.
4. **Migrate Studio**: Review synthesized Angular components and Module Federation configs.
5. **Repair Loop**: Self-healing agent loop that reads test discrepancies and generates TypeScript fixes.
6. **Context Inspector**: Live model provider status and coexistence telemetry.

---

## 💻 Parity CLI Reference

Automate modernizations in your CI/CD pipelines:

```bash
# Display CLI help
python parity-engine/parity_cli.py --help

# Replay and verify all scenarios
python parity-engine/parity_cli.py verify --scenario scenario_1

# Ask the AI Architect a technical question
python parity-engine/parity_cli.py ask "Explain the 4-Eyes principle and how it works"

# Launch Control Center
python parity-engine/parity_cli.py gui --port 8501
```

---

## 📚 Detailed Documentation

* 📖 **[Product & Architecture Report](docs/PRODUCT_REPORT.md)**: In-depth technical architecture, problem statement, and component design.
* 🛠️ **[User & Operator Guide](docs/PARITY_USER_GUIDE.md)**: Step-by-step developer walkthrough, API reference, and troubleshooting guide.
* 🛡️ **[Internal E2E Audit Report](docs/INTERNAL_AUDIT_REPORT.md)**: Formal verification scorecard detailing all 699 checks across scenarios 1–6.

---

## 📄 License & Hackathon Submission

Developed for the **Cerebral Valley / Meta Global AI Developer Hackathon (2026)**.  
MIT License.
