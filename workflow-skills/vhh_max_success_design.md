---
name: vhh-max-success-design
description: Maximum-success-rate VHH (nanobody) de novo design pipeline. 4 orthogonal generation paths (BoltzGen nanobody-anything, Germinal, IgGM, RFdiffusion+AbMPNN; BindCraft excluded — not VHH-specific), 2-model or 3-model structure validation (Chai-1+Boltz-2 default 2-model; Protenix+Boltz-2+Chai-1 3-model; AF2m removed after SNAC-DB 2026 Nb-Ag benchmark), developability funnel (ANARCI, protein-sol, AbMPNN scoring, Stability Oracle, netMHCpan I+II, glycosylation), and affinity maturation with MBER. Parallel to nanobody_design skill; use this when success rate matters more than compute cost.
---

# VHH Max-Success Design Skill

> **Last updated:** 2026-05-12 — (24) **L2/L4 分工再校准（hard drop 大幅收窄）**：原则——L2 hard drop 只保留"不可救的明确缺陷"（generator failure / 序列非法 / 结构折叠失败），可通过点突变 / surface charge engineering 缓解的项目全部降为 soft flag + 进 Pareto 自然降权。① **Step 2.seqfilter**：CDR N-glycan motif（N→Q 可救）/ 极端 pI < 4.0 或 > 10.0 / 极端净电荷 < −8，三项从 hard drop 改 soft flag，新增 `rescue_suggestion` 列；保留 hard drop 仅：CDR3 长度越界 / 未配对 Cys / ANARCI 失败。② **Step 2.solfilter**：`protein_sol < 0.45` 从 hard drop 改 soft flag（连续值已在 Pareto），实测阈值与 VHH 实际可溶性相关性弱，避免误杀 IgGM/Germinal borderline 候选。③ **Step 2.mhcfilter**：FR 多 allele MHC（非 scaffold 来源）从 hard drop 改 soft flag + `mhc_risk_score` += 2.0 强惩罚 + humanize 突变建议（FR 可定向去免疫原性，hard drop 丢 head-on 候选成本过高）。④ **Step 4.4 Pareto**：6 → 7 目标，新增 `seq_risk_count`（汇总 pI/charge soft flag），`glycan_count` 语义扩展含 CDR；attrition 期望从"10–15% + 15% + ?"全部归零，靠 Pareto 多目标自然降权。⑤ **Hard Drop / Soft Flag 总表** 同步搬家，"早期 Hard Drop"表新增"不可救原因"列，"早期 Soft Flag"表新增"rescue 路径"列。 (23) **S2+S3+S7 核心排序重写**：① 新建 scripts/config.py 集中 L3.A/L3.B 模型矩阵 + binding_composite 权重 + flag 降权因子（SKILL.md 不再列具体模型分配，单一 source-of-truth）；② Step 3.5 重写为 5-step 流水线：ipTM chain-pair<0.5 hard drop → 5-seed CDR3 Cα 连通分量聚类（主簇≥3/5）→ 簇内 ipSAE_min → 跨模型 ipSAE_min（min-min，Overath 2025 F1=0.61 路径校准前 floor=0.50）→ AntiConf (pTM × pDockQ2，Ünsal 2026) 簇内代表挑选；③ Step 4.4 binding_composite 重写为 5 分量加权（ipSAE 0.40 / cluster_size 0.20 / AntiConf 0.15 / dSASA 0.15 / cdr_dominance 0.10）+ 4 个 flag 乘性降权（cdr_dominance_low 0.7 / anticonf_low 0.85 / pose_diverged 0.5 / ipsae_min_min_below_floor 0.7）；④ 下游 filter_dsasa.py / hotspot_prescreen.py 加 --cif-path-col 参数读 representative_cif_path_primary 列。详细 spec/plan 见 docs/superpowers/{specs,plans}/2026-05-12-s2s3s7-*.md。 (22) **Step 2.negctrl 扩展为双 null**（S5 of 3.5 framework rewrite）：原 scramble CDR3 null（Sub-step A/B）保留不变；新增 Sub-step C/D：**unrelated antigen null** — 每候选 × decoy panel（3–10 个真实无关 PDB）× 1 seed → ipSAE_min null 分布。理由：Greiff Champloo 2026 实测 confidence metrics 不区分 cognate vs non-cognate，两个 null 失败模式互补（scramble 查 generator failure / 序列侥幸；unrelated antigen 查"万能 sticky" VHH）。Decoy panel 一次性建库 `inputs/decoy_panel/`，所有项目复用，要求 BLAST E<1e-3 排除同源、fold 多样、避开 HSA/lysozyme 等 sticky 蛋白、大小 ±50% 真靶点。算力控制：unrelated null 只对 L3.A 幸存者（~150 候选）跑，3 decoy × 1 seed × 2 model ≈ 900 预测（L3.B base 的 1.2×）。`path_thresholds.json` schema 扩展为 `{scramble_floor, unrelated_floor}` 双门槛，L3 gate 要求双 95% 分位均过。新增 config: `DECOY_PANEL_DIR / DECOY_N_PANEL / DECOY_SEEDS_PER_CANDIDATE / UNRELATED_NULL_PERCENTILE`；新增工具占位：`build_decoy_panel.py / submit_unrelated_null.py`；扩展工具：`calibrate_neg_control_thresholds.py` 增加 `--unrelated-scores` 参数。 (21) **AF2m 移出 L3 验证器**（S1 of 3.5 framework rewrite）：依据 SNAC-DB (Sanofi 2026) per-model Nb-Ag 数据，AlphaFold2.3-multimer 在 NANOBODY-antigen 上 Rank-1 仅 9.9%（与 OpenFold-3p2 并列最差），Protenix-v1 23.8%（最高）。前版 "Chai-1 + AF2m" 2-model 推荐基于 "AF2 vs AF3 架构正交" 推理 + Ünsal 2026 混合 Ab+Nb 数据集 "AF2 整体胜" 结论，但 Ünsal 数据集以经典抗体为主；VHH 子集上 AF2m 实测垫底。架构正交性救不了 VHH 任务上 AF2m 的实测垫底。**新 2-model 默认 = Chai-1 + Boltz-2**（Protenix v2 下架期间）；Protenix v2 回归后升级为 **Protenix + Boltz-2**；3-model 高把握 = **Protenix + Boltz-2 + Chai-1**（全 AF3 家族，误差相关性通过 framework-level robustness 补偿——pose convergence + min-min + 后续 3.5.1 unrelated antigen null + 3.5.2 跨模型 epitope Jaccard）。Step 3.4 (AF2m) 和 Step 3.6 (AF2Rank) 标注 deprecated；modal_alphafold.py / modal_af2rank.py 不再列为标准工具。Path A (BoltzGen) 因内部已用 Boltz-2，L3 实际可用模型仅 Chai-1 + Protenix（强制 2-model 上限）。MBER 重验证（Step 5.2）共识门槛随之调整。 (20) **BoltzGen scaffold 库与官方对齐（Path A 关键 bug fix）**：根因——`gen_scaffold_yamls.py` 把 H2 硬编码为 Kabat 50..65（16 res），导致 BoltzGen 把 FR3 起始 β-sheet 残基（`LYADSVRG` 等）当 CDR 设计 → V_H 折叠塌陷。16F9 实测 4 scaffold × 100 = 400 designs 中 91% miss hotspot（HS=0/8），仅 2 个真接触。修复：① 新建 BoltzGen 专用库 `~/protein-design-utils/vhh/scaffolds/boltzgen_official/`（7 个官方 scaffold，Chothia loop tip + 1 buffer 标定，YAML+CIF 直接来自 HannesStark/boltzgen `example/nanobody_scaffolds/`）；② `gen_scaffold_yamls.py` 标记 deprecated for BoltzGen，仅留给 IgGM/RFantibody/Germinal（这些工具不复用 BoltzGen yaml，H2 边界不影响）；③ SKILL config 新增 `VHH_SCAFFOLDS_BOLTZGEN`，旧 `VHH_SCAFFOLDS` 保留给其他路径；④ Path A Step A0 改为复制 `boltzgen_official/yaml/` 到 `inputs/boltzgen_scaffolds/`；⑤ 新增 scaffold 纪律：禁止套公式生成 BoltzGen yaml，必须 PyMOL/ANARCI 视检 loop tip。 (18) Bug fix: Step 2.mhcfilter FR hard-drop 规则修正——central scaffold library 的 FR 保守序列已有临床验证，MHC 命中应 flag 不 hard-drop；仅非 scaffold 来源的新引入 FR 序列在 ≥3 allele SB 时才 hard-drop；同步更新 Hard Drop 总表和 failure_reason 表。触发条件：16F9 smoke test 中 8coh_A/7dv4_B 因 scaffold FR2 MHC-II 信号被整体删除，逻辑矛盾（临床在用 scaffold 被计算预测推翻）。 (17) 9处审阅改进：① L3.A Path A改用Chai-1（Protenix是AF3复刻，与Boltz-2高度相关）；② Step 2.negctrl路径模型对齐（Path A→Chai-1，B/C/D→Boltz-2）；③ L3.A Pose收敛改为per-track（Track A:3/3严格，B_keep:2/3宽松）；④ Layer 2.5 Track B增加Boltz-2独立ipTM复测（禁用生成器自报ipTM）；⑤ L3.B 2-model共识改为双门控+加权排名（AND投票→连续分数提升recall）；⑥ Pareto结合三联指标合并为binding_composite（8目标→6目标，减少强耦合目标竞争）；⑦ Ibex单体预筛从Step 3.0提前至Step 2.ibex（Layer 2末尾，hotspot预筛之前，防止fold塌陷浪费hotspot检查）；⑧ L5.2 MBER后验证简化（2-model+3seeds，ANARCI/AbMPNN承袭，ΔΔG必须重跑）；⑨ 路径代表配额从20%提至30%，多样性从30%降至20%。 (19) 目录结构修正：`gen/` 只存放模型生成输出（boltzgen/iggm/rfantibody），所有过滤/验证产物统一移入 `val/`：序列过滤链（seq_aa/seq_sol/seq_filtered/rejected）→ `val/filter/`，多样性诊断报告 → `val/diversity/`，ibex PDB → `val/ibex_monomer/pdb/`；废弃 `gen/debug/`、`gen/rejected/`、`gen/diversity/` 这三个混用目录（触发条件：16F9 smoke test 清理时发现逻辑混乱）。(16) 文件命名重构：① Layer 2 序列过滤链中间文件（seq_aa / seq_sol）移入 `val/filter/`，主链只保留 4 个文件（merged→dedup→seq_filtered→l3_input）；② Layer 4 采用列追加模式，4.1→4.3 共用 `l4_scored.csv`（不建中间文件），l4_funnel_final.csv 废弃；③ Pareto 输出合并为单文件 `final/pareto_results.csv`（含 pareto_rank 列），删除 pareto_rank/pareto_front/pareto_selected 三文件；④ Pareto 目标表来源标注更新（protein_sol/mhc_min_rank/glycan_count 改为 Layer 2 来源）。(15) L4 重构：① protein-sol 从 L4.2 提前至 Step 2.solfilter（序列级，L3 之前 fail-fast）；② MHC I+II 从 L4.5 提前至 Step 2.mhcfilter（治疗安全性门控，L3 之前 fail-fast）；③ Step 4.6 CDR 糖基化 delta 检查删除（Step 2.seqfilter 绝对门控已覆盖，到 L4.6 时 CDR 必然无 NXS/T）；FR 糖基化 delta 检查合并入 Step 2.seqfilter 作第 7 项（flag，不硬删，进 Pareto glycan_count）；④ L4 步骤重编号：4.3 AbMPNN→4.2，4.4 StabilOracle→4.3，4.7/4.7b Pareto→4.4/4.4b，4.8→4.5；⑤ L4 步序说明更新；⑥ Layer 3 gate 和 Layer 4 gate 漏斗数字更新；seqfilter 输出重命名为 seq_aa_filtered_pool.csv，mhcfilter 最终产出 seq_filtered_pool.csv（下游引用不变）。(14) 新增 Step 3.5a Hotspot re-verification：在 L3.B 高质量共折叠结构上重跑 hotspot_prescreen（Step 3.5 ipSAE 之后、Step 3.5b dSASA 之前）；L3 全流程原本无 epitope 特异性检查（ipSAE/dSASA/clash 只验证结合质量，不验证结合位置），此步填补缺口；Hard drop，不设 Track B，零额外 GPU；3.5b --input 改为读 l3b_hotspot_recheck.csv。(13) 6处 Bug 修复：① Step 2.l3pool 新增 Track A+B_keep 汇总步骤（`l3_input_pool.csv`），Step 2.negctrl 和 Step 3.0 Ibex 改读此文件（原引用 `seq_filtered_pool.csv` 会包含 L2.5 已拒绝候选，污染 negctrl 基线和 Ibex 批量提交）；② filter_dsasa.py 两次调用补全 `--input` 参数（3.5b 读 `consensus_ranked.csv`，3.5d 读 `dsasa_filter_results.csv`，输出统一为 `consensus_ranked_dsasa.csv`）；③ Step 4.6 末尾定义 `l4_funnel_final.csv`（Step 4.7 引用此文件但此前从未创建）；④ "7 个 Pareto 目标" → "8 个"（cdr_dominance_score 加入后漏改）；⑤ Step 5.1 MBER "default 50" → "default 20"（config 已改未同步）；⑥ Step 3.1 Input 改为 `l3a_pass.csv`（L3.B header 已注明但 Step 3.1 本身未更新）。(12) 6处结构性改进：① Step 2.seqfilter 新增序列预筛层（零GPU，ANARCI提前+极端电荷+非配对Cys+N-glycan+pI，L4.1改为读取此步结果）；② L3 拆分为 L3.A（粗筛 Boltz-2+Protenix 3seeds → top 150）+ L3.B（精筛，原 Steps 3.1–3.7）；③ Step 3.5b 扩展 CDR 全主导度（cdr_dominance_score，CDR1+2+3/total dSASA ≥0.5）+更新 binding_quality_score 为3/4分量公式；④ Step 3.5d 新增界面 clash 精确检查（Cβ-Cβ<3.4Å，≤3对）；⑤ Layer 4.8 人工审查门控（合成前必须，渲染+逐候选清单+review_notes.md）；⑥ Step 4.7b 改为24/48/96组合策略（高分50%+多样性30%+路线代表20%）。新增配置参数：SEQ_PI_MIN/MAX、SEQ_NET_CHARGE_MIN、L3A_SEEDS/PASS_N、L3_CLASH_MAX_PAIRS、L3_CDR_DOMINANCE_MIN、FINAL_CANDIDATE_TARGET/TOP_SCORING/DIVERSITY/PATH_REP_FRAC。新增待实现工具：seq_prefilter.py、l3a_filter.py、build_final_candidates.py、apply_review_decisions.py；filter_dsasa.py 需新增 --all-cdrs/--mode clash 参数。(11) 6处改进合入：① Step 2.dedup 改为两阶段（路线内80% CDR3聚类 + 跨路线保留独立hit）；② Step 2.negctrl 新增路线特异性阈值校准（每路线5个scramble负控）；③ L3 加入抗原多聚体状态强制检查；④ L3 可选multi-seed pose convergence模式（L3_MULTI_SEED_MODE）；⑤ Step 3.2 RFantibody分数分布外偏低警告；⑥ Step 4.7b 路线配额强制执行（RFAb:4/BoltzGen:2/Germinal:2/IgGM:2）；新增配置参数：L3_MULTI_SEED_MODE/COUNT、L3_POSE_CONVERGENCE_RMSD/MIN_SEEDS、TOP10_PATH_QUOTA；新增待实现工具：merge_path_pools.py、generate_neg_controls.py、calibrate_neg_control_thresholds.py、enforce_path_quota.py。(10) Scaffold 库升级：从 4 → 8 临床代表（TheraSAbDab + Evers et al. mAbs 2025 文献挖掘，含 Netakimab/Porustobart/Erfonrilimab 新增；中央库 `~/protein-design-utils/vhh/scaffolds/`，胚系 IGHV3-23/IGHV3-7，人源化 71–85%）。(9) L3 结构预测模式重构：新增"2-model vs 4-model"选择决策提示；明确 AF3 家族（Chai-1/Boltz-2/Protenix）误差相关性高、AF2m 正交性最强；推荐默认 2-model = Chai-1 + AF2m（Protenix v2 上线后升级为 ①）；共识阈值随模式调整（2/2 vs 3/4）。(8) 冗余修复：① Step 2.dedup 删除错误 MMseqs2 MCP 引用；② Step 3.6 AF2Rank 条件逻辑改为"AF2m 默认运行 → 总是免费复用"；③ Step 1.4/4.6 glycoengineering 加 input 标注；④ "5路径" → "4路径"；⑤ L4.3 AbMPNN 取消 Path D 复用 D2 分数捷径，4 路径统一在 L3 复合物结构重打分。(7) Path D (BindCraft) 移出主流程：BindCraft 是通用蛋白 binder 工具，非 VHH 专用；Path B (Germinal) 是抗体优化版替代，4 路径降为标准。(1) L3.0 Ibex 改 `ibex_predict_batch`; (2) L4 顺序调整（protein-sol 升至 4.2，AbMPNN 降至 4.3）; (3) Step 2.dedup MMseqs2 去重; (4) Step 2.diversity 5路径多样性诊断 → 4路径; (5) Track B 三档距离判定 + 两条自动召回规则; (6) 阈值 Tier1/Tier2 分层校准. Previous: L4.2 ESM PLL → AbMPNN scoring; L3.6 AF2Rank CONDITIONAL.

Maximum-success-rate VHH (nanobody) de novo design pipeline. Combines **4 orthogonal generation tools** (BoltzGen / Germinal / IgGM / RFdiffusion+AbMPNN), **2-model (default) or 3-model (high-confidence) AF3-family co-folding validation** (Chai-1+Boltz-2 default; +Protenix when v2 weights available; AF2m removed after SNAC-DB 2026 Nb-Ag benchmark showed 9.9% Rank-1 success — tied worst), strict developability funnel, and affinity maturation loop. Designed to maximize experimental hit rate when compute budget is not the primary constraint.

