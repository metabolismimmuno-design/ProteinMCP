# VHH Max-Success Design Skill

> **Last updated:** 2026-04-14 — added `ibex_mcp` (L3.0 monomer sanity check), `iggm_mcp` (replaces `modal run modal_iggm.py` in Path C), `filter_dsasa.py` (L3.5b CDR3 interface filter), Protenix v2 note (L3.3).

Maximum-success-rate VHH (nanobody) de novo design pipeline. Combines 5 orthogonal generation tools, 4-model structure validation, strict developability funnel, and affinity maturation loop. Designed to maximize experimental hit rate when compute budget is not the primary constraint.

**Parallel to `nanobody_design.md`**: that skill is a single-path (BoltzGen) workflow; this skill is a multi-path pipeline for higher success rate.

---

## Prerequisites

Before running this workflow, install the skill and all required MCPs:

```bash
pskill install vhh_max_success_design
```

This will install the following MCP servers:
- `bindcraft_mcp` — BindCraft end-to-end binder design with AF2 validation
- `boltzgen_mcp` — BoltzGen all-atom generation (nanobody-anything protocol)
- `chai1_mcp` — Chai-1 structure prediction (validation model 1)
- `boltz2_mcp` — Boltz-2 structure prediction + affinity (validation model 2)
- `protenix_mcp` — Protenix structure prediction (validation model 3; **v2 default with `use_tfg_guidance=True` once weights re-open, currently v1**)
- `ibex_mcp` — VHH/Ab monomer structure prediction (L3.0 sanity check; replaces NanoBodyBuilder2; non-commercial license per `feedback_ibex_mcp.md`)
- `iggm_mcp` — IgGM epitope-conditioned CDR design (Path C; per `feedback_iggm_mcp.md`)
- `rfdiffusion2_mcp` — (NOT USED; listed here only to avoid accidental install; RFdiffusion v1 is used via modal script)
- `ligandmpnn_mcp` — ProteinMPNN sequence design (for RFdiffusion path)
- `stability_oracle_mcp` — ΔΔG mutation scanning
- `netMHCpan_mcp` — MHC-I immunogenicity scan (mandatory per `feedback_immunogenicity_check.md`)
- `netMHCIIpan_mcp` — MHC-II immunogenicity scan
- `protein-sol_mcp` — Solubility prediction
- `interpro` — Target domain annotation
- `mmseqs2` — Target MSA generation

**Non-MCP modal scripts used directly** (via `modal run`):
- `modal_germinal.py` — Germinal VHH de novo (germline-aware)
- `modal_rfdiffusion.py` — RFdiffusion v1 partial diffusion
- `modal_alphafold.py` — AF2 multimer (validation model 4)
- `modal_anarci.py` — IMGT/Kabat VHH numbering
- `modal_esm2_pll.py` — ESM2 sequence plausibility (PLL)
- `modal_esm2_predict_masked.py` — ESM2 masked residue suggestion (optional L5)
- `modal_mber.py` — MBER affinity maturation
- `modal_af2rank.py` — AF2Rank structural re-identification
- `modal_md_protein_ligand.py` — OpenMM MD for top candidates
- `modal_pdb2png.py` — PyMOL visualization for report

**Adaptyv skills referenced** (loaded on demand via `Skill` tool):
- `adaptyv:ipsae` — Binder ranking (L3.5)
- `adaptyv:foldseek` — Structural novelty check (L3 end)
- `adaptyv:protein-qc` — QC threshold defaults (all layers)
- `adaptyv:cell-free-expression` — L6 experimental planning
- `adaptyv:binding-characterization` — L6 SPR/BLI planning
- `adaptyv:pdb` / `adaptyv:uniprot` — L1 target fetching

