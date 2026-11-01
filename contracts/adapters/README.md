# Source adapter contract

An adapter converts a source application and optional golden traces into the
framework-neutral `BehaviorSpec` contract. Implementations should be
deterministic, report parsing errors, and never silently invent rules.

