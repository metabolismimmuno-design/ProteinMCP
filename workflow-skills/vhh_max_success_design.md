---
name: vhh-max-success-design
description: Maximum-success-rate VHH (nanobody) de novo design pipeline. 4 orthogonal generation paths (BoltzGen nanobody-anything, Germinal, IgGM, RFdiffusion+AbMPNN; BindCraft excluded — not VHH-specific), 2-model or 4-model structure validation (Chai-1+AF2m recommended 2-model), developability funnel (ANARCI, protein-sol, AbMPNN scoring, Stability Oracle, netMHCpan I+II, glycosylation), and affinity maturation with MBER. Parallel to nanobody_design skill; use this when success rate matters more than compute cost.
---

# VHH Max-Success Design Skill

> **Last updated:** 2026-04-15 — (10) Scaffold 库升级：从 4 → 8 临床代表（TheraSAbDab + Evers et al. mAbs 2025 文献挖掘，含 Netakimab/Porustobart/Erfonrilimab 新增；中央库 `~/protein-design-utils/vhh/scaffolds/`，胚系 IGHV3-23/IGHV3-7，人源化 71–85%）。(9) L3 结构预测模式重构：新增"2-model vs 4-model"选择决策提示；明确 AF3 家族（Chai-1/Boltz-2/Protenix）误差相关性高、AF2m 正交性最强；推荐默认 2-model = Chai-1 + AF2m（Protenix v2 上线后升级为 ①）；共识阈值随模式调整（2/2 vs 3/4）。(8) 冗余修复：① Step 2.dedup 删除错误 MMseqs2 MCP 引用；② Step 3.6 AF2Rank 条件逻辑改为"AF2m 默认运行 → 总是免费复用"；③ Step 1.4/4.6 glycoengineering 加 input 标注；④ "5路径" → "4路径"；⑤ L4.3 AbMPNN 取消 Path D 复用 D2 分数捷径，4 路径统一在 L3 复合物结构重打分。(7) Path D (BindCraft) 移出主流程：BindCraft 是通用蛋白 binder 工具，非 VHH 专用；Path B (Germinal) 是抗体优化版替代，4 路径降为标准。(1) L3.0 Ibex 改 `ibex_predict_batch`; (2) L4 顺序调整（protein-sol 升至 4.2，AbMPNN 降至 4.3）; (3) Step 2.dedup MMseqs2 去重; (4) Step 2.diversity 5路径多样性诊断 → 4路径; (5) Track B 三档距离判定 + 两条自动召回规则; (6) 阈值 Tier1/Tier2 分层校准. Previous: L4.2 ESM PLL → AbMPNN scoring; L3.6 AF2Rank CONDITIONAL.

Maximum-success-rate VHH (nanobody) de novo design pipeline. Combines **4 orthogonal generation tools** (BoltzGen / Germinal / IgGM / RFdiffusion+AbMPNN), 4-model structure validation, strict developability funnel, and affinity maturation loop. Designed to maximize experimental hit rate when compute budget is not the primary constraint.

> **BindCraft 不在此 pipeline：** BindCraft 是通用蛋白 binder 工具（hallucination-based），不具备 VHH 特异性（无 IMGT FR 感知、无 germline 约束）。Germinal (Path B) 是更适合抗体的替代方案。如需 BindCraft 做通用蛋白设计，使用 `adaptyv:bindcraft` skill。

**Parallel to `nanobody_design.md`**: that skill is a single-path (BoltzGen) workflow; this skill is a multi-path pipeline for higher success rate.

---

## Prerequisites

Before running this workflow, install the skill and all required MCPs:

```bash
pskill install vhh_max_success_design
```

This will install the following MCP servers:
- `bindcraft_mcp` — (**NOT USED in VHH pipeline**; BindCraft is a general protein binder tool, use `adaptyv:bindcraft` skill instead)
- `boltzgen_mcp` — BoltzGen all-atom generation (nanobody-anything protocol)
- `chai1_mcp` — Chai-1 structure prediction (validation model 1)
- `boltz2_mcp` — Boltz-2 structure prediction (validation model 2; affinity module not used — not validated for VHH-antigen interfaces)
- `protenix_mcp` — Protenix structure prediction (validation model 3; **v2 default with `use_tfg_guidance=True` once weights re-open, currently v1**)
- `ibex_mcp` — VHH/Ab monomer structure prediction (L3.0 sanity check; replaces NanoBodyBuilder2; non-commercial license per `feedback_ibex_mcp.md`)
- `iggm_mcp` — IgGM epitope-conditioned CDR design (Path C; per `feedback_iggm_mcp.md`)
- `rfdiffusion2_mcp` — (NOT USED; listed here only to avoid accidental install; RFdiffusion v1 is used via modal script)
- `ligandmpnn_mcp` — AbMPNN sequence design for VHH (checkpoint: `abmpnn` via ligandmpnn_mcp infrastructure; fallback: `proteinmpnn_v_48_020`)
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
- `modal_esm2_pll.py` — ~~ESM2 sequence plausibility (PLL)~~ **(deprecated in L4.2; replaced by AbMPNN scoring mode — see Step 4.2)**
- `modal_esm2_predict_masked.py` — ESM2 masked residue suggestion (optional L5)
- `modal_mber.py` — MBER affinity maturation
- `modal_af2rank.py` — AF2Rank structural re-identification
- `modal_pdb2png.py` — PyMOL visualization for report

**Adaptyv skills referenced** (loaded on demand via `Skill` tool):
- `adaptyv:ipsae` — Binder ranking (L3.5)
- `adaptyv:foldseek` — IP / structural similarity annotation (L3 end; annotate `ip_risk`, do not auto-drop)
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

