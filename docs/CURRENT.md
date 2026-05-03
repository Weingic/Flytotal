# Flytotal Current Entry

Last updated: 2026-05-01

## Current Working Version

- Branch: `feat/win-codex`
- Latest pushed checkpoint: `0114198 feat: add nodeb c3 uart dual-node test`
- Current focus: v5.2 direct-upgrade multimodal debug line.
- Current hardware test target: `NodeA + NodeB` (`ESP32-S3 + ESP32-C3`), not full `A1 + A2`.

## Where Things Live

- Firmware: `src/`, `include/`, `lib/`, `platformio.ini`
- Local tools and dashboard: `tools/`
- Documents and answer material: `docs/`
- Diagrams: `diagrams/`
- Standalone hardware demos: `examples/`
- Runtime outputs and evidence cache: `captures/`
- Future local model files: `models/` (ignored by Git)

## Read First

1. `docs/2026-04-29_v5_2_fusion_stage_v1.md`
2. `docs/2026-04-30_v5_2_algorithm_evidence_pack_v1.md`
3. `docs/2026-04-30_v5_2_defense_qa_v1.md`
4. `docs/2026-04-30_co_sensing_design_v1.md`
5. `docs/2026-04-30_nodea_nodeb_dual_node_execution_v1.md`
6. `docs/flytotal-v5.1-ld2451-nodeb-nodec-plan.md`

## Current Dual-Node Definition

The current hardware dual-node test means:

- `NodeA`: ESP32-S3 main sensing node.
- `NodeB`: ESP32-C3 auxiliary identity-chain and communication node.

The older `A1 + A2` wording means two complete sensing nodes and is kept as a future expansion/demo concept.

## Current Architecture Rule

Do not keep adding large algorithm logic directly to `src/main.cpp`.
v5.2 is now the default debug line: normal `pio run` builds the upgraded firmware, and missing hardware inputs must degrade to invalid/offline fields instead of blocking the main loop.

Current module homes:

- `lib/Fusion/`
- `lib/Ld2451Parser/`
- `lib/TrackManager/` for current multirotor scoring
- `lib/GimbalPredictor/`
- Future full handoff module: `lib/CoSensing/`

## Git Hygiene

Runtime files under `captures/` are outputs, not source. New local JSON/session/evidence/model files should stay ignored unless intentionally promoted into a curated doc or evidence sample.

Existing tracked capture history is kept for now. Do not mass-remove it during hardware联调.

## 给小白的解释

这是什么：这是打开仓库后最先看的入口页，告诉你当前主线到底是哪一版。

有什么用：避免再被 v1.0、v5.1、v5.2、A1+A2、NodeA+NodeB 这些名字绕晕。

你现在该怎么做：按 Read First 顺序先看 v5.2 四份文档，再开始接硬件和跑仿真。