> **BindCraft 不在此 pipeline：** BindCraft 是通用蛋白 binder 工具（hallucination-based），不具备 VHH 特异性（无 IMGT FR 感知、无 germline 约束）。Germinal (Path B) 是更适合抗体的替代方案。如需 BindCraft 做通用蛋白设计，使用 `adaptyv:bindcraft` skill。

**Parallel to `nanobody_design.md`**: that skill is a single-path (BoltzGen) workflow; this skill is a multi-path pipeline for higher success rate.

---

## Prerequisites

Before running this workflow, install the skill and all required MCPs:

```bash
# pskill 位于 ~/claude-project/ProteinMCP/.venv/bin/pskill
# 若未在 PATH，先激活 venv 或用绝对路径：
source ~/claude-project/ProteinMCP/.venv/bin/activate
pskill install vhh_max_success_design
```

This will install the following MCP servers:
- `bindcraft_mcp` — (**NOT USED in VHH pipeline**; BindCraft is a general protein binder tool, use `adaptyv:bindcraft` skill instead)
- `boltzgen_mcp` — BoltzGen all-atom generation (nanobody-anything protocol)
- `chai1_mcp` — Chai-1 structure prediction (validation model 1)
- `boltz2_mcp` — Boltz-2 structure prediction (validation model 2; affinity module not used — not validated for VHH-antigen interfaces)
- `protenix_mcp` — Protenix structure prediction (validation model 3; **v2 default with `use_tfg_guidance=True` once weights re-open, currently v1**)
- `ibex_mcp` — VHH/Ab monomer structure prediction (Step 2.ibex sanity check, moved to Layer 2 end before hotspot prescreen; replaces NanoBodyBuilder2; non-commercial license per `reference_mcp_tools.md`)
- `iggm_mcp` — IgGM epitope-conditioned CDR design (Path C; per `reference_mcp_tools.md`)
- `rfdiffusion2_mcp` — (NOT USED; listed here only to avoid accidental install; RFdiffusion v1 is used via modal script)
- `ligandmpnn_mcp` — AbMPNN sequence design for VHH (checkpoint: `abmpnn` via ligandmpnn_mcp infrastructure; fallback: `proteinmpnn_v_48_020`)
- `stability_oracle_mcp` — ΔΔG mutation scanning
- `netMHCpan_mcp` — MHC-I immunogenicity scan (mandatory per `reference_vhh_max_success_skill.md`)
- `netMHCIIpan_mcp` — MHC-II immunogenicity scan
- `protein-sol_mcp` — Solubility prediction
- `interpro` — Target domain annotation
- `mmseqs2` — Target MSA generation

**Local CLI dependencies（需本地安装，非 MCP）：**
- `mmseqs` CLI — Step 2.dedup 序列聚类去重（`mmseqs easy-cluster`）。安装：`brew install mmseqs2` 或 `conda install -c bioconda mmseqs2`。验证：`mmseqs --version`。注意：`mcp__mmseqs2` 是 MSA 工具，不能用于聚类，两者完全独立。

**Non-MCP modal scripts used directly** (via `modal run`):
- `modal_germinal.py` — Germinal VHH de novo (germline-aware)
- `modal_rfantibody.py` — RFantibody backbone generation (antibody-finetuned RFdiffusion; **replaces `modal_rfdiffusion.py` for Path D Step D1** as of 2026-04-29); accepts pre-generated HLT file via `--hlt` (see `scaffold2hlt.py`); chain H = VHH output
- `scaffold2hlt.py` — Local script (not Modal): converts scaffold clean PDB + YAML → RFantibody HLT format; reads CDR boundaries from YAML `design` block (not Chothia hardcoded); usage: `python ~/biomodals/scaffold2hlt.py --pdb <clean.pdb> --yaml <scaffold.yaml> --output <hlt.pdb>`
- `modal_rfdiffusion.py` — RFdiffusion v1 general partial diffusion (kept for non-antibody binder tasks; no longer used in VHH max-success pipeline Path D)
- ~~`modal_alphafold.py` — AF2 multimer~~ **(DEPRECATED 2026-05-12)**: AF2m removed from L3 validation. SNAC-DB (Sanofi 2026) NANOBODY-Ag Rank-1 = 9.9% (tied worst with OpenFold-3p2); Protenix-v1 = 23.8% (best). Architectural orthogonality (AF2 MSA+Evoformer vs AF3 family) does not survive contact with empirical Nb-Ag benchmark.
- `modal_anarci.py` — IMGT/Kabat VHH numbering
- `modal_esm2_pll.py` — ~~ESM2 sequence plausibility (PLL)~~ **(deprecated in L4.2; replaced by AbMPNN scoring mode — see Step 4.2)**
- `modal_esm2_predict_masked.py` — ESM2 masked residue suggestion (optional L5)
- `modal_mber.py` — MBER affinity maturation
- ~~`modal_af2rank.py` — AF2Rank structural re-identification~~ **(DEPRECATED 2026-05-12)**: AF2Rank requires AF2 outputs; with AF2m removed from L3, this step has no input. Its original role (VHH monomer fold self-consistency) is already covered by Step 2.ibex.
- `modal_pdb2png.py` — PyMOL visualization for report

**Adaptyv skills referenced** (loaded on demand via `Skill` tool):
- `adaptyv:ipsae` — Binder ranking (L3.5)
- `adaptyv:foldseek` — IP / structural similarity annotation (L3 end; annotate `ip_risk`, do not auto-drop)
- `adaptyv:pdb` / `adaptyv:uniprot` — L1 target fetching（备用，主路径用 gget）

**Global memory files this skill enforces**:
- `reference_vhh_max_success_skill.md` — NetMHCpan I+II mandatory (NetMHCpan 节) + MPNN choice on Path D (MPNN 选型节)
- `domain_protein_design_gotchas.md` — rule #1 (CDR/FR inseparable), rule #2 (cross-model ipTM not comparable)
- `reference_mcp_tools.md` — ibex_mcp usage + non-commercial license caveat; iggm_mcp FASTA format + epitope conditioning
- `feedback_dsasa_filter.md` — CDR3 dSASA filter usage (L3.5b)

---

## Configuration Parameters

> **模型矩阵 / Step 3.5 阈值 / binding_composite 权重 / flag 降权因子**：单一 source-of-truth 在 `~/.claude/skills/vhh-max-success-design/scripts/config.py`（S2 集中化，2026-05-12）。本节 YAML 仅列实验性参数（生成器配额、Layer 4 阈值等）。