# === VHH scaffolds (for BoltzGen + IgGM + RFdiffusion paths) ===
# 中央库: ~/protein-design-utils/vhh/scaffolds/yaml/
# 来源: TheraSAbDab v19 + Evers et al. mAbs 2025 文献挖掘
# 结构聚类 (d=0.25, Cα RMSD + seqid 组合) 选 8 个代表，覆盖 2 个主要胚系
# 启动新靶点前 cp ~/protein-design-utils/vhh/scaffolds/yaml/*.yaml inputs/scaffolds/
VHH_SCAFFOLDS:
  # IGHV3-23 胚系 (人源化 77-85%, 适合大多数靶点)
  - "@inputs/scaffolds/8z8m_B.yaml"  # Ozoralizumab/TNF  | Approved | 84.7% | CDR3=10aa
  - "@inputs/scaffolds/7dv4_B.yaml"  # Porustobart/CTLA4 | Phase-II | 82.5% | CDR3=13aa
  - "@inputs/scaffolds/7a6o_B.yaml"  # Caplacizumab/VWF  | Approved | 77.5% | CDR3=21aa (长CDR3)
  - "@inputs/scaffolds/6rqm_B.yaml"  # Erfonrilimab/CTLA4| Phase-III| 78.6% | CDR3=11aa
  # IGHV3-7 胚系 (人源化 72-79%, CDR3 多样性更强)
  - "@inputs/scaffolds/7xl0_A.yaml"  # Vobarilizumab/ALB | Phase-II | 79.4% | CDR3=15aa
  - "@inputs/scaffolds/7xl0_B.yaml"  # Vobarilizumab/IL6R| Phase-II | 79.0% | CDR3=15aa
  - "@inputs/scaffolds/8coh_A.yaml"  # Gefurulimab/C5    | Phase-III| 76.5% | CDR3=19aa
  - "@inputs/scaffolds/8b7w_H.yaml"  # Netakimab/IL17A   | Approved | 72.5% | CDR3=18aa

# === Output ===
RESULTS_DIR: "@results/vhh_max_success"       # Root output directory
JOB_NAME: "vhh_max_success"                   # Campaign name

# === Layer 2 generation counts ===
L2_BOLTZGEN_NUM_DESIGNS: 80                   # BoltzGen designs per scaffold
L2_BOLTZGEN_BUDGET: 2
L2_GERMINAL_TRAJECTORIES: 200
L2_GERMINAL_PASSING: 30
L2_IGGM_NUM_DESIGNS: 100
L2_RFDIFFUSION_BACKBONES: 500
L2_MPNN_SEQS_PER_BACKBONE: 8

# === Layer 2.5 hotspot pre-screen ===
L2P5_HOTSPOT_MIN_CONTACTS_TRACK_A: 2  # Track A (on-target)：进入主 L3 验证池（gB-VHH N=200 伪AUC校准 2026-04-15）
L2P5_HOTSPOT_MIN_CONTACTS_TRACK_B: 0  # Track B (alt-epitope)：contacts=0 但 ipTM 高 → 表位分析子流程
L2P5_DISTANCE_THRESHOLD: 8.0          # 接触判定距离阈值（Å）

# === Layer 3 validation ===
L3_MIN_MODELS_PASS: 3                         # Candidate must pass >=3 of 4 validation models
L3_MIN_MODELS_PASS_IGGM: 2                   # IgGM path: relaxed threshold (out-of-distribution conformation tolerance)
L3_IPSAE_TOP_FRAC: 0.5                        # Keep top 50% by ipSAE rank

# === Layer 4 thresholds (VHH-specific, borrow from adaptyv:protein-qc, calibrate after first run) ===
L4_PLDDT_MIN: 0.80                            # TODO: calibrate for VHH
L4_IPTM_MIN: 0.9175                           # gB-VHH N=200 伪AUC校准 2026-04-15, AUC=0.752, J=0.408
L4_PAE_INTERFACE_MAX: 10                      # TODO: calibrate for VHH
L4_SCRMSD_MAX: 2.0                            # TODO: calibrate for VHH
L4_ABMPNN_LL_MIN_PERCENTILE: 50               # AbMPNN log-likelihood percentile cutoff (Step 4.3); TODO: calibrate for VHH
L4_PROTEIN_SOL_MIN: 0.45                      # TODO: calibrate for VHH
L4_STABILITY_DDG_MAX: 1.5                     # kcal/mol, positive = destabilizing
L4_MHC_RANK_THRESHOLD: 2.0                    # MHC rank % — above this = not strong binder (safe)
L4_PARETO_MAX_RANK: 2                         # Keep candidates on Pareto front 1 and 2; raise to 3 if <10 survive

# === Layer 5 maturation ===
L5_MBER_TOP_N: 50                             # Top N from L4 enter MBER