**Global memory files this skill enforces**:
- `feedback_immunogenicity_check.md` — netMHCpan I+II mandatory before final ranking
- `domain_protein_design_gotchas.md` — rule #1 (CDR/FR inseparable), rule #2 (cross-model ipTM not comparable)
- `feedback_vhh_sequence_design.md` — MPNN choice on Layer 2 path E
- `feedback_ibex_mcp.md` — Ibex usage + non-commercial license caveat
- `feedback_iggm_mcp.md` — IgGM FASTA format + epitope conditioning
- `feedback_dsasa_filter.md` — CDR3 dSASA filter usage (L3.5b)

---

## Configuration Parameters

```yaml
# === Target ===
TARGET_CIF: "@inputs/target.cif"              # Target structure (CIF preferred)
TARGET_CHAIN: "A"                              # Chain to bind
EPITOPE_RESIDUES: "45,67,89,91,93"            # Epitope residues (author numbering)
HOTSPOT_RESIDUES: "67,89,91"                  # Subset for design conditioning (3-6)

# === VHH scaffolds (for BoltzGen and BindCraft paths) ===
VHH_SCAFFOLDS:
  - "@inputs/scaffolds/7eow.yaml"  # caplacizumab (approved)
  - "@inputs/scaffolds/7xl0.yaml"  # vobarilizumab
  - "@inputs/scaffolds/8coh.yaml"  # gefurulimab
  - "@inputs/scaffolds/8z8v.yaml"  # ozoralizumab

# === Output ===
RESULTS_DIR: "@results/vhh_max_success"       # Root output directory
JOB_NAME: "vhh_max_success"                   # Campaign name

# === Layer 2 generation counts ===
L2_BOLTZGEN_NUM_DESIGNS: 80                   # BoltzGen designs per scaffold
L2_BOLTZGEN_BUDGET: 2
L2_GERMINAL_TRAJECTORIES: 200
L2_GERMINAL_PASSING: 30
L2_IGGM_NUM_DESIGNS: 100
L2_BINDCRAFT_NUM_FINAL: 100
L2_RFDIFFUSION_BACKBONES: 500
L2_MPNN_SEQS_PER_BACKBONE: 8

# === Layer 3 validation ===
L3_MIN_MODELS_PASS: 3                         # Candidate must pass >=3 of 4 validation models
L3_IPSAE_TOP_FRAC: 0.5                        # Keep top 50% by ipSAE rank

# === Layer 4 thresholds (VHH-specific, borrow from adaptyv:protein-qc, calibrate after first run) ===
L4_PLDDT_MIN: 0.80                            # TODO: calibrate for VHH
L4_IPTM_MIN: 0.50                             # TODO: calibrate for VHH
L4_PAE_INTERFACE_MAX: 10                      # TODO: calibrate for VHH
L4_SCRMSD_MAX: 2.0                            # TODO: calibrate for VHH
L4_ESM_PLL_MIN_PERCENTILE: 50                 # TODO: calibrate for VHH
L4_PROTEIN_SOL_MIN: 0.45                      # TODO: calibrate for VHH
L4_STABILITY_DDG_MAX: 1.5                     # kcal/mol, positive = destabilizing
L4_MHC_RANK_THRESHOLD: 2.0                    # MHC rank % — above this = not strong binder (safe)

# === Layer 5 maturation ===
L5_MBER_TOP_N: 50                             # Top N from L4 enter MBER
L5_MD_TOP_N: 15                               # Top N after MBER re-validation enter MD

# === Execution mode ===
EXECUTION_MODE: "hybrid"                      # "parallel" | "serial" | "hybrid" — set at pre-flight
```

---

## Pre-flight: Execution Mode Selection

**Before running any step, ask the user which execution mode to use.**

