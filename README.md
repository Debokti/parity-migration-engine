# SCF parity workspace

This workspace demonstrates a framework-neutral parity workflow for migrating a
server-rendered JSP application to Angular without changing observable business
behavior.

## Architecture

- `contracts/` contains versioned JSON schemas and source-adapter examples.
- `legacy-jsp/` is the shared Java 17/Tomcat/H2 reference implementation.
- `target-angular/` is the migration target and calls the legacy API facade.
- `parity-engine/` owns capture, extraction, generation, replay, and diffing.
- `artifacts/` contains small committed examples; `runs/` is raw output and is
  intentionally ignored.

## Workflow

1. Start the legacy application and seed its deterministic database.
2. Capture golden traces with `parity-engine capture`.
3. Extract a `BehaviorSpec` from source and traces.
4. Generate or repair Angular features from that specification.
5. Replay traces against both applications and run `parity-engine prove`.

The verifier compares API payloads, validation outcomes, and selected state.
Agents are bounded by the contract schemas and must not edit verifier tests.

## Tool transparency and disclaimer

LLM providers and Modal are optional integrations. Provider selection is
explicit through environment variables; local deterministic code remains the
source of truth for comparisons. Example adapter files are illustrative only
and do not claim support for C# WebForms or COBOL/CICS.