# === Execution mode ===
EXECUTION_MODE: "hybrid"                      # "parallel" | "serial" | "hybrid" — set at pre-flight
```

---

## Pre-flight: Execution Mode Selection

**Before running any step, ask the user which execution mode to use.**

**Prompt to user:**
> 在开始 5 层 pipeline 之前，需要你确认执行模式。三个选项：
>
> 1. **Full Parallel**（全并行）—— Layer 2 的 4 条生成路径同时提交到 Modal；Layer 3 的 4 个验证模型也同时提交。最大化墙钟时间效率，但 GPU 并发成本最高，调试难度大。
> 2. **Full Serial**（全串行）—— 每个工具依次提交，等前一个完成再启动下一个。最容易追踪错误和中间态，但墙钟时间最长（Layer 2 单阶段就可能数小时到半天）。
> 3. **Hybrid（推荐）** ✅ —— 按层级内/层级间区分：
>    - **Layer 2（生成）并行**：4 条路径独立无依赖，全部 `--detach` 并行提交
>    - **Layer 3（验证）并行**：4 个结构模型对同一候选池独立预测，全部并行
>    - **Layer 4（Developability 漏斗）串行**：漏斗顺序有强依赖（便宜过滤先行），每一步结果决定下一步输入，必须串行
>    - **Layer 5（成熟）串行**：MBER → 重验证 → 亲和力 → MD，每步依赖前步，必须串行
>
> **推荐选 3 (Hybrid)**。理由：L2/L3 并行能把 4 路径 + 4 模型的墙钟时间压到单路径水平；L4/L5 串行是逻辑必需（漏斗顺序+成熟回路）。Full Parallel 在 L4/L5 强行并行反而会制造无效计算，Full Serial 在 L2/L3 浪费时间。

**Implementation:** Set `EXECUTION_MODE` config based on user choice. Default to `hybrid` if user doesn't respond.

---

## Layer 1 — Target Preparation & Epitope Characterization

Goal: Produce target CIF, epitope residue list, 3–6 hotspots, and competitive intelligence summary.

> **广谱设计（多病原体靶标）入口判断：**
> 如已运行 `cross-genus-conservation` skill，domain annotation（1.2）、UniRef 保守性（1.3）、糖基避雷（1.4）均已在该 skill 中完成，**直接从 1.1 进入，完成后跳至 1.5 竞争情报**。`EPITOPE_RESIDUES` 和 `HOTSPOT_RESIDUES` 直接取用 `design_recommendations.txt` 的输出。

### Step 1.1 — Target structure & sequence

**Tools:** `adaptyv:pdb`, `adaptyv:uniprot`, `gget` skill

- Fetch target structure (CIF preferred, fallback PDB)
- Trim to binding region + 10 Å buffer
- Remove waters, ions, irrelevant ligands
- Extract sequence; verify chain boundaries

### Step 1.2 — Target domain annotation（单靶点模式）

**Tool:** `interpro` MCP (`analyze_protein_sequence`)

> **已运行 cross-genus-conservation → 跳过**（已在 Step 2 完成）

- Confirm epitope falls within the intended functional domain
- Check for disordered regions adjacent to epitope (unreliable for design)

### Step 1.3 — Target MSA & conservation（单靶点模式，可选）

**Tool:** `mcp__mmseqs2__generate_msa`

> **已运行 cross-genus-conservation → 跳过**（已在 Step 4 完成，跨属直接比对比 UniRef entropy 更可靠）

- Generate MSA against UniRef
- Compute per-residue conservation
- Prefer hotspots with conservation score > 0.5 (more robust epitope)

### Step 1.4 — Glycan avoidance（单靶点模式）

**Tool:** `glycoengineering` skill

> **已运行 cross-genus-conservation → 跳过**（已在 Step 5 完成，糖基风险已标注于 design_recommendations.txt）
>
> **Input: 抗原序列**（非 VHH；VHH CDR 侧糖基化检查见 Step 4.6）

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

**广谱模式**（已跑 cross-genus-conservation）：取用 `design_recommendations.txt` 的 hotspot 列表，与竞争情报（1.5）交叉验证（已报道 epitope 优先），去除 🚫 糖基遮蔽残基 → 输出 `inputs/hotspots.json`。

**单靶点模式**：综合 1.3 保守性 + 1.4 糖基 + 1.5 竞争情报 + epitope config → 输出 `inputs/hotspots.json`，3–6 残基，喂给所有 Layer 2 路径。

---

## Layer 2 — Multi-Path Parallel Generation

**4 independent generation paths, all launched in parallel (hybrid mode).** Each produces candidates into `{RESULTS_DIR}/gen/<path>/`.

> **为什么是 4 条而不是 5 条：** Path D (BindCraft) 已移出。BindCraft 是通用蛋白 binder hallucination 工具，无 IMGT FR 感知和 germline 约束；Path B (Germinal) 是 VHH 专用的优化版替代（germline-aware + AF2 内置验证）。需要 BindCraft 做通用蛋白设计时，用 `adaptyv:bindcraft` skill。

### Path A — BoltzGen `nanobody-anything` (Priority P1, validated)

**Tool:** `mcp__boltzgen_mcp__boltzgen_design`

- Input: target CIF + `VHH_SCAFFOLDS` (8 clinical scaffolds，4 IGHV3-23 + 4 IGHV3-7，代表7.75Å平均RMSD多样性)
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

### Path D — RFdiffusion v1 partial + AbMPNN (Priority P3)

**Tools:** `modal run modal_rfdiffusion.py` → `mcp__ligandmpnn_mcp__ligandmpnn_design`

**Step D1 — Backbone generation (RFdiffusion v1):**
- Use VHH scaffold as template for partial diffusion
- `--contigs` fixes FR1/FR2/FR3/FR4, rebuilds CDR1/2/3 loops
- Hotspot conditioning on target
- `L2_RFDIFFUSION_BACKBONES` backbones total

**Step D2 — Sequence design (AbMPNN, strict FR mode):**
- **Use `model_checkpoint: "abmpnn"`** (Exscientia, arXiv:2310.19513): ProteinMPNN fine-tuned on SAbDab antibody structures; ~60% sequence recovery vs ~35% for generic ProteinMPNN; 100% valid antibody sequences
- **Do NOT use SolubleMPNN** per `feedback_vhh_sequence_design.md`
- `vhh_framework_mode: strict` to lock FR, design CDR only
- `num_seq_per_target: L2_MPNN_SEQS_PER_BACKBONE`
- Reason: AbMPNN preserves CDR paratope aromatic/hydrophobic bias (same as ProteinMPNN) while better capturing antibody sequence grammar; solubility filtered downstream in L4 via `protein-sol_mcp`
- Fallback: if AbMPNN weights unavailable, use `model_checkpoint: "proteinmpnn_v_48_020"`

**Step D3 — Pool merge:**
- Output: ~4000 sequences → protein-sol pre-filter (step 4.2) → ~500 → `{RESULTS_DIR}/gen/rfdiffusion/`
- D2 AbMPNN 分数（基于 RFdiffusion 骨架）已在此完成其使命：作为 Path D 内部生成过滤器（4000 → 500）。**不作为 L4.3 的替代**——L4.3 会对所有路径统一在 L3 复合物结构上重新打分。

### Step 2.merge — Candidate pool consolidation

- Unify all 4 paths' outputs into a single candidate table: `{RESULTS_DIR}/gen/merged_pool.csv`
- Columns: `cand_id, source_path, sequence, structure_cif, source_job_id`
- Expected size: 1000–1500 candidates

### Step 2.dedup — MMseqs2 sequence deduplication

**Tools:** `mmseqs easy-cluster` (CLI), then `~/protein-design-utils/vhh/apply_cluster_repr.py`

> **注意：** `mcp__mmseqs2` 是 MSA 生成工具（多序列比对），**不能用于序列聚类**。此步骤直接调用 `mmseqs easy-cluster` CLI。

**Goal:** 相同序列 / 近似重复序列（不同路径独立生成了相同结果）只保留一个代表，节省 L3 GPU 算力。

```bash
# Step 1: export merged pool to FASTA
python ~/protein-design-utils/vhh/pool_to_fasta.py \
  {RESULTS_DIR}/gen/merged_pool.csv \
  --out {RESULTS_DIR}/gen/merged_pool.fasta