**Prompt to user:**
> 在开始 5 层 pipeline 之前，需要你确认执行模式。三个选项：
>
> 1. **Full Parallel**（全并行）—— Layer 2 的 5 条生成路径同时提交到 Modal；Layer 3 的 4 个验证模型也同时提交。最大化墙钟时间效率，但 GPU 并发成本最高，调试难度大。
> 2. **Full Serial**（全串行）—— 每个工具依次提交，等前一个完成再启动下一个。最容易追踪错误和中间态，但墙钟时间最长（Layer 2 单阶段就可能数小时到半天）。
> 3. **Hybrid（推荐）** ✅ —— 按层级内/层级间区分：
>    - **Layer 2（生成）并行**：5 条路径独立无依赖，全部 `--detach` 并行提交
>    - **Layer 3（验证）并行**：4 个结构模型对同一候选池独立预测，全部并行
>    - **Layer 4（Developability 漏斗）串行**：漏斗顺序有强依赖（便宜过滤先行），每一步结果决定下一步输入，必须串行
>    - **Layer 5（成熟）串行**：MBER → 重验证 → 亲和力 → MD，每步依赖前步，必须串行
>
> **推荐选 3 (Hybrid)**。理由：L2/L3 并行能把 5 路径 + 4 模型的墙钟时间压到单路径水平；L4/L5 串行是逻辑必需（漏斗顺序+成熟回路）。Full Parallel 在 L4/L5 强行并行反而会制造无效计算，Full Serial 在 L2/L3 浪费时间。

**Implementation:** Set `EXECUTION_MODE` config based on user choice. Default to `hybrid` if user doesn't respond.

---

## Layer 1 — Target Preparation & Epitope Characterization

Goal: Produce target CIF, epitope residue list, 3–6 hotspots, glycan avoidance list, and competitive intelligence summary.

### Step 1.1 — Target structure & sequence

**Tools:** `adaptyv:pdb`, `adaptyv:uniprot`, `gget` skill

- Fetch target structure (CIF preferred, fallback PDB)
- Trim to binding region + 10 Å buffer
- Remove waters, ions, irrelevant ligands
- Extract sequence; verify chain boundaries

### Step 1.2 — Target domain annotation

**Tool:** `interpro` MCP (`analyze_protein_sequence`)

- Confirm epitope falls within the intended functional domain
- Check for disordered regions adjacent to epitope (unreliable for design)

### Step 1.3 — Target MSA & conservation

**Tool:** `mcp__mmseqs2__generate_msa`

- Generate MSA against UniRef
- Compute per-residue conservation
- Prefer hotspots with conservation score > 0.5 (more robust epitope)

### Step 1.4 — Glycan avoidance

**Tool:** `glycoengineering` skill

- Scan target for N-X-S/T sequons (X ≠ P)
- Flag sequons within epitope ± 8 residues
- Hotspot selection must avoid sequon vicinity (glycan occludes binding)

### Step 1.5 — Competitive intelligence

**Tools:** `claude_ai_PubMed`, `claude_ai_bioRxiv`, `claude_ai_Clinical_Trials`, `paper-lookup` skill

- Search for existing VHH/nanobody against target
- Check ClinicalTrials.gov for nanobody programs on this target
- Identify known epitopes and neutralization mechanisms
- Output: `inputs/competitive_landscape.md`

### Step 1.6 — Hotspot finalization

Combine conservation (1.3), glycan avoidance (1.4), competitive landscape (1.5), and epitope residues (config) → output `inputs/hotspots.json` with 3–6 residues. This feeds all Layer 2 paths.

---

## Layer 2 — Multi-Path Parallel Generation

**5 independent generation paths, all launched in parallel (hybrid mode).** Each produces candidates into `{RESULTS_DIR}/gen/<path>/`.

### Path A — BoltzGen `nanobody-anything` (Priority P1, validated)

**Tool:** `mcp__boltzgen_mcp__boltzgen_design`

- Input: target CIF + `VHH_SCAFFOLDS` (4 clinical scaffolds)
- Protocol: `nanobody-anything`
- `num_designs`: `L2_BOLTZGEN_NUM_DESIGNS` per scaffold
- Output: inverse-folded CIFs → `{RESULTS_DIR}/gen/boltzgen/`
- Post-filter: `modal_boltzgen.py` built-in cysteine filter

