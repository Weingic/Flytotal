# Flytotal Current Entry

Last updated: 2026-04-30

## Current Working Version

- Branch: `feat/win-codex`
- Latest pushed checkpoint: `8508623 feat: add v5.1 nodeb ld2451 fusion fields`
- Current focus: v5.2 architecture cleanup and evidence-first multimodal upgrade.
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

1. `docs/2026-04-30_nodea_nodeb_dual_node_execution_v1.md`
2. `docs/flytotal-v5.1-ld2451-nodeb-nodec-plan.md`
3. `docs/2026-04-23_flytotal_guided_codewalk_01（全仓陪跑讲解01_总览与演进）.md`
4. `docs/2026-04-23_flytotal_guided_codewalk_02（全仓陪跑讲解02_固件主链）.md`
5. `docs/2026-04-23_flytotal_guided_codewalk_03（全仓陪跑讲解03_工具链与网页）.md`
6. `docs/2026-04-22_dual_node_demo_script_v2（双节点演示脚本V2）.md`

## Current Dual-Node Definition

The current hardware dual-node test means:

- `NodeA`: ESP32-S3 main sensing node.
- `NodeB`: ESP32-C3 auxiliary identity-chain and communication node.

The older `A1 + A2` wording means two complete sensing nodes and is kept as a future expansion/demo concept.

## Current Architecture Rule

Do not keep adding large algorithm logic directly to `src/main.cpp`.
New v5.2 capability should be isolated into modules under `lib/` first, then connected to `main.cpp` behind config gates.

Planned module homes:

- `lib/Fusion/`
- `lib/Ld2451Parser/`
- `lib/MultirotorFilter/`
- `lib/CoSensing/`

## Git Hygiene

Runtime files under `captures/` are outputs, not source. New local JSON/session/evidence/model files should stay ignored unless intentionally promoted into a curated doc or evidence sample.

Existing tracked capture history is kept for now. Do not mass-remove it during hardware联调.