# Step 2: cluster at 95% identity with MMseqs2 (easy-cluster mode)
mmseqs easy-cluster \
  {RESULTS_DIR}/gen/merged_pool.fasta \
  {RESULTS_DIR}/gen/mmseqs_clusters \
  /tmp/mmseqs_tmp \
  --min-seq-id 0.95 --cov-mode 1 -c 0.8

# Step 3: apply cluster representatives (keeps highest-score member per cluster)
python ~/protein-design-utils/vhh/apply_cluster_repr.py \
  --pool {RESULTS_DIR}/gen/merged_pool.csv \
  --clusters {RESULTS_DIR}/gen/mmseqs_clusters_cluster.tsv \
  --out {RESULTS_DIR}/gen/dedup_pool.csv
```

- Output: `{RESULTS_DIR}/gen/dedup_pool.csv` — deduplicated candidate table
- Expected size: 1000–1500 → ~800–1200（同序列比率通常 <20% 跨路径）
- Note: `pool_to_fasta.py` 和 `apply_cluster_repr.py` 存放于 `~/protein-design-utils/vhh/`

### Step 2.diversity — 4-path diversity diagnosis

**Tool:** `~/protein-design-utils/vhh/path_diversity_report.py`

**Goal:** 在进入 L3 之前，用三个指标诊断 4 条路径的多样性——如果某条路径高度冗余或严重缺失，提前预警而非浪费验证算力。

```bash
python ~/protein-design-utils/vhh/path_diversity_report.py \
  --pool {RESULTS_DIR}/gen/dedup_pool.csv \
  --outdir {RESULTS_DIR}/gen/diversity/
```

**三个诊断指标：**

| 指标 | 计算方式 | 健康值 |
|------|---------|--------|
| **CDR3 length distribution** | 各路径 CDR3 氨基酸长度分布直方图 | ≥3 个长度 bin 有候选 |
| **CDR3 pairwise Levenshtein distance** | 各路径内 / 跨路径平均距离 | 路径内 >2，跨路径 >3 |
| **Path contribution balance** | 各路径占 dedup 池的比例 | 任一路径占比 <5% 或 >60% 发出警告 |

**输出：**
- `{RESULTS_DIR}/gen/diversity/diversity_report.md` — 三指标摘要 + 警告列表
- `{RESULTS_DIR}/gen/diversity/path_stats.csv` — 数值明细

**决策规则（人工审阅）：**
- 某路径贡献 < 5% → 检查该路径是否运行失败或参数不当，不盲目删路径
- 某路径贡献 > 60% → 路径参数可能过于宽松（生成数量过多），考虑限额或采样
- CDR3 多样性低（平均 Levenshtein < 1.5）→ 回 L2 检查路径 A 的 scaffold 多样性或路径 C 的 IgGM 样本数

---

## Layer 2.5 — Geometric Hotspot Pre-screen

**Goal:** 过滤 hotspot_contacts=0 的完全脱靶候选，节省 L3 四模型验证算力。纯几何分析，零额外 Modal 计算。

**Tool:** `hotspot_prescreen.py`（`~/protein-design-utils/vhh/`）

```bash
python ~/protein-design-utils/vhh/hotspot_prescreen.py \
  {RESULTS_DIR}/gen/ \
  --hotspots inputs/hotspots.json \
  --antigen-chain {TARGET_CHAIN} \
  --threshold {L2P5_DISTANCE_THRESHOLD} \
  --min-contacts {L2P5_HOTSPOT_MIN_CONTACTS} \
  --out {RESULTS_DIR}/l2p5_prescreen.csv
```

**输出：**
- `{RESULTS_DIR}/l2p5_prescreen.csv` — 所有候选的 hotspot 接触统计
- `{RESULTS_DIR}/gen/rejected/hotspot_miss/` — contacts < 阈值的候选（保留，不删除）

**双轨分流（gB-VHH N=200 校准 2026-04-15）：**

| 条件 | 去向 | 标注 |
|------|------|------|
| `hotspot_contacts >= L2P5_HOTSPOT_MIN_CONTACTS_TRACK_A` (≥2) | → **Track A**：主 L3 验证池（on-target binder） | `track=A` |
| `hotspot_contacts == 0` 且 `b2_iptm >= L4_IPTM_MIN` (≥0.9175) | → **Track B**：表位分析子流程（alt-epitope binder） | `track=B` |
| 其余（contacts=0 且 ipTM 低，或 contacts=1 模糊） | → 移入 `rejected/` | — |

**Track B 表位分析子流程：**

**Tool:** `~/protein-design-utils/vhh/track_b_cluster.py`

```bash
python ~/protein-design-utils/vhh/track_b_cluster.py \
  --prescreen {RESULTS_DIR}/l2p5_prescreen.csv \
  --candidates {RESULTS_DIR}/gen/merged_pool.csv \
  --antigen-chain {TARGET_CHAIN} \
  --hotspots inputs/hotspots.json \
  --outdir {RESULTS_DIR}/track_b/