```yaml
# === Target ===
TARGET_CIF: "@inputs/target.cif"              # Target structure (CIF preferred)
TARGET_CHAIN: "A"                              # Chain to bind
EPITOPE_RESIDUES: "45,67,89,91,93"            # Epitope residues (author numbering)
HOTSPOT_RESIDUES: "67,89,91"                  # Subset for design conditioning (3-6)

# === VHH scaffolds — TWO LIBRARIES, PATH-SPECIFIC ===
#
# (A) BoltzGen Path A 专用：~/protein-design-utils/vhh/scaffolds/boltzgen_official/
#     来源：BoltzGen 官方 example/nanobody_scaffolds/（HannesStark/boltzgen, 2026-05-08）
#     CDR 边界：Chothia 结构 loop tip + 1 buffer，逐 scaffold 视检标定
#     **必须用此库** — 旧中央库的 H2=Kabat 50..65 会破坏 V_H 折叠（16F9 实测 91% miss rate，13/4 scaffold × 100 designs 仅 2 个真接触 hotspot）
#     启动新靶点前 cp ~/protein-design-utils/vhh/scaffolds/boltzgen_official/yaml/*.yaml inputs/boltzgen_scaffolds/
#                  cp ~/protein-design-utils/vhh/scaffolds/boltzgen_official/cif/*.cif   inputs/boltzgen_scaffolds/
VHH_SCAFFOLDS_BOLTZGEN:
  - "@inputs/boltzgen_scaffolds/7eow.yaml"        # H1=26..34 H2=52..59 H3=98..118 (21) | 长 H3
  - "@inputs/boltzgen_scaffolds/7xl0.yaml"        # H1=26..33 H2=51..57 H3=97..110 (14) | Vobarilizumab/IL6R
  - "@inputs/boltzgen_scaffolds/8coh.yaml"        # H1=26..33 H2=51..58 H3=97..115 (19) | Gefurulimab/C5
  - "@inputs/boltzgen_scaffolds/8z8v.yaml"        # H1=26..33 H2=51..58 H3=98..108 (11) | 短 H3
  - "@inputs/boltzgen_scaffolds/gontivimab.yaml"  # H1=26..32 H2=52..57 H3=100..116 (17)
  - "@inputs/boltzgen_scaffolds/isecarosmab.yaml" # H1=26..32 H2=52..57 H3=99..108 (10)
  - "@inputs/boltzgen_scaffolds/sonelokimab.yaml" # H1=26..30 H2=50..55 H3=97..111 (15) | IL-17
#
# (B) 其他路径（IgGM / RFantibody / Germinal）专用：~/protein-design-utils/vhh/scaffolds/yaml/
#     来源: TheraSAbDab v19 + Evers et al. mAbs 2025 文献挖掘
#     结构聚类 (d=0.25, Cα RMSD + seqid 组合) 选 8 个代表，覆盖 2 个主要胚系
#     CDR 边界：Kabat-based（gen_scaffold_yamls.py 生成）— 这些工具内部不复用 BoltzGen yaml，所以 H2 宽窄不影响
#     启动新靶点前 cp ~/protein-design-utils/vhh/scaffolds/yaml/*.yaml inputs/scaffolds/
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
L2_RFANTIBODY_BACKBONES: 500          # renamed from L2_RFDIFFUSION_BACKBONES (Path D now uses RFantibody)
L2_MPNN_SEQS_PER_BACKBONE: 8

# === Layer 2.5 hotspot pre-screen ===
L2P5_HOTSPOT_MIN_CONTACTS_TRACK_A: 2  # Track A (on-target)：进入主 L3 验证池（gB-VHH N=200 伪AUC校准 2026-04-15）
L2P5_HOTSPOT_MIN_CONTACTS_TRACK_B: 0  # [DEPRECATED] Track B 分流已改为 ipTM 阈值判定（boltz2_independent_iptm >= L4_IPTM_MIN），contacts 数量不再是 Track B 触发条件；此参数保留仅供参考，下游不读取
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
L5_MBER_TOP_N: 20                             # Top N from L4 enter MBER (L4 now outputs ~5–15; 20 is safe upper bound)

# === Per-path multi-seed convergence (optional, 5× cost) ===
L3_MULTI_SEED_MODE: false                     # true = run 5 seeds per candidate; activates pose convergence scoring
L3_MULTI_SEED_COUNT: 5                        # Seeds per candidate when L3_MULTI_SEED_MODE=true
L3_POSE_CONVERGENCE_RMSD: 4.0                 # CDR3 Cα RMSD threshold for convergence (Å, aligned on antigen)
L3_POSE_CONVERGENCE_MIN_SEEDS: 3              # Min converging seeds to count as convergent

# === Step 2.negctrl Sub-step C/D — Unrelated antigen null (S5 added 2026-05-12) ===
DECOY_PANEL_DIR: "~/protein-design-utils/vhh/decoy_panel/"  # Reusable across projects; build once via build_decoy_panel.py
DECOY_N_PANEL: 3                              # Number of decoy antigens to use per candidate (3–10; cost scales linearly); 3 = lean mode
DECOY_SEEDS_PER_CANDIDATE: 1                  # Seeds per (candidate × decoy) pair; 1 = lean; 3 = full
UNRELATED_NULL_PERCENTILE: 95                 # Real candidate must beat this %ile of null distribution to pass

# === Step 2.seqfilter (sequence pre-filter, before any structure prediction) ===
SEQ_PI_MIN: 4.0                            # pI lower bound (too acidic → poor expression)
SEQ_PI_MAX: 10.0                           # pI upper bound (too basic → aggregation risk)
SEQ_NET_CHARGE_MIN: -8                     # Net charge at pH 7.4 lower bound
SEQ_CDR3_LEN_MIN: 8                        # CDR3 min length (aa)
SEQ_CDR3_LEN_MAX: 22                       # CDR3 max length (aa)

# === Layer 3 two-round co-folding ===
L3A_SEEDS: 5                               # Seeds per candidate in L3.A (coarse screen); fallback: 3 seeds if compute-constrained
L3A_COARSE_PASS_N: 150                     # Max candidates advancing L3.A → L3.B
L3A_MIN_CONVERGE_SEEDS: 2                 # Min converging seeds required in L3.A
L3B_SEEDS: 5                               # Seeds per candidate in L3.B (when MULTI_SEED_MODE=true)
L3_CLASH_MAX_PAIRS: 3                      # Max Cβ-Cβ < 3.4Å pairs at interface (clash filter)
L3_CDR_DOMINANCE_SOFT_FLAG: 0.50           # CDR 主导度软阈值：< 0.50 时 flag（cdr_dominance_low_flag=True），不删除
L3_CDR_DOMINANCE_HARD_DROP: 0.25          # CDR 主导度硬阈值：< 0.25 时 hard drop（FR 堆积为主，paratope 贡献极低）

# === Final experimental set (Step 4.7b combinatorial) ===
FINAL_CANDIDATE_TARGET: 48                 # Total synthesis candidates: 24 / 48 / 96
FINAL_TOP_SCORING_FRAC: 0.50              # structural_consensus: Pareto rank 1–2，高结构共识
FINAL_DIVERSITY_FRAC: 0.17                # cdr3_diversity: 高分池外 CDR3 Levenshtein 最大化贪心采样
FINAL_EPITOPE_DIV_FRAC: 0.12             # epitope_diversity: 按 predicted_epitope_cluster 聚类取代表
FINAL_PATH_REP_FRAC: 0.12                 # path_quota: 每条生成路径 Pareto 最高分代表（4 路径均须有代表）
FINAL_DEV_FRAC: 0.04                      # high_developability: 结构分数中等但 protein-sol / humanness / mhc_risk_score 优秀
FINAL_EXPLOR_FRAC: 0.04                   # exploratory: 模型分歧大但 pose 有趣的候选
PATH_QUOTA_PER_10:                         # Per-path quota per 10 slots (scales with FINAL_CANDIDATE_TARGET)
  rfantibody: 4
  boltzgen: 2
  germinal: 2
  iggm: 2

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
>    - **Layer 3（验证）两轮并行**：L3.A 的 Boltz-2 + Protenix 并行提交（3 seeds each）；L3.A gate 后，L3.B 选定的 2–4 模型再次并行提交
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

**Tool:** `gget` skill（主路径：`gget pdb <ID>` 下载结构，`gget uniprot <ID>` 获取序列/注释；备用：`/adaptyv:pdb` 或 `/adaptyv:uniprot`）

- Fetch target structure (CIF preferred, fallback PDB)
- Trim to binding region + 10 Å buffer
- Remove waters, ions, irrelevant ligands
- Extract sequence; verify chain boundaries
- Check oligomeric state: verify UniProt 'Subunit structure' annotation; record in `inputs/target_oligomer_state.txt` (`monomer` / `homodimer` / `homotrimer` / `heterodimer:<chains>`). **L3 validation must use the physiological oligomeric form**, even if design was run on monomer — a single protomer cannot reproduce the real binding interface geometry in homo/hetero-multimer targets.

### Step 1.2 — Target domain annotation（单靶点模式）

**Tool:** `mcp__interpro__analyze_protein_sequence`

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

**Tools:** `paper-lookup` skill (PubMed / bioRxiv / clinical literature), `WebSearch` (ClinicalTrials.gov)

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

- Input: target CIF + **`VHH_SCAFFOLDS_BOLTZGEN`（7 个 BoltzGen 官方 scaffold，Chothia CDR）**
  - ⚠️ **不要用 `VHH_SCAFFOLDS`（中央临床库）**——其 H2=Kabat 50..65 会破坏 V_H 折叠（16F9 实测 91% miss rate）
- Protocol: `nanobody-anything`
- `num_designs`: `L2_BOLTZGEN_NUM_DESIGNS` per scaffold
- Output: inverse-folded CIFs → `{RESULTS_DIR}/gen/boltzgen/`
- Post-filter: `modal_boltzgen.py` built-in cysteine filter

**Step A0 — 准备 scaffold + 生成完整 BoltzGen YAML（提交前必须先跑）：**

```bash
cd {PROJECT_DIR}
# 1. 复制 BoltzGen 官方 scaffold 到项目 inputs（首次启动靶点时执行一次）
mkdir -p inputs/boltzgen_scaffolds
cp ~/protein-design-utils/vhh/scaffolds/boltzgen_official/yaml/*.yaml inputs/boltzgen_scaffolds/
cp ~/protein-design-utils/vhh/scaffolds/boltzgen_official/cif/*.cif   inputs/boltzgen_scaffolds/

# 2. 生成项目 yaml（在每个 scaffold yaml 末尾追加 target + binding_types）
python ~/protein-design-utils/vhh/gen_boltzgen_yamls.py \
  --antigen {TARGET_CIF} \
  --scaffold-dir inputs/boltzgen_scaffolds \
  --num-designs {L2_BOLTZGEN_NUM_DESIGNS} \
  --results-dir {RESULTS_DIR}/gen/boltzgen
```

- 自动读取 `inputs/boltzgen_scaffolds/*.yaml`（保留官方 design block 不动）+ `inputs/hotspots.json`（`hotspot_residues` 键）
- 自动检测抗原 chain_start（可用 `--chain-start` 覆盖）
- 输出：`inputs/boltzgen/<scaffold>.yaml`（官方模板 + 追加 target entity + binding_types）+ 终端打印提交清单
- ⚠️ **`gen_boltzgen_yamls.py` 必须支持 `--scaffold-dir` 参数**：原版从 `inputs/scaffolds/` 读取（中央库），现在改为可指定。如果脚本未更新，先手动追加 target/binding_types 到 `inputs/boltzgen_scaffolds/<name>.yaml`，**不要重写 design block**

**Step A1 — 提交（MCP，每个 scaffold 一条）：**

Step A0 清单已打印每个 scaffold 的完整参数，直接读取使用：

```python
mcp__boltzgen_mcp__boltzgen_design(
    yaml_str=Path("inputs/boltzgen/{SCAFFOLD}.yaml").read_text(),
    output_dir="<来自 Step A0 清单 output_dir 列>",
    additional_file_paths=["<来自 Step A0 清单 additional_file_paths 列，已是绝对路径>"],
    protocol="nanobody-anything",
    num_designs={L2_BOLTZGEN_NUM_DESIGNS},
)
```

> Step A0 清单已打印每个 scaffold 的 `output_dir` 和 `additional_file_paths`（绝对路径），直接复制，无需手动拼接。

### Path B — Germinal VHH (Priority P1)

**Tool:** `modal run modal_germinal.py`

> **⚠️ 无 MCP 封装，无 job ID 追踪。** Germinal 不支持 `--detach`，在 Hybrid 并行模式下需单独处理：
> ```bash
> # Hybrid 模式：后台运行，输出重定向到日志文件
> modal run modal_germinal.py \
>   --run-type vhh \
>   --max-trajectories L2_GERMINAL_TRAJECTORIES \
>   --max-passing-designs L2_GERMINAL_PASSING \
>   > {RESULTS_DIR}/gen/germinal/run.log 2>&1 &
> echo "Germinal PID: $!"
> # 完成判断：ls {RESULTS_DIR}/gen/germinal/*.pdb | wc -l 达到预期数量
> ```

- Prerequisite: `germinal-models` Volume initialized (see `feedback_biomodals.md`)
- Build `inputs/germinal_target.yaml` with target PDB + epitope + hotspots
- Output: germline-aware VHH sequences + AF2 predictions → `{RESULTS_DIR}/gen/germinal/`

### Path C — IgGM epitope-conditioned design (Priority P2)

**⚠️ 提交前必读 `reference_mcp_tools.md` IgGM 节（2026-04-30 实测修正）**

**Step C0 — 输入文件准备（新项目必须先跑）：**
```bash
python ~/protein-design-utils/vhh/gen_iggm_fastas.py \
  --scaffolds 7a6o_B 7dv4_B 7xl0_B 8coh_A \
  --antigen inputs/<target>_chainA.pdb \
  --antigen-chain A \
  --out-dir inputs/iggm/
```

**Step C1 — 提交（MCP，4 scaffold 并行）：**

**Tool:** `mcp__iggm_mcp__iggm_design`

> ⚠️ 使用 `antigen_pdb_path`（绝对路径），**不用** `antigen_pdb_str`。
> 抗原 PDB 通常 >100KB，超过 Claude Code Read 工具 256KB context 上限；server 直接读文件无大小限制。
> `antigen_pdb_str` 仅用于 <100KB 的小片段。

关键参数规则（违反任一条会静默产出错误结果）：
- `input_fasta_str`：**`>A` body 必须填完整抗原氨基酸序列**（留空 → `aa_seq=None` crash）
- `epitope`：sequential 1-based 编号（auth_seq_id − 链起始偏移），**见项目 hotspots 文件**
- ⚠️ **禁止传 `max_antigen_size`**：会导致 IgGM 以 epitope 为中心截取窗口，epitope index 在截断子序列里全部错位；IgGM 默认 2000，585 aa 以内 A10 无 OOM

```python
mcp__iggm_mcp__iggm_design(
    input_fasta_str=open("inputs/iggm/{SCAFFOLD}.fasta").read(),
    antigen_pdb_path="/abs/path/to/{TARGET}_chainA.pdb",   # ← 不用 antigen_pdb_str
    epitope="{EPITOPE_SEQ}",
    task="design",
    num_samples=L2_IGGM_SAMPLES,
    run_name="prod_100",
    output_dir="{RESULTS_DIR}/gen/iggm/{SCAFFOLD}",
)
```

> 若 MCP 不可用，fallback 到 CLI（`run_in_background: true` 必须加，见 feedback_error_patterns.md）：
> ```bash
> modal run --detach ~/biomodals/modal_iggm.py \
>   --input-fasta inputs/iggm/{SCAFFOLD}.fasta \
>   --antigen inputs/{TARGET}_chainA.pdb \
>   --epitope "{EPITOPE_SEQ}" \
>   --task design --num-samples {L2_IGGM_SAMPLES} --run-name prod_100 \
>   --out-dir {RESULTS_DIR}/gen/iggm/{SCAFFOLD}
> ```

- 速度：~172 s/sample（全长抗原），100 samples ≈ 5h/scaffold
- IgGM 输出是真实 bound complex（chain H + chain A），epitope 约束有效（实测接触距离 1–4 Å）
- Output: per-sample VHH PDBs → `{RESULTS_DIR}/gen/iggm/<scaffold>/prod_100/`

### Path D — RFantibody + AbMPNN (Priority P3)

**Tools:** `modal run modal_rfantibody.py` → `mcp__ligandmpnn_mcp__ligandmpnn_design`

> **Updated 2026-04-29:** Step D1 now uses **RFantibody** (antibody-finetuned RFdiffusion) instead of vanilla RFdiffusion v1. Same D2/D3 logic; only the backbone generation checkpoint and input format changed.

**Step D1 — Backbone generation (RFantibody):**

```bash
# Step 0 (once per scaffold): generate HLT file
python ~/biomodals/scaffold2hlt.py \
  --pdb inputs/scaffolds/{SCAFFOLD}_clean.pdb \
  --yaml inputs/scaffolds/{SCAFFOLD}.yaml \
  --output inputs/rfantibody/{SCAFFOLD}.hlt.pdb

# Step D1: backbone generation
modal run --detach modal_rfantibody.py \
  --target {TARGET_PDB} \
  --hlt inputs/rfantibody/{SCAFFOLD}.hlt.pdb \
  --target-chain {TARGET_CHAIN} \
  --hotspots "{HOTSPOT_RESIDUES}" \
  --design-loops "H1:10,H2:16,H3:{min}-{max}" \
  --num-designs {L2_RFANTIBODY_BACKBONES} \
  --out-dir {RESULTS_DIR}/gen/rfantibody/{SCAFFOLD}
```

- **Checkpoint:** `RFdiffusion_Ab.pt` (Baker lab; fine-tuned on SAbDab antibody structures)
- **HLT pre-generation:** use `scaffold2hlt.py` locally before running Modal; CDR boundaries from YAML `design` block (not Chothia hardcoded); `chothia2HLT.py` is deprecated (hardcodes H3=Chothia 95-102, misses full CDR3)
- **design-loops H3 range:** scaffold CDR3 length (from YAML) as min, min+14 as max; see per-project `inputs/rfantibody/design_loops.json`
- **Output chain:** VHH binder = **chain H** (HLT convention; differs from vanilla RFdiffusion which uses chain B)
- **Design loops syntax:** `H1:len,H2:len,H3:min-max` — loops not listed are fixed from scaffold
- **Hotspot format:** residue numbers only (e.g. `"67,89,91"`); script prepends target chain automatically
- Run per scaffold; results accumulate in `{RESULTS_DIR}/gen/rfantibody/`
- **Pre-run required:** before starting D1, run ANARCI on one scaffold HLT output to get IMGT CDR positions for Step D2:
  ```bash
  # Run AFTER first scaffold's D1 completes (or on the scaffold CIF directly)
  modal run modal_anarci.py \
    --input-fasta {RESULTS_DIR}/gen/rfantibody/{SCAFFOLD}/scaffold_seq.fasta \
    --params "--scheme imgt --csv"
  # Read CDR H1/H2/H3 residue ranges from output → use in D2 cdr_positions
  ```

**Step D2 — Sequence design (AbMPNN, strict FR mode):**
- **Use `model_checkpoint: "abmpnn"`** (Exscientia, arXiv:2310.19513): ProteinMPNN fine-tuned on SAbDab antibody structures; ~60% sequence recovery vs ~35% for generic ProteinMPNN; 100% valid antibody sequences
- **Do NOT use SolubleMPNN** per `reference_vhh_max_success_skill.md`
- `vhh_framework_mode: "strict"` to lock FR, design CDR only
- **`vhh_chain: "H"`** — RFantibody 输出的 binder 固定在 chain H（HLT 约定），必须显式指定，否则 MCP 默认 chain A（错误链）
- **`cdr_positions: {"H": [<CDR1 residues>, <CDR2 residues>, <CDR3 residues>]}`** — strict 模式的必填参数（见 MCP schema）。CDR 编号来源：Step D1 pre-run ANARCI on scaffold HLT（IMGT scheme，chain H）。不能用 L4.1 的 ANARCI 结果（那时 D2 已完成）。
- `num_seq_per_target: L2_MPNN_SEQS_PER_BACKBONE`
- Reason: AbMPNN preserves CDR paratope aromatic/hydrophobic bias (same as ProteinMPNN) while better capturing antibody sequence grammar; solubility filtered downstream in L4 via `protein-sol_mcp`
- Fallback: if AbMPNN weights unavailable, use `model_checkpoint: "proteinmpnn_v_48_020"`

**Step D3 — Pool merge:**
- Output: ~4000 sequences → protein-sol pre-filter (step 4.2) → ~500 → `{RESULTS_DIR}/gen/rfantibody/`
- D2 AbMPNN 分数（基于 RFdiffusion 骨架）已在此完成其使命：作为 Path D 内部生成过滤器（4000 → 500）。**不作为 L4.3 的替代**——L4.3 会对所有路径统一在 L3 复合物结构上重新打分。

### Step 2.merge — Candidate pool consolidation

- Unify all 4 paths' outputs into a single candidate table: `{RESULTS_DIR}/val/filter/merged_pool.csv`
- Columns: `cand_id, source_path, sequence, structure_path, structure_format, source_job_id`
- Expected size: 1000–1500 candidates

**各路径 structure 格式说明（`structure_path` + `structure_format` 两列）：**

| 路径 | structure_path 内容 | structure_format | 说明 |
|------|-------------------|-----------------|------|
| Path A (BoltzGen) | BoltzGen 输出 CIF（含 VHH + 抗原复合物） | `cif` | 可直接用于 L2.5 hotspot prescreen |
| Path B (Germinal) | Germinal 内置 AF2 输出 PDB（含复合物） | `pdb` | 可直接用于 L2.5 hotspot prescreen |
| Path C (IgGM) | IgGM 输出 PDB（含 VHH + 抗原复合物） | `pdb` | 可直接用于 L2.5 hotspot prescreen |
| Path D (RFantibody+MPNN) | RFantibody 骨架 PDB（含 VHH + 抗原，**Chain H = binder**） | `pdb` | AbMPNN 只输出序列，结构复用 RFantibody 骨架；L2.5 以骨架做 hotspot 判断，L3 之后才有序列特异性复合物结构 |

**步骤注意：** L2.5 `hotspot_prescreen.py` 支持读取 `structure_format` 列自动选择解析器（CIF/PDB 均兼容）。Step 3.0 ibex 仅需 `sequence` 列，与 `structure_path` 无关。

### Step 2.dedup — MMseqs2 sequence deduplication (2-phase)

**Tools:** `mmseqs easy-cluster` (CLI), then `~/protein-design-utils/vhh/apply_cluster_repr.py`

> **注意：** `mcp__mmseqs2` 是 MSA 生成工具（多序列比对），**不能用于序列聚类**。此步骤直接调用 `mmseqs easy-cluster` CLI。

**Goal:** 两阶段去重——路线内先压缩冗余，跨路线保留独立 hit。**关键原则：不同生成器独立收敛到同一候选是强正信号，不删。**

**Phase 1 — Intra-path CDR3 deduplication (80% identity, per source_path):**

```bash
# 对每条路线分别运行
for PATH in boltzgen germinal iggm rfantibody; do
  # 提取该路线候选的 CDR3 序列（新增 --source-path + --cdr3-only 参数）
  python ~/protein-design-utils/vhh/pool_to_fasta.py \
    {RESULTS_DIR}/val/filter/merged_pool.csv \
    --source-path ${PATH} \
    --cdr3-only \
    --out {RESULTS_DIR}/val/filter/dedup/${PATH}_cdr3.fasta

  mmseqs easy-cluster \
    {RESULTS_DIR}/val/filter/dedup/${PATH}_cdr3.fasta \
    {RESULTS_DIR}/val/filter/dedup/${PATH}_intra \
    /tmp/mmseqs_tmp_${PATH} \
    --min-seq-id 0.80 --cov-mode 1 -c 0.8

  python ~/protein-design-utils/vhh/apply_cluster_repr.py \
    --pool {RESULTS_DIR}/val/filter/merged_pool.csv \
    --source-path ${PATH} \
    --clusters {RESULTS_DIR}/val/filter/dedup/${PATH}_intra_cluster.tsv \
    --out {RESULTS_DIR}/val/filter/dedup/${PATH}_intra_dedup.csv
done

# 合并各路线去重结果（新工具）
python ~/protein-design-utils/vhh/merge_path_pools.py \
  {RESULTS_DIR}/val/filter/dedup/boltzgen_intra_dedup.csv \
  {RESULTS_DIR}/val/filter/dedup/germinal_intra_dedup.csv \
  {RESULTS_DIR}/val/filter/dedup/iggm_intra_dedup.csv \
  {RESULTS_DIR}/val/filter/dedup/rfantibody_intra_dedup.csv \
  --out {RESULTS_DIR}/val/filter/dedup/intra_dedup_pool.csv
```

**Phase 2 — Cross-path 95% identity deduplication (only true duplicates):**

```bash
python ~/protein-design-utils/vhh/pool_to_fasta.py \
  {RESULTS_DIR}/val/filter/dedup/intra_dedup_pool.csv \
  --out {RESULTS_DIR}/val/filter/dedup/intra_dedup_pool.fasta

mmseqs easy-cluster \
  {RESULTS_DIR}/val/filter/dedup/intra_dedup_pool.fasta \
  {RESULTS_DIR}/val/filter/dedup/cross \
  /tmp/mmseqs_tmp_cross \
  --min-seq-id 0.95 --cov-mode 1 -c 0.8

# --cross-path-keep-all：同一 cluster 内若来自不同路线，各保留最高分代表（不合并）
python ~/protein-design-utils/vhh/apply_cluster_repr.py \
  --pool {RESULTS_DIR}/val/filter/dedup/intra_dedup_pool.csv \
  --clusters {RESULTS_DIR}/val/filter/dedup/cross_cluster.tsv \
  --cross-path-keep-all \
  --out {RESULTS_DIR}/val/filter/dedup_pool.csv
```

- Output: `{RESULTS_DIR}/val/filter/dedup_pool.csv` — deduplicated candidate table
- Expected size: 1000–1500 → ~700–1100（路线内 80% 聚类压缩 ~15–20%，跨路线真重复 <10%）
- **新工具**（需添加到 `~/protein-design-utils/vhh/`）：`merge_path_pools.py`；`pool_to_fasta.py` 需新增 `--source-path` + `--cdr3-only` 参数；`apply_cluster_repr.py` 需新增 `--source-path` + `--cross-path-keep-all` 参数

### Step 2.seqfilter — Sequence-level pre-filter（零 GPU，结构预测前）

**Goal:** 在提交任何结构预测之前，用纯序列规则过滤掉 developability 不达标的候选，节省大量 L3 GPU 算力。所有检查均零额外计算资源。

> **ANARCI 从 L4.1 提前至此步：** L4.1 改为直接读取本步输出，不再重跑。`humanness_score`（`v_identity`）同时写入候选表，L4.7 Pareto 直接使用。

**Tool:** `~/protein-design-utils/vhh/seq_prefilter.py`（新工具，需实现）

```bash
python ~/protein-design-utils/vhh/seq_prefilter.py \
  --pool {RESULTS_DIR}/val/filter/dedup_pool.csv \
  --pi-min {SEQ_PI_MIN} --pi-max {SEQ_PI_MAX} \
  --net-charge-min {SEQ_NET_CHARGE_MIN} \
  --cdr3-len-min {SEQ_CDR3_LEN_MIN} --cdr3-len-max {SEQ_CDR3_LEN_MAX} \
  --anarci-scheme imgt --assign-germline \
  --out {RESULTS_DIR}/val/filter/seq_aa_filtered_pool.csv \
  --rejected {RESULTS_DIR}/val/filter/seq_filter_rejected.csv
```

**7 项检查（顺序即优先级，越便宜越靠前）：**

| 检查 | 方法 | 阈值 | 失败动作 |
|------|------|------|---------|
| CDR3 长度 | ANARCI IMGT CDR3 residue count | 8–22 aa（`SEQ_CDR3_LEN_MIN/MAX`） | **Drop**（generator 失败，不可救） |
| 非配对 Cys | CDR 区 Cys count 奇偶判断 | 奇数 → 非配对双硫桥 | **Drop**（结构失败，不可救） |
| ANARCI 编号 | `modal run modal_anarci.py --scheme imgt --assign_germline --use_species human` | 编号失败 OR FR 边界异常 | **Drop**（序列非法） |
| N-glycan motif（CDR） | regex `N[^P][ST]` in CDR1/CDR2/CDR3 | 任意匹配 → 标注 `cdr_glycan_count` 列 + `rescue_suggestion="N→Q at pos X"` | **Flag**（2026-05-12 改：N→Q 单点突变可救，进 Pareto `glycan_count` 含 CDR） |
| 极端 pI | BioPython `ProteinAnalysis.isoelectric_point()` | < 4.0 或 > 10.0 → 标注 `pi_extreme_flag` + `pi_value` | **Flag**（2026-05-12 改：可通过 surface charge engineering 缓解，进 Pareto `seq_risk_count`） |
| 极端净电荷 | BioPython `ProteinAnalysis.charge_at_pH(7.4)` | < −8 → 标注 `net_charge_extreme_flag` + `net_charge_value` | **Flag**（2026-05-12 改：同上，进 Pareto `seq_risk_count`） |
| N-glycan motif（FR） | regex `N[^P][ST]` in FR1/FR2/FR3/FR4，与 scaffold 序列对比 delta | 新引入 sequon → 标注 `fr_glycan_new_count` 列（不硬删，进 Pareto `glycan_count` 目标；FR 糖基对结合影响小于 CDR，但影响生产工艺） | Flag |

> **序列过滤三步串行（2.seqfilter → 2.solfilter → 2.mhcfilter），共同产出 `val/filter/seq_filtered_pool.csv`。** 中间文件写入 `val/filter/`，主链文件只有一个最终输出，断点重跑可从任意中间文件恢复。

- Output: `{RESULTS_DIR}/val/filter/seq_aa_filtered_pool.csv`（含 `fr_glycan_new_count` 列，debug 中间文件）
- `{RESULTS_DIR}/val/filter/seq_filter_rejected.csv` 含 `rejection_reason` 列，不删除原始记录
- Expected attrition: ~700–1100 → ~600–950（约 10–15%）

### Step 2.solfilter — Solubility pre-filter（序列级，L3 之前淘汰低溶解度候选）

**Tool:** `mcp__protein-sol_mcp__protein_sol_solubility_predict`

**Why here:** protein-sol 只需序列，零 GPU，零结构依赖。放在 L3 之前可避免为低溶解度候选浪费全部结构预测算力。

- Input: `{RESULTS_DIR}/val/filter/seq_aa_filtered_pool.csv`
- 批量提交所有候选序列；protein-sol_mcp 返回 `solubility_score` 列
- **2026-05-12 改 hard drop → soft flag**：`protein_sol_score < L4_PROTEIN_SOL_MIN`（默认 0.45）→ 标注 `low_solubility_flag=True`，不删；连续值 `protein_sol` 已在 Step 4.4 Pareto 作目标维度，重复 hard drop 会丢 IgGM/Germinal borderline 候选（实测 protein-sol 阈值与 VHH 实际可溶性相关性弱）
- Output: `{RESULTS_DIR}/val/filter/seq_sol_filtered_pool.csv`（debug 中间文件）
- Expected attrition: 0（仅 flag，无淘汰；连续值进 Pareto 自然降权）

### Step 2.mhcfilter — 免疫原性预筛（序列级，治疗安全性 fail-fast）

**Tools:** `mcp__netMHCpan_mcp__predict_protein_epitopes`, `mcp__netMHCIIpan_mcp__predict_protein_epitopes`

**This step is non-optional per `reference_vhh_max_success_skill.md`.**

**Why here:** MHC 扫描是治疗安全性硬门控，但仅需序列。L3 是整个 pipeline 最贵的计算步骤，fail-fast 在其之前最大化节省 GPU。

- Input: `{RESULTS_DIR}/val/filter/seq_sol_filtered_pool.csv`
- MHC-I allele panel: `HLA-A02:01,HLA-A24:02,HLA-B07:02,HLA-B35:01`（覆盖主要人群）
- MHC-II: scan full VHH sequence against common HLA-DRB1 panel

**过滤规则（区分 FR / CDR 区，以 ANARCI 分区结果为基准）：**

| 场景 | 操作 | 字段 |
|------|------|------|
| FR 区 Strong Binder (rank ≤0.5%)，**来自 central scaffold library 保守区** | **只 flag，不 hard drop**（scaffold 免疫原性已有临床验证，hard drop 逻辑倒置） | `mhc_fr_strong_binder_flag=True` |
| FR 区 Strong Binder (rank ≤0.5%)，**非 scaffold 来源的新引入 FR 序列** | **2026-05-12 改 hard drop → soft flag**：≥3 个 HLA-DR allele 同时命中 → 强 Pareto 降权 + 标注 `rescue_suggestion="humanize FR via point mutation at residue X"`（FR 序列可定向去免疫原性，hard drop 丢 head-on 候选成本过高） | `mhc_fr_strong_binder_flag=True` + `mhc_risk_score` ≥ 2.0 |
| CDR 区 Strong Binder (rank ≤0.5%) | **只 flag，不 hard drop**；CDR 肽段在复合物状态下被递呈概率极低 | `mhc_cdr_strong_binder_flag=True` |
| ≥3 allele 重复命中同一表位（CDR） | `mhc_multi_allele_flag=True`；强降权（`mhc_risk_score` 累加） | `mhc_multi_allele_flag=True` |
| ≥3 allele 重复命中同一表位（FR，非 scaffold 来源） | **2026-05-12 改 hard drop → soft flag**：`mhc_multi_allele_flag=True` + `mhc_risk_score` += 2.0 强惩罚，进 Pareto 自然降权 | `mhc_multi_allele_flag=True` |
| CDR Strong + 低 humanness + 低 solubility | 三项并发 → 强降权（`mhc_risk_score` 累加惩罚） | `mhc_risk_score` ↑ |

**新增字段（追加至 `seq_filtered_pool.csv`）：**
`mhc_fr_strong_binder_flag`（bool）、`mhc_cdr_strong_binder_flag`（bool）、`mhc_multi_allele_flag`（bool）、`mhc_risk_score`（float，0–3 累加惩罚；供 Step 4.4 Pareto `mhc_risk_score` 目标直接使用）

- **CLI fallback**: `python3.12 ~/biomodals/modal_netmhcpan.py --mode protein --input-fasta seq.fasta --allele "HLA-A02:01,HLA-A24:02,HLA-B07:02,HLA-B35:01"`
- Output: `{RESULTS_DIR}/val/filter/seq_filtered_pool.csv`（pipeline 最终序列过滤输出；2.diversity / 2.5 / 2.l3pool 均读此文件）
- Expected attrition: 0（2026-05-12 起全 soft flag；`mhc_risk_score` 连续值在 Step 4.4 Pareto 降权，FR multi-allele 累加 2.0 强惩罚自然挤出 front 1）

### Step 2.diversity — 4-path diversity diagnosis

**Tool:** `~/protein-design-utils/vhh/path_diversity_report.py`

**Goal:** 在进入 L3 之前，用三个指标诊断 4 条路径的多样性——如果某条路径高度冗余或严重缺失，提前预警而非浪费验证算力。

```bash
python ~/protein-design-utils/vhh/path_diversity_report.py \
  --pool {RESULTS_DIR}/val/filter/seq_filtered_pool.csv \
  --outdir {RESULTS_DIR}/val/diversity/
```

**三个诊断指标：**

| 指标 | 计算方式 | 健康值 |
|------|---------|--------|
| **CDR3 length distribution** | 各路径 CDR3 氨基酸长度分布直方图 | ≥3 个长度 bin 有候选 |
| **CDR3 pairwise Levenshtein distance** | 各路径内 / 跨路径平均距离 | 路径内 >2，跨路径 >3 |
| **Path contribution balance** | 各路径占 dedup 池的比例 | 任一路径占比 <5% 或 >60% 发出警告 |

**输出：**
- `{RESULTS_DIR}/val/diversity/diversity_report.md` — 三指标摘要 + 警告列表
- `{RESULTS_DIR}/val/diversity/path_stats.csv` — 数值明细

**决策规则（人工审阅）：**
- 某路径贡献 < 5% → 检查该路径是否运行失败或参数不当，不盲目删路径
- 某路径贡献 > 60% → 路径参数可能过于宽松（生成数量过多），考虑限额或采样
- CDR3 多样性低（平均 Levenshtein < 1.5）→ 回 L2 检查路径 A 的 scaffold 多样性或路径 C 的 IgGM 样本数

### Step 2.ibex — VHH 单体折叠质量预筛（Ibex，热点几何预筛之前）

**Tool:** `mcp__ibex_mcp__ibex_predict_batch` (批量模式)

**为什么在 Layer 2 末尾（而非 Layer 3）：** Layer 2.5 的热点几何预筛使用生成器初始结构计算接触坐标——如果 VHH 单体本身 fold 塌陷（CDR loop 畸形 / 整体 pLDDT 极低），这些坐标完全不可信；后续所有 GPU 计算（L2.5 + L3）都是基于错误结构的无效投入。Ibex 零额外 Modal 成本，提前砍掉失败单体是最高性价比的过滤。

- Input: VHH sequences as monomers（apo mode，无抗原）
  - Build CSV from `{RESULTS_DIR}/val/filter/seq_filtered_pool.csv`（列：`id,fv_heavy,fv_light`；VHH 的 fv_light 留空）：
    ```
    id,fv_heavy,fv_light
    cand_001,EVQLVES...,
    cand_002,EVQLVES...,
    ```
  - Pass as `csv_content` to `ibex_predict_batch`

**Hard drop（明确结构失败，不可能进入 L3）：**

| 条件 | 判定依据 |
|------|---------|
| Framework pLDDT 明显低（< 60）且 VHH β-sandwich 建模异常 | 框架骨架失败，坐标完全不可信 |
| Canonical disulfide 缺失或 Cα–Cα 几何异常（> 7Å） | VHH 折叠结构性缺陷 |
| CDR3 塌陷进 framework core（CDR3 Cα 质心与 FR2/FR3 Cα 质心距离 < 4Å） | 严重空间干涉，L3 不可能救回 |
| 严重内部 clash（单体内 Cβ–Cβ < 2.5Å 残基对 > 5） | 结构物理不合理 |

**Soft flag（追加字段到候选表，不删除）：**

| 条件 | 字段 |
|------|------|
| CDR3 pLDDT < 70 | `ibex_cdr3_low_plddt=True` |
| CDR3 RMSD vs germline > 4Å | `ibex_cdr3_high_rmsd=True`（de novo CDR3 构象多样性正常，不作淘汰依据） |
| CDR3 loop 较长（≥ 18 aa）且暴露 | `ibex_cdr3_long_exposed=True` |

- Output: `{RESULTS_DIR}/val/ibex_monomer/sanity_pass.csv`（hard drop 已移除；soft flag 字段随行）
- License caveat: Ibex (Genentech/Prescient Design) is **non-commercial only** per `reference_mcp_tools.md`. For internal R&D use only.
- Expected attrition: ~10–20%
- **Fallback:** if `ibex_predict_batch` unavailable → `ibex_predict` single-call loop，log fallback in `{RESULTS_DIR}/val/ibex_monomer/run.log`
- **下游读取：** Layer 2.5 `hotspot_prescreen.py` 改读 `sanity_pass.csv`（而非 `seq_filtered_pool.csv`）；Step 2.l3pool 亦同。

---

## Contact Definitions（全流程统一）

以下三级接触定义在所有 hotspot/contact 相关模块中统一使用，确保跨步骤可复现：

| 级别 | 定义 | 使用场景 |
|------|------|---------|
| **`loose_contact`** | VHH residue 与 antigen residue 的 Cβ–Cβ 距离 ≤ 8Å（Gly 用 Cα） | Layer 2.5 早期预筛（结构精度低，宽松判断） |
| **`hotspot_proximity`** | 任一 VHH CDR residue 到任一 antigen hotspot residue 的最小距离 ≤ 15Å | Layer 2.5 Track 分流（判断是否在 epitope 邻近） |
| **`residue_contact`** | 任一 VHH residue 与 antigen residue 的任一重原子距离 ≤ 4.5Å | Layer 3.B 精筛后 hotspot 重验证（高精度共折叠结构） |

> Layer 2.5 主要使用 `loose_contact` 和 `hotspot_proximity`；严格的 `residue_contact`、dSASA、per-residue hotspot 分析保留至 L3.B 后。

---

## Layer 2.5 — Geometric Hotspot Pre-screen

**Goal:** 对候选做轻量级几何分层（Track A / B / C），不以单次接触结果作为强淘汰依据。纯几何分析，零额外 Modal 计算。

**Tool:** `hotspot_prescreen.py`（`~/protein-design-utils/vhh/`）

```bash
python ~/protein-design-utils/vhh/hotspot_prescreen.py \
  {RESULTS_DIR}/gen/ \
  --hotspots inputs/hotspots.json \
  --antigen-chain {TARGET_CHAIN} \
  --threshold {L2P5_DISTANCE_THRESHOLD} \
  --min-contacts {L2P5_HOTSPOT_MIN_CONTACTS_TRACK_A} \
  --out {RESULTS_DIR}/val/filter/l2p5_prescreen.csv
```

**输出：**
- `{RESULTS_DIR}/val/filter/l2p5_prescreen.csv` — 所有候选的 hotspot 接触统计
- `{RESULTS_DIR}/val/filter/rejected/hotspot_miss/` — contacts < 阈值的候选（保留，不删除）

**Track B 前置步骤：contacts=0 候选独立 ipTM 复测（必须在双轨分流之前）**

生成器输出结构的 ipTM **不能**直接用于 Track B 入选判断——BoltzGen / Germinal / IgGM 的初始 ipTM 反映的是"生成器对自身输出的置信度"，contacts=0 的候选尤其容易出现 generator failure 伪装成高 ipTM（模型对错误结合 pose 过度自信）。必须用独立模型重新预测。

```bash
# 对所有 contacts == 0 候选做 Boltz-2 1-seed 快速复测
# Boltz-2 不参与 BoltzGen/Germinal/IgGM 的生成过程，是独立信号
python ~/protein-design-utils/vhh/repredict_track_b.py \
  --pool {RESULTS_DIR}/val/ibex_monomer/sanity_pass.csv \
  --prescreen {RESULTS_DIR}/val/filter/l2p5_prescreen.csv \
  --contacts-eq 0 \
  --model boltz2 --seeds 1 \
  --out {RESULTS_DIR}/val/track_b/b_independent_iptm.csv
```

- Path D（RFantibody）候选：RFantibody 骨架非 Boltz 家族生成，初始 ipTM 可信度相对较高；但为一致性，仍建议复测（成本很低，contacts=0 候选绝对数量少）
- 新工具：`repredict_track_b.py` 需添加到 `~/protein-design-utils/vhh/`
- 双轨分流**只读 `b_independent_iptm.csv` 的 `boltz2_iptm`**，不读原始生成器 ipTM

**三轨分流（gB-VHH N=200 校准 2026-04-15）：**

使用 `loose_contact`（Cβ–Cβ ≤ 8Å）和 `hotspot_proximity`（CDR–hotspot ≤ 15Å）作为分流指标（见 Contact Definitions）。

> **判定优先级：Track A → Track B → Track C**（条件互斥时从上到下首次匹配即停止）。Track B 需 contacts=0 **且** ipTM 高，优先于 Track C；避免 ipTM 低的候选因 hotspot_proximity 宽松条件误入 Track C rescue pool。

| 条件 | 去向 | 标注 |
|------|------|------|
| `loose_contacts >= 2` | → **Track A**：主 L3 验证池（on-target binder） | `track=A` |
| `loose_contacts == 0` 且 **`boltz2_independent_iptm` >= `L4_IPTM_MIN`** (≥0.9175) | → **Track B**：表位分析子流程（alt-epitope binder）；使用独立复测 ipTM | `track=B` |
| `loose_contacts == 0 或 1` 且 `hotspot_proximity <= 15Å` 且 无严重 clash | → **Track C**：存档 rescue pool，不进主 L3 | `track=C_low_priority` |
| 其余（contacts=0/1、hotspot_proximity > 15Å、严重 clash、表位不可及） | → 移入 `rejected/` | — |

**Track C 自动 rescue 规则：**

- 触发条件：Track A + B_keep 通过 L3.A 的绝对候选数 < 80（经验值：低于此数时 L3.B top 150 名额无法填满，多样性不足；基于 gB-VHH 实际通过率 ~15–20% 估算，500 候选入口约得 75–100 通过，< 80 表明生成质量偏差），且 Track C 候选数 > 20
- 操作：将 Track C 按 `hotspot_proximity` 升序取 top 20%，追加入 L3.A 输入池，标注 `rescue_from_track_c=True`
- Track C 候选存档路径：`{RESULTS_DIR}/val/rescue_pool/track_c.csv`

**Track B 表位分析子流程：**

**Tool:** `~/protein-design-utils/vhh/track_b_cluster.py`

```bash
python ~/protein-design-utils/vhh/track_b_cluster.py \
  --prescreen {RESULTS_DIR}/val/filter/l2p5_prescreen.csv \
  --candidates {RESULTS_DIR}/val/filter/seq_filtered_pool.csv \
  --antigen-chain {TARGET_CHAIN} \
  --hotspots inputs/hotspots.json \
  --outdir {RESULTS_DIR}/val/track_b/
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
| **> 15 Å** | `track=B_alt` | → CDR3 聚类后存入 `{RESULTS_DIR}/val/rescue_pool/alt_epitope_candidates.csv`（带簇标签），不进主 L3 |

**B_alt 聚类（与 B_keep 同步跑）：**

```bash
python ~/protein-design-utils/vhh/track_b_cluster.py \
  --candidates {RESULTS_DIR}/val/track_b/b_alt.csv \
  --outdir {RESULTS_DIR}/val/track_b/alt_clusters/
```

- 输出：`{RESULTS_DIR}/val/rescue_pool/alt_epitope_candidates.csv`（含 `cluster_id`、`cluster_repr` 列）、各簇代表序列 FASTA
- 每簇代表一个潜在的 alt-epitope 结合模式；同簇内保留 ipTM 最高者为代表
- 不进 L3，仅存档。若后续想探索 allosteric 靶点，以簇为单位取代表重走流程即可

**自动召回规则：**

- Track B_keep 候选数 ≥ 20 且 Track A 通过 L3 的绝对数 < 10 → 自动将 B_keep 合并入 L3 验证池

**迭代回路：** Track A pass rate < 5% → 回 L1.6 重选 hotspot，不调 L2 参数。

### Step 2.l3pool — L3 input pool 汇总（Track A + B_keep，negctrl 和 Ibex 的统一输入）

```bash
python -c "
import pandas as pd
prescreen = pd.read_csv('{RESULTS_DIR}/val/filter/l2p5_prescreen.csv')
pool = pd.read_csv('{RESULTS_DIR}/val/ibex_monomer/sanity_pass.csv')
track_ids = prescreen[prescreen['track'].isin(['A', 'B_keep'])]['cand_id']
l3_pool = pool[pool['cand_id'].isin(track_ids)]
l3_pool.to_csv('{RESULTS_DIR}/val/l3_input_pool.csv', index=False)
print(f'L3 input pool: {len(l3_pool)} candidates (Track A + B_keep)')
"
```

- 从 `l2p5_prescreen.csv` 取 `track=A` 和 `track=B_keep` 候选，join 回 `sanity_pass.csv` 取完整候选信息（ibex-passed；不用 `seq_filtered_pool.csv`：含已被 ibex 拒绝的候选，会污染后续步骤）
- Output: `{RESULTS_DIR}/val/l3_input_pool.csv`
- **后续 Step 2.negctrl 均读取此文件**（Ibex 已在 Step 2.ibex 完成；不读 `seq_filtered_pool.csv`：该文件包含 L2.5 已拒绝的候选，会污染 negctrl 基线校准）

### Step 2.negctrl — Dual null control calibration（2026-05-12 扩展为双 null）

**Goal:** 为每条路线建立两个**互补的** null 分布，对 ipTM/ipSAE 设路线特异性阈值。两个 null 检测不同失败模式：

| Null 类型 | 检测的失败模式 | 时机 |
|---|---|---|
| **A. Scramble CDR3 null**（原有）| Generator failure / 序列侥幸假阳 | L3.A 提交时同批跑 |
| **B. Unrelated antigen null**（**新增 S5**）| 缺乏靶点特异性 / "万能 sticky" VHH | L3.B 提交时同批跑（仅对 L3.A 幸存者）|

**判定矩阵**（候选必须**双 null 都过**才算 pass）：

| 过 scramble null | 过 unrelated null | 诊断 |
|:---:|:---:|---|
| ✅ | ✅ | True specific binder |
| ✅ | ❌ | **Sticky VHH**（贴任何蛋白）→ drop |
| ❌ | — | Generator failure / 序列侥幸 → drop |

**依据**：Greiff Champloo 2026（zenodo 18390239）cognate vs non-cognate 实测——内置 confidence metrics 不区分真假配对，必须靠显式阴性对照。两个 null 失败模式互补不重复。

---

#### Sub-step A — Scramble CDR3 null generation（原有，不变）

**方法：** 每条路线随机抽 5 个候选，对其 CDR3 区做 scramble（保留氨基酸组成，打乱顺序）→ 与真实候选同批送 L3 验证模型 → 各路线 scramble 分数 95 分位作为路线特异性阈值下限。

```bash
# Phase A：生成 scramble 序列（需添加到 ~/protein-design-utils/vhh/）
python ~/protein-design-utils/vhh/generate_neg_controls.py \
  --pool {RESULTS_DIR}/val/l3_input_pool.csv \
  --n-per-path 5 \
  --scramble-cdr3 \
  --out-fasta {RESULTS_DIR}/val/neg_control/neg_controls.fasta \
  --out-csv   {RESULTS_DIR}/val/neg_control/neg_controls.csv
```

- 输出：20 个 scramble 序列（4 路线 × 5 个），`source_path` + `is_neg_ctrl=True` 标注
- **在 L3.A 时与真实候选同批提交，且每条路径的 negctrl 必须使用与该路径 L3.A 相同的 scoring model：**
  - **Path A（BoltzGen）negctrl → Chai-1**（Path A 在 L3.A 使用 Chai-1，negctrl 阈值必须从 Chai-1 上跑）
  - **Path B / C / D negctrl → Boltz-2**（这三条路径在 L3.A 使用 Boltz-2 + Protenix；Boltz-2 是主排序模型）
  - **误对齐后果：** 如果 Path A negctrl 在 Boltz-2 上跑，会得到"Boltz-family 分数偏高但偏移量不一致"的阈值——path_thresholds.json 中 boltzgen 的 floor 会系统性失真
- 完成后执行 Phase B。不要放到 L3.B——negctrl 的作用是校准粗筛阈值，L3.A 是获取 per-path 基线分数的正确节点

---

#### Sub-step B — Scramble null Phase B（原有，不变）

```bash
# L3.A 完成后立即计算 scramble null 路线特异性阈值
python ~/protein-design-utils/vhh/calibrate_neg_control_thresholds.py \
  --scramble-scores {RESULTS_DIR}/val/neg_control/scramble_scores.csv \
  --out {RESULTS_DIR}/val/neg_control/path_thresholds.json
```

输出 `path_thresholds.json`（仅 scramble，Sub-step D 后会扩展）：
```json
{
  "boltzgen":   {"l3a_model": "chai1",  "scramble_floor_chai1": 0.61},
  "germinal":   {"l3a_model": "boltz2", "scramble_floor_boltz2": 0.55},
  "iggm":       {"l3a_model": "boltz2", "scramble_floor_boltz2": 0.49},
  "rfantibody": {"l3a_model": "boltz2", "scramble_floor_boltz2": 0.44}
}
```
- `l3a_model` 供 `l3a_filter.py` 读取，确定按哪个模型的 ipTM 做路径基线比对
- **L3.A gate** 中，候选 ipTM 须高于 `scramble_floor_<model>`
- 首次运行无实验数据：作**软过滤**（低于阈值标注 `scramble_neg_ctrl_flag=True`）；获得实验反馈后升为硬过滤

---

#### Sub-step C — Decoy panel preparation（**新增 S5**；一次性建库，所有项目复用）

**Goal**: 构造 3–10 个真实无关抗原的 panel，作为 unrelated antigen null 的输入。

```bash
# 仅在首次部署时跑一次，输出 {DECOY_PANEL_DIR}/{decoy_id}.pdb
python ~/protein-design-utils/vhh/build_decoy_panel.py \
  --target-size {真靶点大小} \
  --target-fasta {TARGET_FASTA} \
  --out-dir {DECOY_PANEL_DIR} \
  --n-decoy 10 \
  --exclude-sticky HSA,lysozyme,IgG_Fc
```

**Decoy panel 入选条件**（脚本自动校验）：
- 真实 PDB 结构（非预测）
- 与真靶点 BLAST E < 1e-3 排除同源
- 与真靶点无功能/通路重叠（人为筛 + KEGG/Reactome 自动 cross-check）
- 大小 ±50% 真靶点
- Fold class 多样：Ig-like / α-helical / β-barrel / αβ 至少 3 类
- 排除 sticky 蛋白：HSA、IgG Fc、HEWL lysozyme

**默认候选**（可作起步 panel）：
- Streptavidin (1MK5) — β-barrel
- GFP (1EMA) — β-barrel
- PKA kinase domain (1ATP) — αβ
- Random viral capsid 单体（无 Ab pocket）— mixed
- Carbonic anhydrase II (1CA2) — α/β

**输出**：`{DECOY_PANEL_DIR}/decoy_panel.csv`（列：`decoy_id, pdb_path, chain, size_aa, fold_class, blast_e_to_target`）

> ⚠️ **检查可复用性**：若 `DECOY_PANEL_DIR` 已有 panel.csv，脚本只校验同源性（新靶点 vs panel 必须 E ≥ 1e-3），同源命中则报错；不重新生成。

---

#### Sub-step D — Unrelated antigen null submission（**新增 S5**；L3.B 提交时同批）

**Goal**: 用 L3.A 幸存者（top ~150）× decoy panel 跑 ipSAE，得 unrelated null 分布。

```bash
# Phase A：生成提交清单（candidate × decoy 笛卡尔积）
python ~/protein-design-utils/vhh/submit_unrelated_null.py \
  --candidates {RESULTS_DIR}/val/l3a/l3a_pass.csv \
  --decoy-panel {DECOY_PANEL_DIR}/decoy_panel.csv \
  --n-decoy {DECOY_N_PANEL} \
  --seeds {DECOY_SEEDS_PER_CANDIDATE} \
  --model-by-path {RESULTS_DIR}/val/neg_control/path_thresholds.json \
  --out-jobs {RESULTS_DIR}/val/neg_control/unrelated_jobs/
```

**算力账**（lean mode 默认）：
- 输入：~150 候选 × 3 decoy × 1 seed × 2 model = **~900 预测**
- 占比：约 L3.B base（150 × 5 seed × 2 model = 1500）的 60%
- 总 L3.B 阶段额外开销 ~1.6×；full mode（5 decoy × 3 seed）为 ~4×

```bash
# Phase B：跑完后计算 unrelated null 阈值
python ~/protein-design-utils/vhh/calibrate_neg_control_thresholds.py \
  --scramble-scores {RESULTS_DIR}/val/neg_control/scramble_scores.csv \
  --unrelated-scores {RESULTS_DIR}/val/neg_control/unrelated_scores.csv \
  --percentile {UNRELATED_NULL_PERCENTILE} \
  --out {RESULTS_DIR}/val/neg_control/path_thresholds.json
```

**扩展后的 `path_thresholds.json` schema**：
```json
{
  "boltzgen": {
    "l3a_model": "chai1",
    "scramble_floor_chai1": 0.61,
    "l3b_models": ["chai1", "protenix"],
    "unrelated_floor_chai1": 0.45,
    "unrelated_floor_protenix": 0.47
  },
  "germinal": {
    "l3a_model": "boltz2",
    "scramble_floor_boltz2": 0.55,
    "l3b_models": ["chai1", "boltz2"],
    "unrelated_floor_chai1": 0.42,
    "unrelated_floor_boltz2": 0.40
  }
}
```

**L3.B gate（更新 Step 3.5）**：
- 候选每个 L3.B 模型 ipSAE_min（跨 seeds 主簇）必须**同时** > `scramble_floor` AND > `unrelated_floor`
- 任一未过 → flag（`scramble_fail_flag` 或 `unrelated_fail_flag`），按"判定矩阵"决定是否 drop
- 双 flag = sticky VHH 类型（区别于单一 scramble fail = 序列侥幸）

- 新工具占位：`build_decoy_panel.py`（Sub-step C）、`submit_unrelated_null.py`（Sub-step D Phase A）
- 扩展工具：`calibrate_neg_control_thresholds.py` 增加 `--unrelated-scores` 和 `--percentile` 参数

---

## Layer 3 — Structure Validation (Two-round: L3.A coarse → L3.B fine)

**两轮架构：** L3.A 用路径感知模型对全量候选做粗筛（→ top `L3A_COARSE_PASS_N` 150）；L3.B 用 2–4 模型对幸存者精筛（→ 15–25）。Absolute ipTM values are NOT compared — only rank agreement matters (per `domain_protein_design_gotchas.md` rule #2).

> **Ibex 单体预筛已在 Step 2.ibex（Layer 2 末尾）完成**，Layer 3 直接从结构共折叠开始，无单体预筛步骤。

### L3.B 模式选择（仅对 L3.A 幸存者；L3.A 使用路径感知模型，见下）

**背景（2026-05-12 重写）：** AF2m 已移出 L3 验证器（SNAC-DB Sanofi 2026 实测：AF2.3-multimer 在 NANOBODY-Ag 上 Rank-1 = 9.9%，与 OpenFold-3p2 并列最差；Protenix-v1 = 23.8%，最高）。**架构正交性救不了 VHH 任务上 AF2m 的实测垫底。** 当前所有 SOTA Nb-Ag 模型（Protenix / Boltz-2 / Chai-1）都是 AF3 家族——误差相关性必须通过 framework-level robustness 补偿（pose convergence + min-min + 3.5.1 unrelated antigen null + 3.5.2 跨模型 epitope Jaccard，参见 `reference_vhh_skill_pending.md` 3.5 节）。

**在此提醒用户选择：**
> 本次 L3 用 **2 个模型（默认）** 还是 **3 个模型（高把握）**？
>
> **2-model（默认）：** 见下表，按 Protenix v2 weights 可用性选：
>
> | 场景 | 推荐 2-model | 说明 |
> |---|---|---|
> | Protenix v2 上线后（首选）| **Protenix v2 + Boltz-2** | Nb-Ag 双优；Protenix 在糖基化界面最稳（35% vs 36%）|
> | 当前（Protenix v2 下架）| **Chai-1 + Boltz-2** ✅ | 默认 fallback；承认 AF3 家族误差相关，靠 3.5 框架补偿 |
>
> **3-model（高把握）：** 候选数 < 300 或第一个靶点无 baseline 时使用。运行 **Protenix + Boltz-2 + Chai-1**（全 AF3 家族，无 AF2m）。
>
> **共识阈值随模式调整：**
> - 2-model：需 **2/2** 通过（两个模型必须一致；双门控+加权排名 — 见 Step 3.5）
> - 3-model：需 **3/3** 通过（IgGM 路径放宽至 2/3）

**默认推荐：** 2-model = **Chai-1 + Boltz-2**（Protenix v2 权重当前下架）。

> ⚠️ **抗原多聚体状态：** 运行 L3 前检查 `inputs/target_oligomer_state.txt`。若靶点非单体（homodimer / trimer 等），所有结构预测**必须传入多聚体抗原**（例如 homodimer 传 chain A+A'）。设计阶段用单体是计算简化，验证必须还原生理结合环境——单体预测无法反映二聚体界面处的表位可及性变化。

> **可选：Multi-seed pose convergence 模式**（`L3_MULTI_SEED_MODE: true`，候选数 ≤ 300 时推荐，计算成本 5×）
> 每个候选跑 `L3_MULTI_SEED_COUNT`（默认 5）个 seed。额外判断：CDR3 Cα RMSD（aligned on antigen）< `L3_POSE_CONVERGENCE_RMSD`（默认 4Å）的 seed 数 ≥ `L3_POSE_CONVERGENCE_MIN_SEEDS`（默认 3）才算"收敛"。收敛性结果写入候选表 `pose_convergent` 列（bool）+ `convergent_seed_frac` 列（float）。在 `binding_quality_score`（Step 3.5b）中：启用本模式时，convergence 占 40%、ipSAE 占 60%（原始 60%/40%）。**单 seed ipTM 0.75 不如 5 seed 中 3 个 ipTM 0.55 但姿势一致。**

> ⚠️ **Path A（BoltzGen）专用规则：L3 中禁止使用 Boltz-2。**
> BoltzGen 内部的 `folding` 步骤已经用 Boltz-2（`boltz2_conf_final.ckpt`）对同一批序列做过一次结构预测。L3 再跑 Boltz-2 是同一模型对同一序列的重复预测，结果高度相关，不提供独立验证信号。
> - **2-model**（Path A 强制上限）：**Chai-1 + Protenix**（AF2m 已废除；Boltz-2 禁用；可用模型只剩 Chai-1 / Protenix）
>   - Protenix v2 下架期间：Path A 只能跑 **Chai-1 + Protenix v1**（接受 v1 性能损失）
> - **3-model 不适用 Path A**：可用复合物模型只有 2 个（Chai-1 + Protenix），无法凑齐 3 个独立模型；如果坚持 3-model，唯一办法是 Protenix v2 + Protenix v1 多 seed → 但两者训练数据高度重叠，不算独立信号。**结论：Path A 候选只走 2-model 模式。**

---

### L3.A — Coarse co-folding screen（路径感知模型，3 seeds）

**Goal:** 对 Step 2.ibex 通过后的全量候选（~500–800）做低成本粗筛，产出 top `L3A_COARSE_PASS_N`（默认 150）进入 L3.B 精筛。

**路径感知模型选择：**

| 路径 | L3.A 用模型 | 理由 |
|------|------------|------|
| **Path A（BoltzGen）** | **Chai-1** | BoltzGen 内部已用 Boltz-2 折叠，L3.A 再跑 Boltz-2 是重复信号；Chai-1 提供独立验证 |
| **Path B / C / D** | **Boltz-2 + Protenix** | 两模型正交性好，成本低；Chai-1 留给 L3.B 精筛 |

**提交（每个候选 `L3A_SEEDS=5` seeds，默认；算力受限 fallback 为 3 seeds）：**

> **Cost note（5 seeds）：** 500–800 候选 × 5 seeds ≈ 2500–4000 预测次数。Boltz-2 约 1–2 min/seed（H100），估计 40–80 GPU-hr；Chai-1 约 2–3 min/seed，估计 80–200 GPU-hr。3-seed fallback 将成本降低 40%，置信度分层中 `high` 标准随之降级（见下表）。

- **Chai-1**（Path A 专用）：`mcp__chai1_mcp__chai1_predict`，输出 `{RESULTS_DIR}/val/l3a/chai1/`
- **Boltz-2**（Path B/C/D）：`mcp__boltz2_mcp__boltz2_predict_structure`，输出 `{RESULTS_DIR}/val/l3a/boltz2/`
- **Protenix**（Path B/C/D）：`mcp__protenix_mcp__protenix_predict`，输出 `{RESULTS_DIR}/val/l3a/protenix/`

**L3.A 置信度分层（写入 `l3a_confidence` 列）：**

| 置信度 | 5-seeds 标准 | 3-seeds fallback 标准 | 后续处置 |
|--------|-------------|----------------------|---------|
| `high` | ≥ 3/5 seeds 收敛到相同 epitope | 2/3 seeds 收敛 | 优先进入 L3.B |
| `medium` | 2/5 seeds 收敛，或单模型支持但 pose 合理 | 1/3 seed 合理 | 进 L3.B diversity/rescue 通道 |
| `low` | 0–1/5 seeds 可信 | 0/3 合理 | 不进 L3.B（除非 Track C rescue 触发） |

**L3.A top 150 输出组成建议：**
- 70% `high` confidence candidates（按双模型平均 ipSAE rank 排序）
- 20% `medium` confidence 且 CDR3 多样性高（Levenshtein > 4 vs high 候选集）
- 10% 路径/表位多样性 rescue（保证 4 路径均有代表）

**L3.A 三项过滤标准（需同时满足）：**

| 指标 | 计算 | 阈值 |
|------|------|------|
| ipTM 路线基线 | 两模型 ipTM 均超 `path_thresholds.json` 对应 floor | Step 2.negctrl 输出 |
| Pose convergence | CDR3 Cα RMSD < 4Å（aligned on antigen）的 seed 数达到 per-track 阈值 | Track A：3/3 全部收敛（严格）；Track B_keep：2/3 收敛（宽松） |
| 无严重 clash | VHH–antigen 界面 Cβ–Cβ < 3.4Å 残基对数 ≤ `L3_CLASH_MAX_PAIRS`（默认 3） | ≤ 3 对 |

**Path A（BoltzGen）— 使用 Chai-1（Boltz-2 已在生成阶段内部使用，不可重复）：**
```bash
python ~/protein-design-utils/vhh/l3a_filter.py \
  --chai1-dir    {RESULTS_DIR}/val/l3a/chai1/ \
  --path-thresholds {RESULTS_DIR}/val/neg_control/path_thresholds.json \
  --convergence-rmsd {L3_POSE_CONVERGENCE_RMSD} \
  --convergence-min-by-track "A:3,B_keep:2" \
  --clash-max     {L3_CLASH_MAX_PAIRS} \
  --top-n         {L3A_COARSE_PASS_N} \
  --out {RESULTS_DIR}/val/l3a/l3a_pass.csv
```

**Path B / C / D — 使用 Boltz-2 + Protenix：**
```bash
python ~/protein-design-utils/vhh/l3a_filter.py \
  --boltz2-dir   {RESULTS_DIR}/val/l3a/boltz2/ \
  --protenix-dir {RESULTS_DIR}/val/l3a/protenix/ \
  --path-thresholds {RESULTS_DIR}/val/neg_control/path_thresholds.json \
  --convergence-rmsd {L3_POSE_CONVERGENCE_RMSD} \
  --convergence-min-by-track "A:3,B_keep:2" \
  --clash-max     {L3_CLASH_MAX_PAIRS} \
  --top-n         {L3A_COARSE_PASS_N} \
  --out {RESULTS_DIR}/val/l3a/l3a_pass.csv
```

**L3.A gate：** ~500–800 → top ~150（按两模型平均 ipSAE rank 排序截断；候选数不足 150 则全部通过）。

> 新工具：`l3a_filter.py` 需添加到 `~/protein-design-utils/vhh/`

---

### L3.B — Fine co-folding validation（对 L3.A top 150）

> 以下 Steps 3.1–3.7 即 L3.B 精筛，输入改为 `{RESULTS_DIR}/val/l3a/l3a_pass.csv`。

### Step 3.1 — Chai-1 prediction

**Tool:** `mcp__chai1_mcp__chai1_predict`

- Input: L3.A pass candidates (`{RESULTS_DIR}/val/l3a/l3a_pass.csv`)
- Output: `{RESULTS_DIR}/val/l3a/chai1/` with per-candidate ipTM, pLDDT, PAE

### Step 3.2 — Boltz-2 prediction

**Tool:** `mcp__boltz2_mcp__boltz2_predict_structure`

- **Path A（BoltzGen）候选跳过本步骤**（BoltzGen 内部已用 Boltz-2 做过折叠，重复预测无独立信号；见 L3 Path A 专用规则）。对 Path A 候选在提交前按 `source_path` 过滤掉即可。
- **⚠️ Path D（RFantibody）分数解读注意：** RFantibody backbone 在 Boltz-2 训练数据分布外（SAbDab 单链抗体结构），导致其 Boltz-2 绝对 ipTM **系统偏低**——这是分布偏移伪影，不代表候选结合质量差。处理方式：① Path D 候选以 `path_thresholds.json`（Step 2.negctrl）的路线特异性阈值过滤，不用全局 `L4_IPTM_MIN`；② 在 Step 3.5 排序中，Path D 候选优先参考 Chai-1 分数和 pose convergence（如启用），Boltz-2 分数仅作参考，**不与其他路线绝对值比较**。
- Output: `{RESULTS_DIR}/val/l3a/boltz2/`（仅含 Path B / C / D 候选）

### Step 3.3 — Protenix prediction

**Tool:** `mcp__protenix_mcp__protenix_predict`

- **Version note (2026-04-14):** `modal_protenix.py` 已升级为 v2 默认 + `use_tfg_guidance=True`（Ab-Ag DockQ +9–13 pp, v2 5 seeds 超过 v1 1000 seeds）。当前 v2 权重被 ByteDance 临时下架（GitHub Issues #294/#296），脚本会回落 v1。权重重新开放后无需改 skill，自动切换。详见 `project_vhh_tool_upgrades.md` 对话 A
- Output: `{RESULTS_DIR}/val/l3a/protenix/`

### ~~Step 3.4 — AlphaFold multimer prediction~~ **(DEPRECATED 2026-05-12)**

AF2m removed from L3 validation. See changelog (21) and L3.B 模式选择 background for rationale (SNAC-DB Nb-Ag Rank-1 = 9.9%, tied worst). Do **not** run `modal_alphafold.py` for L3 — its outputs are no longer consumed by any downstream step.

This step number is preserved (not renumbered) to avoid breaking references to Steps 3.5 / 3.5a / 3.5b / 3.5d / 3.6 / 3.7 throughout the skill.

### Step 3.5 — 5-seed cluster + min-min ipSAE_min + AntiConf representative (S3+S7 rewrite, 2026-05-12)

**Tool:** `~/protein-design-utils/vhh/consensus_rank.py`

**Pipeline (per candidate, per model — model assignment from `scripts/config.py:L3B_MODEL_BY_PATH`):**

| Step | Operation | Hard drop | Soft flag |
|------|-----------|-----------|-----------|
| ① | ipTM chain-pair < `L3B_IPTM_CHAIN_PAIR_HARD_DROP` (default 0.50) | seeds dropped; if remaining < 3 → flag `iptm_chainpair_fail_<model>` | — |
| ② | 5-seed CDR3 Cα 连通分量聚类 @ `L3B_CLUSTER_RMSD_ANGSTROM` (4Å) | — | main_cluster<3 → `pose_diverged_<model>` |
| ③ | Cluster-internal ipSAE_min | — | — |
| ④ | Cross-model ipSAE_min (min-min) + Overath F1 floor 0.50 | — | < floor → `ipsae_min_min_below_floor` |
| ⑤ | AntiConf (pTM × pDockQ2) → 簇内代表 pose 挑选 | — | < 0.40 → `anticonf_low_<model>` |
| ⑥ | Dual null gate (S5 from Step 2.negctrl, scramble + unrelated) | scramble_fail / unrelated_fail per judgement matrix | — |

```bash
python ~/protein-design-utils/vhh/consensus_rank.py \
  --candidates {RESULTS_DIR}/val/l3a/l3a_pass.csv \
  --l3b-root {RESULTS_DIR}/val/l3b/ \
  --vhh-chain B --antigen-chain {TARGET_CHAIN} \
  --out {RESULTS_DIR}/val/l3b/consensus_ranked.csv
```

**Output columns** (per model + `_primary` derived):
`cluster_size_<model>`, `cluster_size_frac_<model>`, `main_cluster_seed_ids_<model>`, `ipsae_min_within_<model>`, `anticonf_score_<model>`, `representative_seed_id_<model>`, `representative_cif_path_<model>`, plus `_primary` versions (consensus_rank.py derives per row from `L3B_MODEL_BY_PATH[path][0]`).
Cross-model: `ipsae_min_min`, `cross_model_incomplete`, `ipsae_min_min_below_floor`.
Flag aggregates: `pose_diverged_flag`, `anticonf_low_flag`.

**Output: `consensus_ranked.csv`** — feeds Step 3.5a/3.5b/3.5d via `--cif-path-col representative_cif_path_primary`.

### Step 3.5a — Hotspot re-verification on L3.B structures（零 GPU，epitope 特异性精确检查）

**Tool:** `~/protein-design-utils/vhh/hotspot_prescreen.py`

**Rationale:** L2.5 用的是生成时结构（BoltzGen/Germinal/IgGM 输出），精度参差不齐；L3 全流程中没有其他步骤验证结合位置（ipSAE / dSASA / clash 只检查"结合质量"，不检查"是否贴在正确的表位"）。此步骤在 L3.B 高质量共折叠结构上重跑 hotspot 接触检查，是 pipeline 中唯一的 epitope 特异性精确验证。

```bash
python ~/protein-design-utils/vhh/hotspot_prescreen.py \
  {RESULTS_DIR}/val/l3a/ \
  --candidates {RESULTS_DIR}/val/l3b/consensus_ranked.csv \
  --hotspots inputs/hotspots.json \
  --antigen-chain {TARGET_CHAIN} \
  --threshold 4.5 --mode residue_contact \
  --min-contacts {L2P5_HOTSPOT_MIN_CONTACTS_TRACK_A} \
  --out {RESULTS_DIR}/val/l3b/hotspot_recheck.csv
```

- Input: `consensus_ranked.csv`（L3.B 共折叠结构，Chai-1 / Boltz-2 / Protenix 级别精度）
- 零额外 GPU 成本：复用已完成的 L3.B 结构文件
- 此步骤使用 `residue_contact`（重原子距离 ≤ 4.5Å，见 Contact Definitions）进行精确验证

**L3.B hotspot 重验证判定规则：**

| 条件 | 操作 | 标注 |
|------|------|------|
| CDR 区有 ≥1 `residue_contact` 且接触中心在 epitope zone（hotspot 质心 ±10Å）内 | Pass | `l3b_hotspot_pass=True` |
| CDR 区有 ≥1 `residue_contact` 但接触中心在 epitope zone 外 ≤20Å | 保留，标注为 alternative epitope | `alternative_epitope_candidate=True` |
| 完全无 CDR-mediated contact（framework 主导）或接触中心 > 20Å outside epitope | Hard drop | — |
| 严重 clash / 链穿插 / glycan-shielded / membrane-buried 区域命中 | Hard drop | — |
| 多模型、多 seed 中 pose 完全不收敛（L3.A `l3a_confidence=low` 漏入者） | Hard drop | — |

> `alternative_epitope_candidate` 保留在 `l3b_hotspot_recheck.csv` 中，单独标注。这类候选可能结合邻近功能性表位，不应自动删除；进入后续 Pareto 时在 `epitope_consistency_score` 维度有惩罚，最终由人工审查决定是否合成。

- 新增列：`l3b_hotspot_contacts`（int）、`l3b_hotspot_pass`（bool）、`alternative_epitope_candidate`（bool）、`l3b_hotspot_jaccard`（float；= |接触残基 ∩ hotspot_set| / |接触残基 ∪ hotspot_set|；`alternative_epitope_candidate=True` 时值为 NaN）
- Output: `{RESULTS_DIR}/val/l3b/hotspot_recheck.csv`
- Expected attrition: < 5%（L2.5 已预筛大部分；此处主要捕获生成结构精度不足导致的漏网）

### Step 3.5b — CDR3 dSASA interface filter

**Tool:** `~/protein-design-utils/vhh/filter_dsasa.py` (BioPython Shrake-Rupley + cdr_boundaries; 零额外依赖)

- Goal: 剔除 CDR3 没真正参与界面的 candidate（结构看着像 binder，实际 CDR3 没贴上去）
- Input: 2-model / 3-model 共识通过的 candidate CIFs（建议用 Chai-1 或 Boltz-2 输出，预测质量稳定）
- Compute: `dSASA_ratio` = (CDR3 SASA in apo − CDR3 SASA in complex) / CDR3 SASA in apo
- **Threshold (initial):** `L3_DSASA_RATIO_MIN = 0.25` — **TBD，待 gB-VHH campaign 反向校准**
  - 参考：gB-VHH Task 6 实测范围 0.147–0.578；seed_44 普遍高于 seed_43
- Drop candidates with dSASA_ratio < threshold
- 注意 FR3 motif：longcdr3 scaffold 是 `DRFTISRDNAK`（非标准 `GRFTISRDNAK`），`cdr_boundaries.py` regex 已放宽为 `[A-Z]RF[TN]ISRDNAK`，对所有 VHH scaffold 通用
- Output: `{RESULTS_DIR}/val/l3b/dsasa_filter_results.csv` + `consensus_ranked_dsasa.csv`
- 详见 `feedback_dsasa_filter.md`

**CDR 主导界面判断（`cdr_dominance_score`，与 dSASA 同步计算）：**

```bash
# filter_dsasa.py 扩展 --all-cdrs 参数（需更新脚本）
python ~/protein-design-utils/vhh/filter_dsasa.py \
  --input {RESULTS_DIR}/val/l3b/hotspot_recheck.csv \
  --all-cdrs \
  --cdr-dominance-soft-flag {L3_CDR_DOMINANCE_SOFT_FLAG} \
  --cdr-dominance-hard-drop {L3_CDR_DOMINANCE_HARD_DROP} \
  --out {RESULTS_DIR}/val/l3b/dsasa_filter_results.csv
```

- `cdr_dominance_score` = Σ(CDR1 + CDR2 + CDR3 dSASA) / total_interface_dSASA
- **Soft flag：** `cdr_dominance_score` < `L3_CDR_DOMINANCE_SOFT_FLAG`（默认 0.50）→ 写入 `cdr_dominance_low_flag=True`，不删除；在 Pareto 中 `binding_composite` 自动降权
- **Hard drop：** `cdr_dominance_score` < `L3_CDR_DOMINANCE_HARD_DROP`（默认 0.25）→ FR 堆积极度主导，paratope 贡献可忽略，删除
- 写入 `consensus_ranked_dsasa.csv`，新增 `cdr_dominance_score`、`cdr_dominance_low_flag` 列

> **`binding_quality_score` 已废弃 (2026-05-12)** — 合并入 Step 4.4 `binding_composite` 5 分量公式，避免 L3/L4 双 source。

<!-- Step 3.5c (Boltz-2 affinity prediction) removed:
     Boltz-2 affinity 模块训练于通用 PPI 数据集，对 VHH-抗原界面（高度不对称，
     单域 ~15 kDa vs 抗原）无验证依据，预测值不可靠，不纳入排名。
     如需计算亲和力代理指标，用 Stability Oracle (Step 4.4) 的 ΔΔG 扫描或
     MBER (Step 5.1) 的亲和力成熟回路，均有更好的 VHH 适用性。 -->

### Step 3.5d — Interface clash check（精确版）

**Tool:** BioPython Cβ–Cβ distance scan，集成进 `filter_dsasa.py --mode clash`（零额外依赖）

```bash
python ~/protein-design-utils/vhh/filter_dsasa.py \
  --input {RESULTS_DIR}/val/l3b/dsasa_filter_results.csv \
  --mode clash \
  --clash-max {L3_CLASH_MAX_PAIRS} \
  --out {RESULTS_DIR}/val/l3b/consensus_ranked_dsasa.csv
```

- 计算 VHH–antigen 界面（5Å 范围内残基对）中 Cβ–Cβ < 3.4Å 的残基对数（Gly 用 Cα 代替）
- **Hard drop：** clash pairs > `L3_CLASH_MAX_PAIRS`（默认 3）
- L3.A 中已做粗 clash 预判；本步骤在 L3.B 复合物结构上精确计算，两者独立互补
- 结果写入 `consensus_ranked_dsasa.csv`，新增 `clash_pair_count` 列

---

### ~~Step 3.6 — AF2Rank structural re-identification~~ **(DEPRECATED 2026-05-12)**

AF2Rank requires AF2 outputs from Step 3.4. With AF2m removed, this step has no input. Its original role (VHH monomer fold self-consistency) is already covered by Step 2.ibex (Ibex monomer prediction with framework pLDDT, CDR3 collapse, disulfide geometry checks).

**保留下来的两个 pool 质量诊断**（不再依赖 AF2Rank，独立执行）：
- **Ibex 拒绝率**（Step 2.ibex 被删候选数 / 输入总数）> 30% → pool 整体 VHH 单体折叠质量差；考虑回 L2 调整生成参数。**用 Step 2.ibex run log 的拒绝计数**，不用过滤后的 pool pLDDT 分布。
- **ipSAE Spearman 秩相关**（Step 3.5 各模型间）< 0.4 → 界面信号不可靠；回查 L3 threshold 是否过松，并考虑启用 3-model 模式或 3.5.3 自适应 seed rescue（pending）。

这两个诊断可作为 L3 gate 后的人工 check，写入 `{RESULTS_DIR}/val/l3b/pool_quality_diagnostics.md`。

### Step 3.7 — IP / structural similarity annotation (foldseek)

> **保留原因：IP 风险标注，非质量过滤。** VHH 框架收敛到小结构库，结构相似（TM-score > 0.7）是正常现象而非质量问题；仅当 CDR3 序列高度相同时才有 IP 风险。结构相似的候选**不因本步骤被删除**。

**Tool:** `adaptyv:foldseek` skill

- Query each surviving candidate against PDB + SAbDab
- **Annotate, do NOT auto-drop**: add `top_hit_tm_score` and `top_hit_pdb_id` columns to the candidate table
  - TM-score > 0.9 to a known VHH + CDR3 sequence identity > 80% → flag `ip_risk=HIGH` (near-identical to deposited structure; requires IP review before filing)
  - TM-score > 0.7 (structural similarity only, CDR3 divergent) → flag `ip_risk=LOW` (convergent VHH fold is expected and acceptable; no action needed)
  - Otherwise → `ip_risk=NONE`
- **Rationale:** VHH framework folds converge to a small structural repertoire — TM-score > 0.7 against SAbDab is normal and does NOT indicate quality problems. Dropping on structural similarity alone would remove candidates with validated scaffold geometries. Only sequence-level CDR3 identity raises genuine IP concerns.
- **Hard drop** (only case): TM-score > 0.95 AND CDR3 identity > 90% to an existing therapeutic VHH in clinical trials (query via `WebSearch` on ClinicalTrials.gov if flagged) — this indicates near-copy of a clinical asset
- Output: `{RESULTS_DIR}/val/l3b/ip_annotated.csv`

### Layer 3 gate

Expected funnel（两轮架构）：
- Step 2.seqfilter 后：~600–950
- Step 2.solfilter 后：~510–810（protein-sol −15%）
- Step 2.mhcfilter 后：~470–780（FR multi-allele hard drop，CDR 改 flag；实际损耗降低）
- L2.5 hotspot prescreen 后：varies（Track A + B_keep 进主 L3；Track C 存档 rescue pool）
- Step 2.ibex（Ibex 单体预筛）后：减少 10–20%
- **L3.A gate**：→ top 150（路径感知：Path A 用 Chai-1，B/C/D 用 Boltz-2+Protenix）
- **L3.B gate**（Steps 3.1–3.5）：top 150 → ipSAE 共识筛选 + **dual null gate**（Step 2.negctrl Sub-step A+D 输出）
  - 双 null pass → `specific`（候选）
  - 仅 scramble pass / unrelated fail → `sticky` VHH → drop（~5–10% L3.A 幸存者）
  - 仅 unrelated pass / scramble fail → `sticky`（罕见但理论上可能，按 sticky drop）
  - 双 fail → `seq_luck` → drop
- **Step 3.5a hotspot 精确验证**：< 5% 额外 attrition（捕获 L2.5 漏网脱靶）
- **Steps 3.5b–3.7**：dSASA + clash + foldseek → ~30–60 enter Layer 4（Step 3.6 AF2Rank 已 deprecated）

**Iteration loop 1:** If < 10% of pool survives Layer 3 across all 4 paths uniformly → hotspots likely wrong or epitope occluded. Return to Step 1.6, reselect hotspots, rerun Layer 2. **Do NOT** debug individual candidates in this failure mode.

---

## Layer 4 — Developability Funnel (SERIAL — order matters)

**Strictly serial**, cheap-first. Each step reads the previous step's output. Intermediate CSVs persisted between steps (format TBD — decide on first run).

**Layer 4 step order (rationale):**
> 4.1 ANARCI 列传递（零算力，读 seqfilter 输出）→ **4.2 AbMPNN（需 L3 复合物 CIF，GPU）** → 4.3 Stability Oracle（序列级精细热稳定性）→ 4.4 Pareto 多目标优选
>
> protein-sol / MHC / 糖基化（CDR + FR delta）已在 Layer 2（Steps 2.seqfilter / 2.solfilter / 2.mhcfilter）完成，进入 L4 的候选已通过全部序列级过滤。L4 只保留必须依赖 L3 结构或需要精细池子的步骤：AbMPNN scoring 需要复合物 CIF，Stability Oracle 在 AbMPNN 缩小池后运行更高效。

### Step 4.1 — ANARCI results propagation（读取 Step 2.seqfilter 输出，不重跑）

> **ANARCI 已在 Step 2.seqfilter 中运行完毕。本步骤只做列传递，零额外 GPU / 计算成本。**

```bash
python ~/protein-design-utils/vhh/propagate_anarci.py \
  --seqfilter-output {RESULTS_DIR}/val/filter/seq_filtered_pool.csv \
  --l3b-survivors    {RESULTS_DIR}/val/l3b/ip_annotated.csv \
  --out {RESULTS_DIR}/l4_scored.csv
```

> **`l4_scored.csv` 是 Layer 4 的唯一工作文件。** Steps 4.1→4.3 各自追加列，不建新文件；Step 4.4 Pareto 读此文件输出最终结果。

- 传递列：`anarci_pass`、`v_gene`（最佳配 IGHV 名称）、`humanness_score`（= `v_identity`，FR 序列与人源胚系的相似度）
- VHH 典型范围：0.72–0.87 vs human IGHV3 family；FR humanness 是框架区免疫原性风险的正确代理（CDR 排除在外）
- L4.7 Pareto 的 `humanness_score` 维度直接用本步输出，无需重计算
- **无额外 attrition**（seqfilter 已过滤所有 ANARCI fail 候选）
- 新工具：`propagate_anarci.py` 需添加到 `~/protein-design-utils/vhh/`
- Output: `{RESULTS_DIR}/l4_scored.csv`（Layer 4 工作文件起点）

### Step 4.2 — AbMPNN sequence-structure consistency scoring

**Tool:** `mcp__ligandmpnn_mcp__ligandmpnn_design` (scoring mode, `calc_score=True`)

**Rationale:** ESM-2 PLL 对 CDR 区域无效——通用蛋白语言模型会因 CDR 高度可变而给低分，但这是 CDR 的正常特征，不是质量差。AbMPNN（SAbDab 抗体结构训练）能正确理解 CDR 变异空间，给出结构条件化的序列合理性评分。

- Input: each candidate's **PDB**（不接受 CIF；CIF 须先用 `Bio.PDB.PDBIO()` 转换）+ sequence (structure-conditioned scoring)
- **L3 复合物结构来源（按路径分）**，均在该结构上跑 `calc_score=True`：
  - **Path B / C / D 候选**：Boltz-2 预测结构 preferred（稳定性好），fallback Chai-1
  - **Path A（BoltzGen）候选**：禁止用 Boltz-2（BoltzGen 内部已用 Boltz-2 折叠，同模型重复无独立信号）→ 使用 **Chai-1** 预测结构
- **Path D 不复用 D2 分数**：D2 的 AbMPNN 是在 RFdiffusion 骨架（pre-L3，无抗原）上打的，度量"序列与骨架吻合度"；L4.3 需要的是"序列与复合物界面的吻合度"——两者不等价，不可替代
- Metric: length-normalized log-likelihood (`ll_fullseq` / sequence length)
- Drop bottom `L4_ABMPNN_LL_MIN_PERCENTILE` (default: below median)
- **追加 `abmpnn_ll` 列到 `l4_scored.csv`，删除不通过行后写回**
- Expected reduction: ~30–60 → ~20–40

**Note:** AbMPNN scoring is structure-conditioned — requires a CIF input per candidate. Ensure L3 outputs are available before running this step.

### Step 4.3a — Monomer stability analysis（单体稳定性，全局 ΔΔG 扫描）

**Tool:** `mcp__stability_oracle_mcp__stability_oracle_predict`

- Mode: per-candidate ΔΔG at mutation hotspots（不做 `--scan-all`，成本过高）
- **扫描范围（mutation hotspots 定义）：** CDR1 / CDR2 / CDR3 全部残基 + framework core 约 20 个保守位置（β-sheet core / hydrophobic core / canonical disulfide C22–C96 邻近 ±2 residue）；不扫 FR 暴露 loop 及 VHH 特有的 CDR3-FR2 疏水界面以外的 FR 残基
- 追加 residue 分区信息（来自 ANARCI Step 4.1）：将每个 ΔΔG residue 标注为 FR / CDR1 / CDR2 / CDR3

**位置感知判定规则：**

| 位置 | ΔΔG > `L4_STABILITY_DDG_MAX` (1.5 kcal/mol) | 处理 |
|------|---------------------------------------------|------|
| Framework core（β-sheet core / hydrophobic core / disulfide 邻近 ±2 residue） | **Hard drop**（框架失稳，无法挽回） | — |
| 暴露 CDR loop / 非核心 loop / 不参与结构稳定的位置 | **只 flag**，`ddg_cdr_high_flag=True`；不删除 | `ddg_cdr_high_flag=True` |

- **追加 `ddg_max_fr`（FR 最大 ΔΔG）和 `ddg_max_cdr`（CDR 最大 ΔΔG）到 `l4_scored.csv`**；删除 FR hard drop 行后写回
- Expected reduction: ~20–40 → ~17–36（CDR 高 ΔΔG 不再硬删，损耗减少）

### Step 4.3b — Interface hotspot analysis（界面 hotspot ΔΔG）

**Tool:** `mcp__stability_oracle_mcp__stability_oracle_predict` (同工具，对界面接触 residue 单独运行)

- Input: L3.B `residue_contact` 判定的界面接触 residue 列表（来自 Step 3.5a `l3b_hotspot_recheck.csv`）
- 只扫描参与 VHH–antigen 界面的 CDR residue（非全序列）
- 计算界面接触 residue 的 ΔΔG：高 ΔΔG（> 2.0 kcal/mol）在界面 hotspot 位置提示结合界面不稳定
- 追加 `ddg_interface_max` 列到 `l4_scored.csv`
- **不做 hard drop**：界面 hotspot ΔΔG 作为 Pareto `ddg_max` 目标的输入权重更新

- `l4_scored.csv` 至此包含全部 L4 过滤列，直接供 Step 4.4 Pareto 读入

### Step 4.4 — Multi-objective Pareto selection

**Tool:** `~/protein-design-utils/vhh/pareto_L4_ranker.py`

**Goal:** 避免单一加权分数掩盖真实 tradeoff。用 7 目标 Pareto 非支配分层保留 borderline 候选，并输出生成层反馈信号供下一轮 campaign 调整各路径配额。

**Hard pre-filter（直接删，不入 Pareto）：**

> 以下三项已在 Step 2.seqfilter 过滤，此处为**防御性双重确认**（防止中间步骤引入异常候选）。

- `anarci_pass == 0`（Step 2.seqfilter 已过滤；此处安全网）
- `cdr3_len` ∉ [8, 22]（Step 2.seqfilter 已过滤；此处安全网）
- `cdr3_cys_count` 为奇数（Step 2.seqfilter 已过滤；此处安全网）

**Pareto 前置过滤（未达最低阈值者不进 Pareto，节省 Pareto 维度）：**

```python
# pose_convergence_score：L3.A seed 中收敛 pose 的比例
# 定义：各 seed CDR3 Cα 质心两两距离 < 4Å 的 seed 对比例
df["pose_convergence_score"] = df["l3a_converged_seeds"] / df["l3a_total_seeds"]

# epitope_consistency_score：L3.B 接触残基集合与 hotspot 定义的 Jaccard 相似度
# epitope_consistency = |接触残基 ∩ hotspot| / |接触残基 ∪ hotspot|
df["epitope_consistency_score"] = df["l3b_hotspot_jaccard"]

# Pareto 前置过滤（未达阈值直接排在 Pareto 末尾，不删除；标注 pre_pareto_fail=True）
df["pre_pareto_fail"] = (
    (df["pose_convergence_score"] < 0.30) |  # 3/10 seed 以下收敛认为 pose 不稳定
    (df["epitope_consistency_score"] < 0.10)  # 几乎不与 hotspot 重叠（注意 alt_epitope 候选豁免此检查）
) & ~df["alternative_epitope_candidate"]
```

**binding_composite 预计算（Hard pre-filter 之后、Pareto 之前）：**

```python
# binding_composite (5 分量，权重来自 scripts/config.py:BINDING_COMPOSITE_WEIGHTS)
from scripts.config import BINDING_COMPOSITE_WEIGHTS as W, FLAG_DOWNWEIGHT_FACTORS as F

base = (
    W["ipsae_min"]           * rank_normalize(df["ipsae_min_min"]) +              # 0.40
    W["cluster_size_frac"]   * rank_normalize(df["cluster_size_frac_primary"]) +  # 0.20
    W["anticonf_score"]      * rank_normalize(df["anticonf_score_primary"]) +     # 0.15
    W["dsasa_ratio"]         * rank_normalize(df["dsasa_ratio"]) +                # 0.15
    W["cdr_dominance_score"] * rank_normalize(df["cdr_dominance_score"])          # 0.10
)
# 4 flag 乘性降权
mult = 1.0
for flag_col, factor in F.items():
    mult *= df[flag_col].apply(lambda x: factor if x else 1.0)
df["binding_composite"] = base * mult
```

**7 个 Pareto 目标（2026-05-12 新增 `seq_risk_count` 维度，配合 L2/L4 分工再校准）：**

| 来源列 | 方向 | 来源步骤 |
|--------|------|---------|
| `binding_composite` | max | 5 分量加权（ipSAE_min 0.40 + cluster_size 0.20 + AntiConf 0.15 + dSASA 0.15 + cdr_dominance 0.10）+ 4 flag 乘性降权；详见 scripts/config.py |
| `protein_sol` | max | Step 2.solfilter protein-sol score（hard drop 已移除 2026-05-12；连续值降权） |
| `ddG_max` | min | L4.3 Stability Oracle ΔΔG max |
| `mhc_risk_score` | min | Step 2.mhcfilter 累加风险分（0–5；全 soft flag 2026-05-12；FR multi-allele 累加 2.0 强惩罚） |
| `glycan_count` | min | Step 2.seqfilter `fr_glycan_new_count + cdr_glycan_count`（CDR/FR 总 sequon 数，2026-05-12 扩展含 CDR） |
| `seq_risk_count` | min | Step 2.seqfilter 可救 soft flag 累加：`pi_extreme_flag + net_charge_extreme_flag`（2026-05-12 新增维度；CDR glycan 单算 `glycan_count`） |
| `humanness_score` | max | L4.1（来自 Step 2.seqfilter ANARCI `v_identity`） |

```bash
python ~/protein-design-utils/vhh/pareto_L4_ranker.py \
  --input {RESULTS_DIR}/l4_scored.csv \
  --outdir {RESULTS_DIR}/final/ \
  --top-n-fronts {L4_PARETO_MAX_RANK}
```

**输出（均写入 `{RESULTS_DIR}/final/`）：**
- `pareto_results.csv` — 全部候选 + `pareto_rank` 列（-1 = hard filter 删除；rank 1–2 = 进入 Step 4.4b）
- `generation_feedback.json` — 各 L2 路径/scaffold 占比 + 下一轮配额 delta 建议

- 进入 Step 4.4b 组合选择的候选：`rank <= L4_PARETO_MAX_RANK`（默认 2，兜底确保不少于 5 个）
- Expected: ~15–28 → **5–15 candidates**（Pareto front 1–2，作为 4.4b 高分部分的核心）

**Step 4.4b — 组合策略选 `FINAL_CANDIDATE_TARGET` 个实验候选（24 / 48 / 96）：**

> 选择目标数前提醒用户：24 = 单次小规模表达验证；48 = 一块 48-well；96 = 一块板，适合高通量细胞展示或 ELISA 筛选。

```bash
python ~/protein-design-utils/vhh/build_final_candidates.py \
  --pareto {RESULTS_DIR}/final/pareto_results.csv \
  --pool   {RESULTS_DIR}/val/filter/seq_filtered_pool.csv \
  --target {FINAL_CANDIDATE_TARGET} \
  --top-scoring-frac  {FINAL_TOP_SCORING_FRAC} \
  --diversity-frac    {FINAL_DIVERSITY_FRAC} \
  --path-rep-frac     {FINAL_PATH_REP_FRAC} \
  --path-quota-per-10 "rfantibody:4,boltzgen:2,germinal:2,iggm:2" \
  --out {RESULTS_DIR}/final/top_candidates.csv
```

**三部分组合（以 FINAL_CANDIDATE_TARGET=48 为例）：**

**Portfolio 类别（6 类，比例均可通过配置参数调整）：**

| 类别 | 配置参数 | 48 总默认分配 | 来源与规则 |
|------|---------|------------|-----------|
| `structural_consensus` | `FINAL_TOP_SCORING_FRAC=0.50` | 24 | Pareto rank 1–2，高结构共识；按路线配额分配 |
| `cdr3_diversity` | `FINAL_DIVERSITY_FRAC=0.17` | 8 | 高分池外 CDR3 Levenshtein 最大化贪心采样 |
| `epitope_diversity` | `FINAL_EPITOPE_DIV_FRAC=0.12` | 6 | 按 `predicted_epitope_cluster` 聚类取代表，覆盖不同 epitope sub-site |
| `path_quota` | `FINAL_PATH_REP_FRAC=0.12` | 6 | 每条生成路径 Pareto 最高分代表（4 路径均须有代表） |
| `high_developability` | `FINAL_DEV_FRAC=0.04` | 2 | 结构分数中等但 protein-sol / humanness / mhc_risk_score 优秀 |
| `exploratory` | `FINAL_EXPLOR_FRAC=0.04` | 2 | 模型分歧大但 pose 有趣的候选（`l3a_confidence=medium` 且 `alternative_epitope_candidate`） |

**新增字段（写入 `{RESULTS_DIR}/final/top_candidates.csv`）：**
`selection_category`（上表六类之一）、`selection_reason`（选入理由简述）、`cdr3_cluster`（CDR3 聚类 ID）、`predicted_epitope_cluster`（epitope 聚类 ID）、`source_path_quota_flag`（bool）

- **配额缩放逻辑：** `PATH_QUOTA_PER_10` 定义每 10 个名额的路线比例（4:2:2:2），按 `FINAL_CANDIDATE_TARGET` 线性缩放（48 个 → 19:10:10:10，不足时顺延补位）
- **RFantibody 比例最高（40%）：** SAbDab fine-tuned backbone 成熟度最高，历史命中率最稳
- 多样性部分保证探索性——即使 Pareto 分数中等，CDR3 差异大的候选可能命中不同 epitope sub-site
- Output: `{RESULTS_DIR}/final/top_candidates.csv`（含 `selection_category` 列：`structural_consensus` / `cdr3_diversity` / `epitope_diversity` / `path_quota` / `high_developability` / `exploratory`）

> ⚠️ **验证深度不同，合成前需向实验员明确说明：**
> - `structural_consensus` + `path_quota`：经过完整 L3.A + L3.B + L4 漏斗验证，计算置信度最高
> - `cdr3_diversity`：仅经过 Step 2.seqfilter 序列过滤，**无结构预测验证**——属于"探索性"候选，覆盖计算筛选可能遗漏的序列空间；实验结果反馈后用于下一轮校准
> - `epitope_diversity` / `high_developability` / `exploratory`：经过 L3 + L4 漏斗，但入选理由侧重多样性/可开发性，结构共识度低于 structural_consensus

- 新工具：`build_final_candidates.py` 需添加到 `~/protein-design-utils/vhh/`，替换旧的 `enforce_path_quota.py`

### Layer 4 gate

Expected output: 5–15 Pareto-validated candidates → Step 4.4b 组合扩充（多样性 + 路线代表补足至 24/48/96）→ Layer 4.5 human review.

### Layer 4.5 — Human review checkpoint（合成前必须）

**Goal:** 在提交 MBER / 合成之前，人工审查结构质量和表位合理性，弥补自动化流程的系统性盲点。

**渲染结构图（复用 Step 6.1 Sub-step A 的工具，提前运行）：**

```bash
modal run modal_pdb2png.py \
  --input-dir {RESULTS_DIR}/final/ \
  --top-candidates {RESULTS_DIR}/final/top_candidates.csv \
  --output-dir {RESULTS_DIR}/final/review_pngs/ \
  --views "front,side,cdrs"
```

**逐候选审查清单（结果记录到 `{RESULTS_DIR}/final/review_notes.md`）：**

- [ ] VHH CDR loop 姿势合理（无穿透抗原、无环塌陷）
- [ ] CDR 主导界面（目视与 `cdr_dominance_score` 一致）
- [ ] 表位区域与预期一致（PyMOL 叠加 `inputs/hotspots.json` 热点）
- [ ] 界面无大空洞（目视）
- [ ] FR 侧无明显非特异性堆积接触
- [ ] 多聚体靶点（如有）：binding pose 不阻断生理配体或对称界面

**决策规则：**

| 结论 | 操作 |
|------|------|
| 结构问题明确 | 从候选列表删除，从 Pareto 下一 front 补位 |
| 有疑虑不确定 | 标注 `review_flag=uncertain`，降为 P3 合成优先级 |
| 无问题 | 标注 `review_flag=approved` |

```bash
python ~/protein-design-utils/vhh/apply_review_decisions.py \
  --candidates {RESULTS_DIR}/final/top_candidates.csv \
  --review-notes {RESULTS_DIR}/final/review_notes.md \
  --out {RESULTS_DIR}/final/reviewed_candidates.csv
```

- **Layer 5 及 Layer 6 报告使用 `reviewed_candidates.csv`**，非 `top_candidates.csv`
- 新工具：`apply_review_decisions.py` 需添加到 `~/protein-design-utils/vhh/`

---

## Layer 5 — Affinity Maturation（可选分支，实验验证后再做）

> ⚠️ **Layer 5 默认不在第一轮实验前执行。** 在获得实验 binding 数据之前做 computational maturation，优化的是计算 pose 而非真实结合——MBER 已有 AF2-top = Chai-1-bottom 的失败案例（`task09_1_summary.md`）。**推荐在第一轮实验有命中后，以实验 hit 为 parent 进行定向成熟。**
>
> 如果坚持在实验前做轻量优化，须遵守以下约束：
> - 只对 top 10–20 parent 做，每个 parent 最多 3–5 个 variant
> - 不重设计整个 CDR3
> - 不突变 framework core / canonical disulfide 邻近（±2 residue）
> - 不引入新的 glycosylation motif、unpaired Cys、高疏水 patch
> - MBER 后必须重走 L3.B + Layer 4 + 人工审查

### Step 5.1 — MBER affinity maturation

**Tool:** `modal run modal_mber.py`

- Input: top `L5_MBER_TOP_N` (default 20, clip to L4 output size if smaller) from Layer 4
- MBER runs ~91 iterations of logit optimization + semigreedy per candidate
- Output: affinity-matured sequences → `{RESULTS_DIR}/mature/mber/`
- **Cost note:** MBER is expensive (~30 min per candidate on H100). If L4 output > 30, prioritize by Layer 3 ipSAE rank consensus.

### Step 5.2 — MANDATORY L3 re-validation after MBER

跳过 L3.A（MBER 输出已是 top 候选），直接跑 L3.B 精筛（Steps 3.1–3.5）。

| 项目 | 规则 |
|------|------|
| 模型配置 | 同 L3.B：2-model（L3.B 选定组合）+ 5 seeds（与 L3.B 一致；MBER 变体数量少，算力可承受） |
| ANARCI / AbMPNN scoring | 直接承袭 L4 结果，不重跑 |
| ΔΔG | **必须重跑**（成熟序列与 L4 输入序列不同） |
| binding_composite | 用新 ipSAE 重算（0.50×ipTM + 0.30×CDR3 dSASA + 0.20×CDR 主导度） |
| 失败处理 | re-validation 不通过 → 回退 pre-MBER 版本（`task09_1_summary.md`：MBER AF2-top = Chai-1 bottom 踩坑） |

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
     SOTA campaigns (BindCraft/Germinal/IgGM) don't run MD; L3 consensus +
     L3.5b dSASA + L4.3 AbMPNN scoring + L4.4 Stability Oracle + L4.7 Pareto multi-objective
     selection already covers binding quality, thermodynamic stability, and developability.
     100ns × 15 candidates ≈ 100–200 A100-h; better spent on cell-free expression.
     If MD is needed for a specific mechanism/paper study, write a dedicated skill. -->

### Layer 5 gate

**Layer 5 是可选分支，两路出口：**

| 路径 | 触发条件 | 下游输入来源 |
|------|---------|------------|
| **跳过 Layer 5**（推荐首轮） | 无实验 hit 数据；默认路径 | Layer 4.5 `manual_review_final.csv` 直接进 Layer 6 |
| **运行 Layer 5** | 已有实验命中，需定向成熟 | Step 5.2 `mature/revalidated.csv` 进 Layer 6（revalidated 候选替换或追加原始 hit） |

Expected final output: 10–20 candidates for experimental testing.

---

## Layer 6 — Experimental Planning & Reporting

### Step 6.1 — Report generation

**Tools:** `modal run modal_pdb2png.py`, `~/protein-design-utils/vhh/generate_report.py`

**Sub-step A — Render structure images (optional but recommended):**
```bash
modal run modal_pdb2png.py \
  --input-dir {RESULTS_DIR}/mature/ \
  --output-dir {RESULTS_DIR}/final/pngs/ \
  --top-n 10
```

**Sub-step B — Generate report files:**
```bash
python ~/protein-design-utils/vhh/generate_report.py \
  --results-dir {RESULTS_DIR} \
  --campaign {JOB_NAME}
```

**Outputs:**
- `{RESULTS_DIR}/final/top_candidates.html` — Interactive two-tab report:
  - **汇报 Tab**: pipeline funnel bars + path contribution, Top candidate decision cards (P1/P2/P3 + 4-dimension signal lights), expandable parameter comparison table (click any dimension cell to reveal raw metrics)
  - **实验员 Tab**: minimal sequence table (full sequence + CDR1/2/3 + synthesis priority), suitable for direct handoff to synthesis team
- `{RESULTS_DIR}/final/top_candidates.md` — Static Markdown (Section 1: director summary + funnel; Section 2: lab sequence table with IMGT CDR annotations)

**4 parameter dimensions (expandable in HTML):**

| Dimension | Default display | Raw metrics (on expand) |
|-----------|----------------|------------------------|
| 结合质量 | ●●●●● (1-5 dots) | model consensus N/4, ipSAE rank %, dSASA ratio |
| 可开发性 | ●●●●○ (1-5 dots) | protein-sol, ΔΔG max, AbMPNN LL |
| 安全性 | ✓/⚠/✗ | MHC worst rank %, humanness %, CDR glycan count |
| 亲和力 | KD nM or Pareto rank | MBER KD, Pareto rank |

**Synthesis priority rules:**
- P1: Pareto rank 1 AND safety ✓
- P2: (Pareto rank 2 AND safety ≠ ✗) OR (Pareto rank 1 AND safety ⚠)
- P3: all other L4 survivors

**Note:** ESM2 suggestions (Step 5.4) are intentionally excluded from the report.
Unvalidated suggestions would confuse the synthesis team about which sequence to order.
If an ESM2 suggestion is adopted, it must re-enter L3/L4 validation as a new candidate.

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
python ~/protein-design-utils/vhh/calibrate_thresholds.py \
  --csv {RESULTS_DIR}/val/l3b/consensus_ranked_dsasa.csv \
  --out-dir ~/protein-design-utils/vhh/calibration_output/
```
（`calibrate_thresholds.py` 存放于 `~/protein-design-utils/vhh/`，计算 dSASA p25 + ipSAE cut 推荐值，输出写入 `--out-dir` 目录（自动创建），手动确认后更新 skill config）

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
- Trigger: MBER-matured candidate fails L3.B re-validation (2-model / 3-model consensus)
- Diagnosis: MBER overfit AF2 (known failure mode from HSV1 task09_1; remains relevant even after AF2m removed because MBER itself optimizes against AF2)
- Action: revert to pre-MBER candidate, do NOT tune MBER parameters

<!-- Loop 3 (MD fail) removed 2026-04-14 along with Step 5.5 (R2-5). -->

---

## Hard Constraints (non-negotiable)

1. **FR/CDR are jointly optimized** (`domain_protein_design_gotchas.md` #1): do not transplant CDRs across FRs. Use strict FR mode in Path D from the start.
2. **Cross-model ipTM is not comparable** (`domain_protein_design_gotchas.md` #2): Layer 3 consensus uses rank agreement, never absolute ipTM comparison across models.
3. **Immunogenicity scan is mandatory** (`reference_vhh_max_success_skill.md`): Step 4.5 cannot be skipped for therapeutic VHH.
4. **AbMPNN (not SolubleMPNN) for VHH** (`reference_vhh_max_success_skill.md`): Path D uses AbMPNN (`model_checkpoint: "abmpnn"`) — antibody-fine-tuned ProteinMPNN — with strict FR mode; protein-sol downstream filter in L4. Fallback to `proteinmpnn_v_48_020` if AbMPNN weights unavailable.
5. **MBER outputs MUST be re-validated** (Step 5.2): MBER's AF2-optimized outputs cannot bypass L3.B consensus (2-model default, 3-model high-confidence; AF2m deprecated since 2026-05-12).

---

## Troubleshooting

**Layer 2 generation failures:**
- BoltzGen CUDA version mismatch → see `feedback_biomodals.md` (PyTorch 2.11+cu126)
- Germinal volume missing → run `modal_setup_germinal_volume.py` first
- RFantibody DGL error → uses DGL 2.4.0+cu118 (no graphbolt fix needed; if DGL error appears, check CUDA 11.8 compatibility in Modal image)
- `modal_rfdiffusion.py` DGL graphbolt error (non-Path-D uses) → already patched in `modal_rfdiffusion.py`

**Layer 3 validation inconsistency:**
- 2/3 models give wildly different ranks → expected cross-model variance within AF3 family (all are AF3 reproductions, but training data differs). Use consensus, don't debug individual model scores.
- Protenix times out → Protenix is slowest; increase timeout or accept 2/3 consensus (3-model mode) / fall back to 2-model (Chai-1 + Boltz-2)

**Layer 4 funnel over-filtering:**
- <10 candidates reach Layer 5 → thresholds too strict, relax in order: protein-sol (Step 2.solfilter) first, then AbMPNN (Step 4.2), then pLDDT/ipTM (L3 gate)
- Never relax immunogenicity (4.5) or glycosylation (4.6)

**Layer 5 MBER all candidates fail re-validation:**
- MBER is overfitting AF2 → revert all to pre-MBER, skip MBER for this campaign, report Layer 4 survivors as final

---

## Candidate Lineage Tracking

**必须维护全流程追踪文件：** `{RESULTS_DIR}/tracking/candidate_lineage.csv`

每个候选无论通过或失败，均须记录状态（**不只保存 pass candidates**）。

| 字段 | 说明 |
|------|------|
| `candidate_id` | 全局唯一 ID（格式：`{path}_{scaffold}_{idx}`） |
| `source_path` | A/B/C/D |
| `parent_scaffold` | 生成时骨架名称 |
| `sequence` | 完整 VHH 序列 |
| `cdr1` / `cdr2` / `cdr3` | ANARCI 切分结果 |
| `cdr3_cluster` | CDR3 聚类 ID（Step 4.4b） |
| `predicted_epitope_cluster` | epitope 聚类 ID（Step 3.5a 接触中心） |
| `sequence_filter_status` | `pass` / `hard_drop` / `soft_flag` |
| `sequence_filter_flags` | 逗号分隔 flag 列表（如 `mhc_cdr_strong_binder,ibex_cdr3_high_rmsd`） |
| `monomer_qc_status` | `pass` / `hard_drop`（ibex Step 2.ibex） |
| `hotspot_track` | `A` / `B` / `B_keep` / `C_low_priority` / `rejected` |
| `l3a_status` | `high` / `medium` / `low` / `skipped` |
| `l3b_status` | `pass` / `fail` / `alternative_epitope_candidate` |
| `developability_status` | `pass` / `fr_ddg_drop` / `borderline` |
| `final_selection_status` | `selected` / `pareto_survivor` / `not_selected` |
| `final_selection_reason` | `structural_consensus` / `cdr3_diversity` / `epitope_diversity` / `path_quota` / `high_developability` / `exploratory` / `—` |

---

## Failure Reason Summary

**每次 campaign 结束后生成：** `{RESULTS_DIR}/tracking/failure_reason_summary.md`

按 generation route 统计各环节失败原因，用于下一轮 generation feedback（不只是当前筛选复盘）。

**统计字段（各路径分别计数）：**

| 失败原因 | 统计环节 |
|---------|---------|
| `invalid_anarci` | Step 2.seqfilter |
| `missing_canonical_cys` | Step 2.seqfilter |
| `unpaired_cys` | Step 2.seqfilter |
| `cdr_glycosylation` | Step 2.seqfilter |
| `low_solubility` | Step 2.solfilter |
| `fr_mhc_hard_drop` | Step 2.mhcfilter（仅非 scaffold 来源新引入 FR；scaffold 保守 FR → flag 不删） |
| `monomer_fold_failure` | Step 2.ibex（framework hard drop） |
| `cdr3_collapse` | Step 2.ibex（CDR3 塌陷） |
| `no_hotspot_proximity` | Layer 2.5（rejected） |
| `l3a_low_confidence` | L3.A |
| `null_sticky_vhh` | Step 3.5 dual null gate（unrelated null fail；S5 新增）|
| `null_seq_luck` | Step 3.5 dual null gate（scramble null fail）|
| `l3b_no_cdr_contact` | Step 3.5a |
| `severe_clash` | Step 3.5d |
| `fr_ddg_drop` | Step 4.3a |
| `pareto_not_selected` | Step 4.4b |

生成命令：
```bash
python ~/protein-design-utils/vhh/failure_summary.py \
  --lineage {RESULTS_DIR}/tracking/candidate_lineage.csv \
  --out {RESULTS_DIR}/tracking/failure_reason_summary.md
```

> `failure_summary.py` 需添加到 `~/protein-design-utils/vhh/`

---

## Hard Drop / Soft Flag 总表

### 早期 Hard Drop（序列级，只基于**不可救**的明确缺陷，2026-05-12 收窄）

| 条件 | 环节 | 不可救原因 |
|------|------|-----------|
| invalid ANARCI / 序列非法 | Step 2.seqfilter | 序列编号失败，生成器 artefact |
| missing canonical cysteine | Step 2.seqfilter | 双硫桥缺失，VHH 折叠崩溃 |
| unpaired cysteine | Step 2.seqfilter | 奇数 Cys 错配，结构不稳定 |
| CDR3 长度越界 [8,22] | Step 2.seqfilter | generator 失败，不可救 |
| Framework fold 失败（β-sandwich 破坏 / framework pLDDT < 60 / disulfide 几何异常） | Step 2.ibex | 单体折叠失败 |
| CDR3 塌陷进 framework core | Step 2.ibex | 几何不可救 |
| 严重内部 clash（单体 Cβ–Cβ < 2.5Å 残基对 > 5） | Step 2.ibex | 结构不可救 |
| hotspot_proximity > 15Å 且 loose_contacts = 0 | Layer 2.5 rejected | 几何已证伪 |

### 早期 Soft Flag（只 flag，不删除；可救项进 Pareto 自然降权）

| 条件 | 字段 | rescue 路径 |
|------|------|-------------|
| **CDR N-glycan motif**（2026-05-12 从 hard drop 改） | `cdr_glycan_count` + `rescue_suggestion` | N→Q 单点突变 |
| **极端 pI < 4.0 或 > 10.0**（2026-05-12 从 hard drop 改） | `pi_extreme_flag` + `pi_value` | surface charge engineering |
| **极端净电荷 < −8**（2026-05-12 从 hard drop 改） | `net_charge_extreme_flag` + `net_charge_value` | surface charge engineering |
| **低 protein-sol < 0.45**（2026-05-12 从 hard drop 改） | `low_solubility_flag` | 连续值进 Pareto `protein_sol` 维度 |
| **FR ≥3 allele MHC（非 scaffold）**（2026-05-12 从 hard drop 改） | `mhc_fr_strong_binder_flag` + `mhc_risk_score` += 2.0 | humanize FR via point mutation |
| CDR MHC strong binder | `mhc_cdr_strong_binder_flag` | 复合物状态下 epitope 不暴露 |
| FR glycosylation motif（非 CDR） | `fr_glycan_new_count` | 进 Pareto `glycan_count` |
| CDR3 pLDDT < 70 | `ibex_cdr3_low_plddt` | L3 验证看真实结构 |
| CDR3 RMSD > 4Å | `ibex_cdr3_high_rmsd` | 同上 |
| CDR3 较长且暴露 | `ibex_cdr3_long_exposed` | 同上 |
| loose_contacts = 0/1 但 hotspot_proximity ≤ 15Å | Track C | L3.A 进一步评估 |
| L3.A medium confidence | `l3a_confidence=medium` | L3.B 精筛 |

### 后期 Hard Drop（仅在充分验证信息后执行）

| 条件 | 环节 |
|------|------|
| 完全无 CDR-mediated contact（framework 主导）且 epitope 中心 > 20Å outside | Step 3.5a |
| `null_gate_status == sticky`（unrelated antigen null 失败，S5 新增） | Step 3.5 dual null gate |
| `null_gate_status == seq_luck`（scramble CDR3 null 失败） | Step 3.5 dual null gate |
| 严重 clash（complex Cβ–Cβ < 3.4Å 残基对 > 3） | Step 3.5d |
| glycan-shielded / membrane-buried / oligomer-blocked 区域命中 | Step 3.5a |
| 多模型、多 seed pose 完全不收敛（pose_convergence_score < 0.30） | Step 4.4 pre-filter |
| Framework core ΔΔG > 1.5 kcal/mol | Step 4.3a |

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
source ~/claude-project/ProteinMCP/.venv/bin/activate
pskill uninstall vhh_max_success_design
```