### Path B — Germinal VHH (Priority P1)

**Tool:** `modal run modal_germinal.py`

- Prerequisite: `germinal-models` Volume initialized (see `feedback_biomodals.md`)
- Build `inputs/germinal_target.yaml` with target PDB + epitope + hotspots
- Run: `--run-type vhh --max-trajectories L2_GERMINAL_TRAJECTORIES --max-passing-designs L2_GERMINAL_PASSING`
- Output: germline-aware VHH sequences + AF2 predictions → `{RESULTS_DIR}/gen/germinal/`

### Path C — IgGM epitope-conditioned design (Priority P2)

**Tool:** `mcp__iggm_mcp__iggm_design` (replaces direct `modal run modal_iggm.py` — gains pmcp job tracking)

- Input: VHH scaffold FASTA with `X` masking CDR1/2/3 positions (CDR1+2+3 全部重新设计，FR 保留)
- Antigen FASTA: last header specifies antigen chain ID and **must include full sequence body**, not empty header (踩坑见 `feedback_iggm_mcp.md`)
- Epitope conditioning: pass epitope residue list from Step 1.6 hotspots — this is the unique value of IgGM (RFdiffusion can't do epitope conditioning at sequence level)
- Samples: `L2_IGGM_SAMPLES` (gB demo: 5 samples ~10s each)
- Output: per-sample VHH PDBs → `{RESULTS_DIR}/gen/iggm/`

### Path D — BindCraft + VHH template partial hallucination (Priority P2)

**Tool:** `mcp__bindcraft_mcp__bindcraft_design`

- Input: target PDB + one VHH scaffold from `VHH_SCAFFOLDS` as starting template
- Target hotspots: `HOTSPOT_RESIDUES`
- `number_of_final_designs`: `L2_BINDCRAFT_NUM_FINAL`
- Filter option: standard (or `hard` for higher stringency)
- Output: AF2-validated CDR-hallucinated VHHs → `{RESULTS_DIR}/gen/bindcraft/`

### Path E — RFdiffusion v1 partial + ProteinMPNN (Priority P3)

**Tools:** `modal run modal_rfdiffusion.py` → `mcp__ligandmpnn_mcp__ligandmpnn_design`

**Step E1 — Backbone generation (RFdiffusion v1):**
- Use VHH scaffold as template for partial diffusion
- `--contigs` fixes FR1/FR2/FR3/FR4, rebuilds CDR1/2/3 loops
- Hotspot conditioning on target
- `L2_RFDIFFUSION_BACKBONES` backbones total

**Step E2 — Sequence design (ProteinMPNN, strict FR mode):**
- **Use ProteinMPNN (not SolubleMPNN)** per `feedback_vhh_sequence_design.md`
- `vhh_framework_mode: strict` to lock FR, design CDR only
- `num_seq_per_target: L2_MPNN_SEQS_PER_BACKBONE`
- Reason: CDR paratope needs aromatic/hydrophobic bias that SolubleMPNN strips away; solubility is filtered downstream in L4 via `protein-sol_mcp`

**Step E3 — Pool merge:**
- Output: ~4000 sequences → PLL pre-filter (see Step 4.2 early application) → ~500 → `{RESULTS_DIR}/gen/rfdiffusion/`

### Step 2.merge — Candidate pool consolidation

- Unify all 5 paths' outputs into a single candidate table: `{RESULTS_DIR}/gen/merged_pool.csv`
- Columns: `cand_id, source_path, sequence, structure_cif, source_job_id`
- Expected size: 1000–1500 candidates

---

## Layer 3 — 4-Model Orthogonal Structure Validation

**All 4 models run in parallel (hybrid mode) on the merged pool.** Absolute ipTM values are NOT compared — only rank agreement matters (per `domain_protein_design_gotchas.md` rule #2).

### Step 3.0 — Ibex VHH monomer sanity check (cheap pre-filter)

**Tool:** `mcp__ibex_mcp__ibex_predict`

- Goal: cheaply剔除明显坏 scaffold（畸形 CDR loop / 框架塌陷），省下 4 模型复合物预测的算力
- Input: each candidate VHH sequence as monomer (apo mode)
- Filter criteria:
  - CDR-H3 RMSD vs nearest germline reference > 4.0 Å → drop (loop 不收敛)
  - Overall pLDDT < 70 → drop (单体本身建模失败)
- Output: `{RESULTS_DIR}/val/ibex_monomer/sanity_pass.csv`
- License caveat: Ibex (Genentech/Prescient Design) is **non-commercial only** per `feedback_ibex_mcp.md`. For internal R&D use only; do not embed in商用产品输出
- Expected attrition: ~10–20% of merged pool drops here

### Step 3.1 — Chai-1 prediction

**Tool:** `mcp__chai1_mcp__chai1_predict`

- Input: merged pool CIFs or FASTA
- Output: `{RESULTS_DIR}/val/chai1/` with per-candidate ipTM, pLDDT, PAE

### Step 3.2 — Boltz-2 prediction

**Tool:** `mcp__boltz2_mcp__boltz2_predict_structure`

- Output: `{RESULTS_DIR}/val/boltz2/`

### Step 3.3 — Protenix prediction

**Tool:** `mcp__protenix_mcp__protenix_predict`

- **Version note (2026-04-14):** `modal_protenix.py` 已升级为 v2 默认 + `use_tfg_guidance=True`（Ab-Ag DockQ +9–13 pp, v2 5 seeds 超过 v1 1000 seeds）。当前 v2 权重被 ByteDance 临时下架（GitHub Issues #294/#296），脚本会回落 v1。权重重新开放后无需改 skill，自动切换。详见 `project_vhh_tool_upgrades.md` 对话 A
- Output: `{RESULTS_DIR}/val/protenix/`

### Step 3.4 — AlphaFold multimer prediction

**Tool:** `modal run modal_alphafold.py`

- Output: `{RESULTS_DIR}/val/af2m/`

### Step 3.5 — Rank consensus (ipSAE)

**Tool:** `adaptyv:ipsae` skill

- Compute ipSAE per model per candidate
- Require candidate passes `L3_MIN_MODELS_PASS` (default 3) of 4 models with ipSAE in top `L3_IPSAE_TOP_FRAC`
- **Do NOT compare ipTM/ipSAE absolute values across models** — only within-model ranks
- Output: `{RESULTS_DIR}/val/consensus_ranked.csv`

### Step 3.5b — CDR3 dSASA interface filter

**Tool:** `~/protein-design-utils/vhh/filter_dsasa.py` (BioPython Shrake-Rupley + cdr_boundaries; 零额外依赖)

- Goal: 剔除 CDR3 没真正参与界面的 candidate（结构看着像 binder，实际 CDR3 没贴上去）
- Input: 4-model 共识通过的 candidate CIFs（建议用 Chai-1 或 Boltz-2 输出，预测质量稳定）
- Compute: `dSASA_ratio` = (CDR3 SASA in apo − CDR3 SASA in complex) / CDR3 SASA in apo
- **Threshold (initial):** `L3_DSASA_RATIO_MIN = 0.25` — **TBD，待 gB-VHH campaign 反向校准**
  - 参考：gB-VHH Task 6 实测范围 0.147–0.578；seed_44 普遍高于 seed_43
- Drop candidates with dSASA_ratio < threshold
- 注意 FR3 motif：longcdr3 scaffold 是 `DRFTISRDNAK`（非标准 `GRFTISRDNAK`），`cdr_boundaries.py` regex 已放宽为 `[A-Z]RF[TN]ISRDNAK`，对所有 VHH scaffold 通用
- Output: `{RESULTS_DIR}/val/dsasa_filter_results.csv` + `consensus_ranked_dsasa.csv`
- 详见 `feedback_dsasa_filter.md`

### Step 3.6 — AF2Rank structural re-identification

**Tool:** `modal run modal_af2rank.py`

- Refold each candidate structure, verify it matches itself
- Drop candidates where AF2Rank identifies instability
- Output: `{RESULTS_DIR}/val/af2rank_filtered.csv`

### Step 3.7 — Novelty check (foldseek)

**Tool:** `adaptyv:foldseek` skill

- Query each surviving candidate against PDB + SAbDab
- **Drop candidates with TM-score > 0.7 to any known antibody structure** (avoid inadvertent copying of natural VHH)
- Output: `{RESULTS_DIR}/val/novel_candidates.csv`

### Layer 3 gate

Expected funnel: 1000–1500 → ~200–300 candidates enter Layer 4.

**Iteration loop 1:** If < 10% of pool survives Layer 3 across all 5 paths uniformly → hotspots likely wrong or epitope occluded. Return to Step 1.6, reselect hotspots, rerun Layer 2. **Do NOT** debug individual candidates in this failure mode.

---

## Layer 4 — Developability Funnel (SERIAL — order matters)

**Strictly serial**, cheap-first. Each step reads the previous step's output. Intermediate CSVs persisted between steps (format TBD — decide on first run).

### Step 4.1 — ANARCI numbering & framework integrity

**Tool:** `modal run modal_anarci.py`

- Scheme: IMGT (primary), Kabat (secondary check)
- Pass: numbering succeeds AND FR1/FR2/FR3/FR4 boundaries match the scaffold/template
- **Drop:** any candidate ANARCI fails to number, or FR region length deviates
- Expected reduction: 200–300 → ~180–250

### Step 4.2 — ESM2 PLL sequence plausibility

**Tool:** `modal run modal_esm2_pll.py`

- Compute length-normalized PLL
- Drop bottom `L4_ESM_PLL_MIN_PERCENTILE` (default: below median)
- Expected reduction: 180–250 → ~90–125

### Step 4.3 — Solubility

**Tool:** `mcp__protein-sol_mcp__protein_sol_solubility_predict`

- Drop candidates with score < `L4_PROTEIN_SOL_MIN`
- Expected reduction: 90–125 → ~70–100

### Step 4.4 — Stability Oracle ΔΔG scan

**Tool:** `mcp__stability_oracle_mcp__stability_oracle_predict`

- Mode: per-candidate ΔΔG at mutation hotspots (not full `--scan-all` — too expensive at this funnel stage)
- Drop candidates with any residue ΔΔG > `L4_STABILITY_DDG_MAX`
- Expected reduction: 70–100 → ~50–75

### Step 4.5 — Immunogenicity (MHC-I + MHC-II, MANDATORY)

**Tools:** `mcp__netMHCpan_mcp__predict_protein_epitopes`, `mcp__netMHCIIpan_mcp__predict_protein_epitopes`

**This step is non-optional per `feedback_immunogenicity_check.md`.**

- MHC-I: scan full VHH sequence against common HLA-A/B/C panel
- MHC-II: scan full VHH sequence against common HLA-DRB1 panel
- **Drop candidates with any strong binder (rank < `L4_MHC_RANK_THRESHOLD`) within CDR regions**
- Weak binders (rank 2–10%) in FR are tolerated
- Expected reduction: 50–75 → ~30–50

### Step 4.6 — De novo glycosylation sequon check

**Tool:** `glycoengineering` skill

- Scan designed VHH CDRs for newly-introduced N-X-S/T sequons not present in the original scaffold
- Drop candidates with new sequons in CDRs (glycans on paratope ruin affinity and add manufacturing risk)
- Expected reduction: 30–50 → ~25–40

### Layer 4 gate

Expected output: ~25–40 candidates → Layer 5.

---

## Layer 5 — Affinity Maturation & Final Selection (SERIAL)

### Step 5.1 — MBER affinity maturation

**Tool:** `modal run modal_mber.py`

- Input: top `L5_MBER_TOP_N` (default 50, clip to L4 output size if smaller) from Layer 4
- MBER runs ~91 iterations of logit optimization + semigreedy per candidate
- Output: affinity-matured sequences → `{RESULTS_DIR}/mature/mber/`
- **Cost note:** MBER is expensive (~30 min per candidate on H100). If L4 output > 30, prioritize by Layer 3 ipSAE rank consensus.

### Step 5.2 — MANDATORY L3 re-validation after MBER

**Re-run Steps 3.1–3.5 on MBER outputs.**

- Reason: MBER optimizes against AF2-multimer; Chai-1 / Boltz-2 / Protenix may disagree (`task09_1_summary.md` evidence: MBER AF2-top was Chai-1-bottom)
- If a matured candidate fails re-validation → revert to its pre-MBER version
- Output: `{RESULTS_DIR}/mature/revalidated.csv`

### Step 5.3 — Boltz-2 affinity prediction

**Tool:** `mcp__boltz2_mcp__boltz2_predict_affinity`

- Per-candidate KD estimate
- **Use for relative ranking, not absolute** (Boltz-2 affinity is still approximate)
- Output: `{RESULTS_DIR}/mature/affinity_ranked.csv`

### Step 5.4 — (Optional) ESM2 masked residue refinement

**Tool:** `modal run modal_esm2_predict_masked.py`

- For top 5 candidates, mask each CDR residue in turn
- If ESM2 strongly prefers a different residue (>3x over current), note as "ESM2 suggests X → Y"
- **Do not auto-apply** — flag for manual review; actual application requires another L3/L4 round
- Output: `{RESULTS_DIR}/mature/esm2_suggestions.csv`

### Step 5.5 — MD stability check on top candidates

**Tool:** `modal run modal_md_protein_ligand.py`

- Input: top `L5_MD_TOP_N` (default 15) VHH-target complexes
- 100 ns trajectory
- Metrics: RMSD (global & per-domain), RMSF per residue, interface contact persistence
- **Drop candidates where VHH unbinds or CDR3 shows RMSD > 3 Å from starting pose**
- Output: `{RESULTS_DIR}/mature/md_survivors.csv`

### Layer 5 gate

Expected final output: 10–20 candidates for experimental testing.

---

## Layer 6 — Experimental Planning & Reporting

### Step 6.1 — Cell-free expression planning (if applicable)

**Tool:** `adaptyv:cell-free-expression` skill

- Review top candidates for CFPS compatibility
- Flag disulfide-rich or aggregation-prone sequences
- Suggest DNA template design

### Step 6.2 — SPR/BLI experimental design

**Tool:** `adaptyv:binding-characterization` skill

- Platform selection (SPR vs BLI) based on expected KD range
- Surface chemistry and analyte flow parameters
- Kinetic vs affinity measurement strategy

### Step 6.3 — Report generation

**Tools:** `modal run modal_pdb2png.py`, `exploratory-data-analysis` skill

- Render top 10 VHH-target complexes as publication-quality PNGs
- Generate full funnel CSV: `{RESULTS_DIR}/final/funnel_full.csv` (every candidate across every layer)
- Generate top-table: `{RESULTS_DIR}/final/top_candidates.md` with sequence, L3 consensus rank, L4 developability flags, L5 affinity, MD survival, ESM2 suggestions

---

## Thresholds (VHH-specific, all marked TBD for calibration)

All Layer 3/4/5 thresholds in the config section above are **starting values borrowed from `adaptyv:protein-qc`**, not VHH-validated. After the first full campaign:

1. Collect the Layer 3 consensus ranks of candidates that experimentally bind (KD < 1 μM)
2. Collect the Layer 4 values of candidates that experimentally fail (no expression / aggregation / low Tm)
3. Update thresholds to maximize AUC for experimental success prediction
4. Record in `domain_protein_design_gotchas.md` if any threshold deviation is systematic (i.e., "for VHH, use pLDDT > 0.85 instead of 0.80")

Until calibrated, treat thresholds as soft filters — if a candidate misses one threshold by <10% but passes everything else, keep it in a "borderline" tier rather than dropping.

---

## Iteration Loops

**Loop 1 — Layer 3 fail → Layer 1 hotspot reselection**
- Trigger: < 10% of L2 pool passes L3 consensus (Step 3.5)
- Diagnosis: hotspots are buried/occluded, or epitope is wrong
- Action: Return to Step 1.6 (hotspot selection), not Layer 2 parameter tuning

**Loop 2 — Layer 5.2 fail after MBER → drop to pre-MBER version**
- Trigger: MBER-matured candidate fails 4-model re-validation
- Diagnosis: MBER overfit AF2 (known failure mode from HSV1 task09_1)
- Action: revert to pre-MBER candidate, do NOT tune MBER parameters

**Loop 3 — Layer 5.5 MD fail → flag CDR3 instability**
- Trigger: Candidate unbinds or CDR3 RMSF spikes in MD
- Diagnosis: static ipTM missed dynamic instability
- Action: Drop candidate. If >50% of top-N fail MD, reconsider whether L3 thresholds are too loose.

---

## Hard Constraints (non-negotiable)

1. **FR/CDR are jointly optimized** (`domain_protein_design_gotchas.md` #1): do not transplant CDRs across FRs. Use strict FR mode in Path E from the start.
2. **Cross-model ipTM is not comparable** (`domain_protein_design_gotchas.md` #2): Layer 3 consensus uses rank agreement, never absolute ipTM comparison across models.
3. **Immunogenicity scan is mandatory** (`feedback_immunogenicity_check.md`): Step 4.5 cannot be skipped for therapeutic VHH.
4. **ProteinMPNN not SolubleMPNN for VHH** (`feedback_vhh_sequence_design.md`): Path E uses ProteinMPNN full sequence + protein-sol downstream filter.
5. **MBER outputs MUST be re-validated** (Step 5.2): MBER's AF2-optimized outputs cannot bypass 4-model consensus.

---

## Troubleshooting

**Layer 2 generation failures:**
- BoltzGen CUDA version mismatch → see `feedback_biomodals.md` (PyTorch 2.11+cu126)
- Germinal volume missing → run `modal_setup_germinal_volume.py` first
- RFdiffusion DGL graphbolt error → already patched in `modal_rfdiffusion.py`

**Layer 3 validation inconsistency:**
- 4 models give wildly different ranks → expected cross-model variance, not a bug. Use consensus, don't debug individual model scores.
- Protenix times out → Protenix is slowest; increase timeout or accept 3/4 consensus

**Layer 4 funnel over-filtering:**
- <10 candidates reach Layer 5 → thresholds too strict, relax in order: ESM_PLL (4.2) first, then protein-sol (4.3), then pLDDT/ipTM (L3 gate)
- Never relax immunogenicity (4.5) or glycosylation (4.6)

**Layer 5 MBER all candidates fail re-validation:**
- MBER is overfitting AF2 → revert all to pre-MBER, skip MBER for this campaign, report Layer 4 survivors as final

---

## References

- BoltzGen: https://github.com/jwohlwend/boltzgen
- Germinal: https://github.com/... (internal biomodals wrapper)
- IgGM: biomodals wrapper only
- RFdiffusion v1: https://github.com/RosettaCommons/RFdiffusion
- ProteinMPNN: https://github.com/dauparas/ProteinMPNN
- MBER: biomodals wrapper (uses germinal-models Volume)
- ipSAE: adaptyv skill

---

## Cleanup

```bash
pskill uninstall vhh_max_success_design
```