```

1. 提取所有 Track B 候选的 CDR3 序列
2. 计算 CDR3 pairwise Levenshtein 距离，层次聚类（阈值 0.5）
3. 以序列簇差异推测多样表位识别：**不同簇 = 可能识别不同的表位区域**
4. 计算各簇代表候选与靶 epitope 质心的最近距离（Å）
5. 输出：`track_b_clusters.csv`（簇分配 + 距离）、`track_b_summary.md`（摘要）、`track_b_representatives.fasta`（各簇代表序列）

**两档距离判定（基于 CDR3 与 epitope 质心最近 Cα 距离）：**

| 距离 | 标注 | 去向 |
|------|------|------|
| **≤ 15 Å** | `track=B_keep` | → L3 弱标注通道，与 Track A 合并验证（CDR3 贴近 epitope，可能是 hotspot 定义偏差导致的漏网） |
| **> 15 Å** | `track=B_alt` | → CDR3 聚类后存入 `alt_epitope_candidates.csv`（带簇标签），不进主 L3 |

**B_alt 聚类（与 B_keep 同步跑）：**

```bash
python ~/protein-design-utils/vhh/track_b_cluster.py \
  --candidates {RESULTS_DIR}/track_b/b_alt.csv \
  --outdir {RESULTS_DIR}/track_b/alt_clusters/
```

- 输出：`alt_epitope_candidates.csv`（含 `cluster_id`、`cluster_repr` 列）、各簇代表序列 FASTA
- 每簇代表一个潜在的 alt-epitope 结合模式；同簇内保留 ipTM 最高者为代表
- 不进 L3，仅存档。若后续想探索 allosteric 靶点，以簇为单位取代表重走流程即可

**自动召回规则：**

- Track B_keep 候选数 ≥ 20 且 Track A 通过 L3 的绝对数 < 10 → 自动将 B_keep 合并入 L3 验证池

**迭代回路：** Track A pass rate < 5% → 回 L1.6 重选 hotspot，不调 L2 参数。

---

## Layer 3 — Structure Validation (2-model or 4-model)

**在运行 L3 之前，必须先确认用几个模型、选哪两个。** Absolute ipTM values are NOT compared — only rank agreement matters (per `domain_protein_design_gotchas.md` rule #2).

### L3 模式选择（运行前必读）

**背景：** Chai-1 / Boltz-2 / Protenix 都属于 AF3 家族（架构相近、训练数据重叠），三者的预测误差高度相关——同时运行三个等于花大量 GPU 在相关模型上。AF2m 是不同范式（MSA-heavy + Evoformer），与 AF3 家族正交性最强。因此"1 个 AF3 家族模型 + AF2m"是性价比最高的 2-model 组合。

**在此提醒用户选择：**
> 本次 L3 用 **2 个模型（推荐）** 还是 **4 个模型（完整版）**？
>
> **2-model（推荐）：** 选 1 个 AF3 家族 + AF2m。参考下表：
>
> | 优先级 | AF3 家族选择 | 适用场景 |
> |--------|------------|---------|
> | ① | **Protenix**（v2 + `use_tfg_guidance=True`） | v2 权重已上线时首选；Ab-Ag DockQ 比 v1 高 9–13 pp |
> | ② | **Chai-1** | Protenix v2 权重下架（当前状态）时的默认替换 |
> | ③ | **Boltz-2** | 候选池 > 1000 且时间是瓶颈时的速度优先选择 |
>
> **4-model（高把握模式）：** 需要最高置信度时使用（如第一个靶点无历史 baseline、或候选数 <300 负担不大）。运行全部 Chai-1 + Boltz-2 + Protenix + AF2m。
>
> **共识阈值随模式调整：**
> - 2-model：需 **2/2** 通过（两个模型必须一致）
> - 4-model：需 **3/4** 通过（IgGM 路径放宽至 2/4）

**默认推荐：** 2-model = **Chai-1 + AF2m**（Protenix v2 权重当前下架，Chai-1 是稳定替代）。

---

### Step 3.0 — Ibex VHH monomer sanity check (cheap pre-filter)

**Tool:** `mcp__ibex_mcp__ibex_predict_batch` (批量模式，不再单条循环)

- Goal: cheaply 剔除明显坏 scaffold（畸形 CDR loop / 框架塌陷），省下 4 模型复合物预测的算力
- Input: batch of VHH sequences as monomers (apo mode)
  - Build `inputs/ibex_batch.fasta` from `{RESULTS_DIR}/gen/merged_pool.csv` (sequence column)
  - Pass entire FASTA in a single `ibex_predict_batch` call — avoids per-candidate API round-trip overhead
- Filter criteria:
  - CDR-H3 RMSD vs nearest germline reference > 4.0 Å → drop (loop 不收敛)
  - Overall pLDDT < 70 → drop (单体本身建模失败)
- Output: `{RESULTS_DIR}/val/ibex_monomer/sanity_pass.csv`
- License caveat: Ibex (Genentech/Prescient Design) is **non-commercial only** per `feedback_ibex_mcp.md`. For internal R&D use only; do not embed in 商用产品输出
- Expected attrition: ~10–20% of merged pool drops here

**Implementation note:** if `ibex_predict_batch` is unavailable (schema mismatch or job limit), fall back to `ibex_predict` single-call loop — log the fallback in `{RESULTS_DIR}/val/ibex_monomer/run.log`.

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
- **L3 filter threshold（按模式和路径）：**
  - **2-model 模式：** 所有路径需 2/2 通过（IgGM 不放宽，因为只有两个模型时放宽至 1/2 过于宽松）
  - **4-model 模式：** BoltzGen / Germinal / RFdiffusion 路径需 `L3_MIN_MODELS_PASS`（default 3/4）；IgGM 路径放宽至 `L3_MIN_MODELS_PASS_IGGM`（default 2/4）
  - IgGM candidates passing the relaxed threshold are tagged `relaxed_filter=True` in output CSV for downstream tracking
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

**`binding_quality_score` 计算（存入 `consensus_ranked_dsasa.csv`）：**

```python
# 两个分量均先做 min-max 标准化到 [0, 1]，再加权求和
binding_quality_score = (
    0.6 * rank_normalize(ipsae_rank) +      # Step 3.5a：界面预测共识质量
    0.4 * rank_normalize(dsasa_ratio)       # Step 3.5b：CDR3 界面贴合度
)
# rank_normalize(x) = (x - x.min()) / (x.max() - x.min())，分量越大越好
```

<!-- Step 3.5c (Boltz-2 affinity prediction) removed:
     Boltz-2 affinity 模块训练于通用 PPI 数据集，对 VHH-抗原界面（高度不对称，
     单域 ~15 kDa vs 抗原）无验证依据，预测值不可靠，不纳入排名。
     如需计算亲和力代理指标，用 Stability Oracle (Step 4.4) 的 ΔΔG 扫描或
     MBER (Step 5.1) 的亲和力成熟回路，均有更好的 VHH 适用性。 -->

---

### Step 3.6 — AF2Rank structural re-identification

**Tool:** `modal run modal_af2rank.py`

**Default behavior:** Step 3.4 (AF2m multimer) is a standard pipeline step and always runs. When AF2m ran in Step 3.4, **always run AF2Rank at zero extra compute** — reuse Step 3.4 outputs directly. No conditional check required.

**Non-standard case (AF2m explicitly disabled):** Only trigger a fresh AF2Rank run if ANY of the following signals are present:
- Ibex L3.0: rejection rate (candidates dropped by Step 3.0 / total input to Step 3.0) > 30% — indicates VHH monomer fold is broadly unstable across the pool. **Use the Step 3.0 run log's rejection count**, not the current (post-filter) pool pLDDT distribution, which no longer contains dropped candidates.
- ipSAE step 3.5: Spearman rank correlation with other models < 0.4 (interface signal unreliable)
- Otherwise: **skip AF2Rank**, proceed directly to Step 3.7

**Rationale:** ipSAE (Step 3.5) covers complex interface quality; AF2Rank covers VHH monomer fold self-consistency. They are complementary, not redundant. Since AF2m (Step 3.4) runs by default, AF2Rank is essentially always free — the conditional path only matters if AF2m is explicitly removed from the pipeline.

- Output: `{RESULTS_DIR}/val/af2rank_filtered.csv` (or skipped — mark in run log)

### Step 3.7 — IP / structural similarity annotation (foldseek)

> **保留原因：IP 风险标注，非质量过滤。** VHH 框架收敛到小结构库，结构相似（TM-score > 0.7）是正常现象而非质量问题；仅当 CDR3 序列高度相同时才有 IP 风险。结构相似的候选**不因本步骤被删除**。

**Tool:** `adaptyv:foldseek` skill

- Query each surviving candidate against PDB + SAbDab
- **Annotate, do NOT auto-drop**: add `top_hit_tm_score` and `top_hit_pdb_id` columns to the candidate table
  - TM-score > 0.9 to a known VHH + CDR3 sequence identity > 80% → flag `ip_risk=HIGH` (near-identical to deposited structure; requires IP review before filing)
  - TM-score > 0.7 (structural similarity only, CDR3 divergent) → flag `ip_risk=LOW` (convergent VHH fold is expected and acceptable; no action needed)
  - Otherwise → `ip_risk=NONE`
- **Rationale:** VHH framework folds converge to a small structural repertoire — TM-score > 0.7 against SAbDab is normal and does NOT indicate quality problems. Dropping on structural similarity alone would remove candidates with validated scaffold geometries. Only sequence-level CDR3 identity raises genuine IP concerns.
- **Hard drop** (only case): TM-score > 0.95 AND CDR3 identity > 90% to an existing therapeutic VHH in clinical trials (query via `claude_ai_Clinical_Trials` if flagged) — this indicates near-copy of a clinical asset
- Output: `{RESULTS_DIR}/val/ip_annotated.csv`

### Layer 3 gate

Expected funnel: 1000–1500 → ~200–300 candidates enter Layer 4.

**Iteration loop 1:** If < 10% of pool survives Layer 3 across all 4 paths uniformly → hotspots likely wrong or epitope occluded. Return to Step 1.6, reselect hotspots, rerun Layer 2. **Do NOT** debug individual candidates in this failure mode.

---

## Layer 4 — Developability Funnel (SERIAL — order matters)

**Strictly serial**, cheap-first. Each step reads the previous step's output. Intermediate CSVs persisted between steps (format TBD — decide on first run).

**Layer 4 step order (rationale):**
> 4.1 ANARCI（零 GPU，秒级）→ **4.2 protein-sol（MCP，免费，序列级）** → 4.3 AbMPNN（需 CIF，GPU）→ 4.4 Stability Oracle → 4.5 MHC → 4.6 glycosylation
>
> protein-sol 只需序列即可运行，无需 L3 结构输出；AbMPNN scoring 需要 CIF 输入（GPU），放在 protein-sol 后可以先用便宜过滤压缩候选池，节省 GPU 算力。

### Step 4.1 — ANARCI numbering & framework integrity + germline humanness

**Tool:** `modal run modal_anarci.py`

- Scheme: IMGT (primary), Kabat (secondary check)
- **Required params:** `--csv --assign_germline --use_species human --ncpu 2`
  - `--assign_germline` activates germline alignment; `--use_species human` restricts to human IGHV germlines
  - Output CSV gains `v_gene` (best-match IGHV name) and `v_identity` (float 0–1, FR sequence identity to that germline)
- Pass: numbering succeeds AND FR1/FR2/FR3/FR4 boundaries match the scaffold/template
- **Drop:** any candidate ANARCI fails to number, or FR region length deviates
- **Extract `humanness_score`**: copy `v_identity` column as `humanness_score` — this is the L4.7 Pareto input for that dimension. VHH typical range: 0.72–0.87 vs human IGHV3 family. Measures FR humanness only (CDR excluded), which is the correct proxy for immunogenic risk in the framework region.
- Expected reduction: 200–300 → ~180–250

### Step 4.2 — Solubility (sequence-level, cheap, run before AbMPNN)

**Tool:** `mcp__protein-sol_mcp__protein_sol_solubility_predict`

- **Run before AbMPNN** (step 4.3): protein-sol requires only sequence — no GPU, no CIF needed. Filters low-solubility candidates early and reduces the AbMPNN GPU batch size.
- Drop candidates with score < `L4_PROTEIN_SOL_MIN`
- Expected reduction: 180–250 → ~130–180

### Step 4.3 — AbMPNN sequence-structure consistency scoring

**Tool:** `mcp__ligandmpnn_mcp__ligandmpnn_design` (scoring mode, `score_only=True`)

**Rationale:** ESM2/ESM-C PLL 对 CDR 区域无效——通用蛋白语言模型会因 CDR 高度可变而给低分，但这是 CDR 的正常特征，不是质量差。AbMPNN（SAbDab 抗体结构训练）能正确理解 CDR 变异空间，给出结构条件化的序列合理性评分。

- Input: each candidate's CIF + sequence (structure-conditioned scoring)
- **所有 4 条路径统一**在 L3 预测复合物结构（Boltz-2 preferred for stability，fallback Chai-1）上跑 `score_only=True`
- **Path D 不复用 D2 分数**：D2 的 AbMPNN 是在 RFdiffusion 骨架（pre-L3，无抗原）上打的，度量"序列与骨架吻合度"；L4.3 需要的是"序列与复合物界面的吻合度"——两者不等价，不可替代
- Metric: length-normalized log-likelihood (`ll_fullseq` / sequence length)
- Drop bottom `L4_ABMPNN_LL_MIN_PERCENTILE` (default: below median)
- Expected reduction: 130–180 → ~65–90

**Note:** AbMPNN scoring is structure-conditioned — requires a CIF input per candidate. Ensure L3 outputs are available before running this step.

### Step 4.4 — Stability Oracle ΔΔG scan

**Tool:** `mcp__stability_oracle_mcp__stability_oracle_predict`

- Mode: per-candidate ΔΔG at mutation hotspots (not full `--scan-all` — too expensive at this funnel stage)
- Drop candidates with any residue ΔΔG > `L4_STABILITY_DDG_MAX`
- Expected reduction: 65–90 → ~50–70

### Step 4.5 — Immunogenicity (MHC-I + MHC-II, MANDATORY)

**Tools:** `mcp__netMHCpan_mcp__predict_protein_epitopes`, `mcp__netMHCIIpan_mcp__predict_protein_epitopes`

**This step is non-optional per `feedback_immunogenicity_check.md`.**

- MHC-I: scan full VHH sequence against common HLA-A/B/C panel
- MHC-II: scan full VHH sequence against common HLA-DRB1 panel
- **Drop candidates with any strong binder (rank < `L4_MHC_RANK_THRESHOLD`) within CDR regions**
- Weak binders (rank 2–10%) in FR are tolerated
- Expected reduction: 50–70 → ~30–50

### Step 4.6 — De novo glycosylation sequon check

**Tool:** `glycoengineering` skill

> **Input: 设计的 VHH 候选序列**（非抗原；此步骤检查 CDR 设计引入的新糖基化位点——抗原侧的糖基化回避见 Step 1.4）

- Scan designed VHH CDRs for newly-introduced N-X-S/T sequons not present in the original scaffold
- Drop candidates with new sequons in CDRs (glycans on paratope ruin affinity and add manufacturing risk)
- Expected reduction: 30–50 → ~25–40

### Step 4.7 — Multi-objective Pareto selection

**Tool:** `~/protein-design-utils/vhh/pareto_select.py`

**Goal:** 避免单一加权分数掩盖真实 tradeoff。在"结合质量"和"可开发性"两个正交维度上用 Pareto front 选出非劣候选，确保进入 L5 的候选没有在任一维度上被其他候选全面碾压。

**三个 Pareto 目标（均为最大化方向）：**

| 维度 | 来源列 | 含义 |
|------|--------|------|
| `binding_quality_score` | L3.5 加权复合分 | 结合质量（ipSAE 0.6 + dSASA 0.4） |
| `humanness_score` | L4.1 ANARCI `v_identity` | FR 人源化程度（免疫原性代理指标） |
| `protein_sol` | L4.2 protein-sol 输出 | 溶解度 |

```bash
python ~/protein-design-utils/vhh/pareto_select.py \
  --input {RESULTS_DIR}/l4_funnel_final.csv \
  --objectives binding_quality_score humanness_score protein_sol \
  --out {RESULTS_DIR}/final/pareto_selected.csv
```

- 输出列：`pareto_rank`（1 = 第一 Pareto 前沿，即非劣集；2 = 第二前沿，依次类推）
- 第一前沿候选：不存在任何其他候选在三个维度上全部优于它
- 进入 Layer 5 的候选：`pareto_rank <= L4_PARETO_MAX_RANK`（默认 2，兜底确保不少于 10 个）
- Expected: ~25–40 → 15–25 candidates（视前沿分布而定）
- Note: `pareto_select.py` 存放于 `~/protein-design-utils/vhh/`，使用 brute-force 非劣排序（候选数 <200 时无需 NSGA-II）

### Layer 4 gate

Expected output: ~15–25 candidates (Pareto front 1–2) → Layer 5.

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

<!-- Step 5.3 (Boltz-2 affinity prediction) removed:
     Boltz-2 affinity 模块对 VHH-抗原界面无验证依据（见 Step 3.5c removal note）。
     Post-MBER 亲和力代理指标用 Stability Oracle ΔΔG（Step 4.4 re-run on matured seqs）替代。 -->

### Step 5.4 — (Optional) ESM2 masked residue refinement

**Tool:** `modal run modal_esm2_predict_masked.py`

- For top 5 candidates, mask each CDR residue in turn
- If ESM2 strongly prefers a different residue (>3x over current), note as "ESM2 suggests X → Y"
- **Do not auto-apply** — flag for manual review; actual application requires another L3/L4 round
- Output: `{RESULTS_DIR}/mature/esm2_suggestions.csv`

<!-- Step 5.5 MD removed 2026-04-14 (R2-5): ROI negative for de novo VHH screening.
     SOTA campaigns (BindCraft/Germinal/IgGM) don't run MD; L3 4-model consensus +
     L3.5b dSASA + L4.3 AbMPNN scoring + L4.4 Stability Oracle + L4.7 Pareto multi-objective
     selection already covers binding quality, thermodynamic stability, and developability.
     100ns × 15 candidates ≈ 100–200 A100-h; better spent on cell-free expression.
     If MD is needed for a specific mechanism/paper study, write a dedicated skill. -->

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
- Generate top-table: `{RESULTS_DIR}/final/top_candidates.md` with sequence, L3 consensus rank, L4 developability flags, L4.7 Pareto rank, L5 affinity, ESM2 suggestions

---

## Thresholds — Tier 1 / Tier 2 分层校准策略

阈值分为两档，校准时机和软过滤策略不同：

### Tier 1 — 设计完成即可校准（无需实验数据）

这些阈值可用计算指标的分布本身来校准，**不需要等实验数据**：

| 阈值 | 校准方式 | 软过滤 |
|------|---------|--------|
| `L4_IPTM_MIN` (0.9175) | 已用 gB-VHH N=200 伪AUC校准（Youden's J）| **硬过滤**（已校准，不放宽） |
| `L3_DSASA_RATIO_MIN` (0.25) | 首次 campaign 跑完后：对通过 ipSAE 共识的候选算 dSASA 分布，取 p25 作阈值 | **软过滤**（初次运行）→ 硬过滤（校准后）|
| `L3_IPSAE_TOP_FRAC` (0.5) | 首次 campaign 跑完后：看 50% vs 30% cut 对 L4 输出量的影响，选保留 25–40 个 | **软过滤**（首次运行按 40% 执行，兜底）|
| `L4_ABMPNN_LL_MIN_PERCENTILE` (50) | AbMPNN log-likelihood 分布取中位数，首次可用分布调 ±10% | **软过滤**（±10% 内不报警）|

**校准动作（首次 campaign L3 完成后立即执行）：**
```bash
python ~/protein-design-utils/vhh/calibration_output/calibrate_tier1.py \
  --l3-results {RESULTS_DIR}/val/consensus_ranked_dsasa.csv \
  --out ~/protein-design-utils/vhh/calibration_output/tier1_calibrated.json
```
（calibrate_tier1.py 存放于 `~/protein-design-utils/vhh/calibration_output/`，计算 dSASA p25 + ipSAE cut 推荐值，输出 JSON 以便手动确认后更新 skill config）

### Tier 2 — 需要实验数据后校准（软过滤直到获得反馈）

这些阈值必须有湿实验结果（binding / expression / Tm）才能有意义校准，**首次运行时作为软过滤**（miss < 10% 保留为 borderline 候选）：

| 阈值 | 软过滤行为 | 校准所需数据 |
|------|-----------|------------|
| `L4_PLDDT_MIN` (0.80) | miss < 0.78 → borderline | ≥10 个表达结果 |
| `L4_PAE_INTERFACE_MAX` (10) | miss < 12 → borderline | ≥10 个 KD 测量 |
| `L4_SCRMSD_MAX` (2.0) | miss < 2.5 → borderline | ≥10 个结晶/HDX 数据 |
| `L4_PROTEIN_SOL_MIN` (0.45) | miss < 0.40 → borderline | ≥10 个表达产量数据 |
| `L4_STABILITY_DDG_MAX` (1.5) | miss < 2.0 → borderline | ≥10 个 Tm 测量 |
| `L4_MHC_RANK_THRESHOLD` (2.0) | **不软过滤**（免疫原性不让步）| — |

**获得实验数据后的校准步骤：**
1. Collect Layer 3 consensus ranks of candidates that experimentally bind (KD < 1 μM)
2. Collect Layer 4 values of candidates that fail (no expression / aggregation / low Tm)
3. Update thresholds to maximize AUC for experimental success prediction
4. Record in `domain_protein_design_gotchas.md` if any deviation is systematic (i.e., "for VHH, use pLDDT > 0.85 instead of 0.80")

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

<!-- Loop 3 (MD fail) removed 2026-04-14 along with Step 5.5 (R2-5). -->

---

## Hard Constraints (non-negotiable)

1. **FR/CDR are jointly optimized** (`domain_protein_design_gotchas.md` #1): do not transplant CDRs across FRs. Use strict FR mode in Path D from the start.
2. **Cross-model ipTM is not comparable** (`domain_protein_design_gotchas.md` #2): Layer 3 consensus uses rank agreement, never absolute ipTM comparison across models.
3. **Immunogenicity scan is mandatory** (`feedback_immunogenicity_check.md`): Step 4.5 cannot be skipped for therapeutic VHH.
4. **AbMPNN (not SolubleMPNN) for VHH** (`feedback_vhh_sequence_design.md`): Path D uses AbMPNN (`model_checkpoint: "abmpnn"`) — antibody-fine-tuned ProteinMPNN — with strict FR mode; protein-sol downstream filter in L4. Fallback to `proteinmpnn_v_48_020` if AbMPNN weights unavailable.
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
- <10 candidates reach Layer 5 → thresholds too strict, relax in order: protein-sol (4.2) first, then AbMPNN (4.3), then pLDDT/ipTM (L3 gate)
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
