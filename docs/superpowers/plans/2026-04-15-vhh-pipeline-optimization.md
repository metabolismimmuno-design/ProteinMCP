# VHH Pipeline Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 VHH 从头设计 pipeline 的 6 个已知缺陷：hotspot 验证窗口太靠后、Boltz-2 affinity 使用时机偏晚、MBER oracle 与 validator 不一致、IgGM 路径被通用阈值误杀、两个关键阈值缺乏 VHH 特异性校准。

**Architecture:** T1/T5 新建 Python 脚本到 `~/protein-design-utils/vhh/`；T2/T4 直接编辑 skill 源文件；T3 审查 `modal_mber.py` 后新建 `modal_boltz2_mber.py`；T6 用 T5 分析结果更新 skill 并重装。T1–T5 相互独立可按任意顺序执行，T6 依赖 T5 产出。

**Tech Stack:** Python 3.12, BioPython, pandas, matplotlib, scikit-learn, Modal, boltz2_mcp

**Spec:** `docs/superpowers/specs/2026-04-15-vhh-pipeline-optimization-design.md`

---

## Task 1: L2.5 几何 Hotspot 预筛脚本

**目标：** 在 L2 生成和 L3 四模型验证之间插入纯几何分析，过滤 hotspot_contacts=0 的脱靶候选，节省约 4 倍 L3 算力。

**Files:**
- Create: `~/protein-design-utils/vhh/hotspot_prescreen.py`
- Modify: `~/claude-project/ProteinMCP/workflow-skills/vhh_max_success_design.md`（插入 L2.5 步骤 + 新增 config 参数）

---

- [x] **Step 1.1: 读 `filter_dsasa.py` 的 VHH 链检测和 CDR 边界代码**

  ```bash
  cat ~/protein-design-utils/vhh/filter_dsasa.py | head -200
  cat ~/protein-design-utils/vhh/cdr_boundaries.py | head -100
  ```

  重点确认：
  - `_find_vhh_chain()` 的 `WG[QR]GT` motif 逻辑（第几行，什么签名）
  - `get_cdr_boundaries()` 的返回格式（dict of (start, end) 1-indexed）

- [x] **Step 1.2: 写 `hotspot_prescreen.py`**

  保存到 `~/protein-design-utils/vhh/hotspot_prescreen.py`：

  ```python
  #!/usr/bin/env python3
  """
  hotspot_prescreen.py — L2.5 几何 Hotspot 预筛
  ================================================
  对 L2 生成的复合物 CIF/PDB 做纯几何分析，计算 CDR 残基与
  抗原 hotspot 残基的最近原子距离，过滤完全脱靶候选。
  
  无需额外结构预测，零 Modal 算力。
  
  用法：
    python hotspot_prescreen.py <gen_dir> \\
      --hotspots inputs/hotspots.json \\
      --antigen-chain A \\
      --threshold 8.0 \\
      --out results/l2p5_prescreen.csv
  
  输出 CSV 列：
    name, path, hotspot_contacts, contacted_hotspots,
    cdr1_contacts, cdr2_contacts, cdr3_contacts, cdr3_len, vhh_seq
  """
  from __future__ import annotations
  
  import csv
  import json
  import re
  import sys
  import warnings
  import argparse
  from pathlib import Path
  
  try:
      from Bio.PDB import MMCIFParser, PDBParser
      _BIOPYTHON_OK = True
  except ImportError:
      _BIOPYTHON_OK = False
  
  from cdr_boundaries import get_cdr_boundaries
  
  _THREE_TO_ONE = {
      "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
      "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
      "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
      "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
  }
  
  
  def _find_vhh_chain(structure) -> str | None:
      """找含 WG[QR]GT FR4 motif 的链（VHH 标志）。"""
      model = next(structure.get_models())
      for chain in model.get_chains():
          seq = "".join(
              _THREE_TO_ONE.get(r.get_resname(), "X")
              for r in chain.get_residues()
              if r.id[0] == " "
          )
          if re.search(r"WG[QR]GT", seq):
              return chain.id
      return None
  
  
  def _chain_sequence(chain) -> str:
      """提取链的单字母序列（仅标准残基）。"""
      return "".join(
          _THREE_TO_ONE.get(r.get_resname(), "X")
          for r in chain.get_residues()
          if r.id[0] == " "
      )
  
  
  def _get_atoms(chain, residue_indices: list[int]) -> list:
      """
      获取链中指定 1-indexed 位置残基的全重原子列表。
      residue_indices: 1-indexed 顺序编号（按残基在链中的出现顺序）
      """
      residues = [r for r in chain.get_residues() if r.id[0] == " "]
      atoms = []
      for idx in residue_indices:
          if 1 <= idx <= len(residues):
              atoms.extend(
                  a for a in residues[idx - 1].get_atoms()
                  if a.element != "H"
              )
      return atoms
  
  
  def _min_distance(atoms_a: list, atoms_b: list) -> float:
      """计算两组原子之间的最近原子距离（Å）。"""
      if not atoms_a or not atoms_b:
          return float("inf")
      min_d = float("inf")
      for a in atoms_a:
          for b in atoms_b:
              d = a - b  # BioPython 原子减法返回欧式距离
              if d < min_d:
                  min_d = d
      return min_d
  
  
  def analyze_structure(
      struct_path: Path,
      hotspot_residues: list[int],
      antigen_chain_id: str,
      distance_threshold: float = 8.0,
  ) -> dict | None:
      """
      分析单个复合物结构文件，返回 hotspot 接触统计。
  
      Args:
          struct_path: CIF 或 PDB 文件路径
          hotspot_residues: 抗原链中 hotspot 残基的 1-indexed 顺序编号
          antigen_chain_id: 抗原链 ID（如 "A"）
          distance_threshold: 接触判定距离阈值（Å）
  
      Returns:
          dict 或 None（解析失败时）
      """
      if not _BIOPYTHON_OK:
          raise RuntimeError("BioPython 未安装：pip install biopython")
  
      suffix = struct_path.suffix.lower()
      with warnings.catch_warnings():
          warnings.simplefilter("ignore")
          if suffix == ".cif":
              parser = MMCIFParser(QUIET=True)
          else:
              parser = PDBParser(QUIET=True)
          try:
              structure = parser.get_structure(struct_path.stem, str(struct_path))
          except Exception as e:
              print(f"  [WARN] 解析失败 {struct_path.name}: {e}", file=sys.stderr)
              return None
  
      vhh_chain_id = _find_vhh_chain(structure)
      if vhh_chain_id is None:
          print(f"  [WARN] 未找到 VHH 链（WG[QR]GT motif）: {struct_path.name}", file=sys.stderr)
          return None
  
      model = next(structure.get_models())
      vhh_chain = model[vhh_chain_id]
      vhh_seq = _chain_sequence(vhh_chain)
  
      # CDR 边界（1-indexed）
      try:
          bounds = get_cdr_boundaries(vhh_seq)
      except Exception as e:
          print(f"  [WARN] CDR 边界检测失败 {struct_path.name}: {e}", file=sys.stderr)
          return None
  
      cdr_indices: dict[str, list[int]] = {}
      for region in ("cdr1", "cdr2", "cdr3"):
          s, e = bounds[region]
          cdr_indices[region] = list(range(s, e + 1))
  
      # 抗原链
      if antigen_chain_id not in model:
          print(f"  [WARN] 抗原链 {antigen_chain_id!r} 不存在: {struct_path.name}", file=sys.stderr)
          return None
      antigen_chain = model[antigen_chain_id]
  
      # 抗原 hotspot 原子
      hotspot_atoms = _get_atoms(antigen_chain, hotspot_residues)
  
      # 计算每个 hotspot 残基是否与任一 CDR 残基接触
      antigen_residues = [r for r in antigen_chain.get_residues() if r.id[0] == " "]
      contacted: set[int] = set()
      cdr_contact_counts: dict[str, int] = {"cdr1": 0, "cdr2": 0, "cdr3": 0}
  
      for hs_idx in hotspot_residues:
          if hs_idx < 1 or hs_idx > len(antigen_residues):
              continue
          hs_atoms = [
              a for a in antigen_residues[hs_idx - 1].get_atoms()
              if a.element != "H"
          ]
          for region, indices in cdr_indices.items():
              cdr_atoms = _get_atoms(vhh_chain, indices)
              d = _min_distance(cdr_atoms, hs_atoms)
              if d <= distance_threshold:
                  contacted.add(hs_idx)
                  cdr_contact_counts[region] += 1
                  break  # 该 hotspot 已计数，不重复
  
      return {
          "name": struct_path.stem,
          "path": str(struct_path),
          "hotspot_contacts": len(contacted),
          "contacted_hotspots": ",".join(str(h) for h in sorted(contacted)),
          "cdr1_contacts": cdr_contact_counts["cdr1"],
          "cdr2_contacts": cdr_contact_counts["cdr2"],
          "cdr3_contacts": cdr_contact_counts["cdr3"],
          "cdr3_len": len(cdr_indices["cdr3"]),
          "vhh_seq": vhh_seq,
      }
  
  
  def run_prescreen(
      gen_dir: Path,
      hotspots_json: Path,
      antigen_chain: str,
      threshold: float,
      min_contacts: int,
      out_csv: Path,
      pattern: str = "*.cif",
  ) -> tuple[int, int]:
      """
      扫描目录下所有结构文件，输出预筛结果 CSV。
  
      Returns:
          (total, passed) 总数和通过数
      """
      # 读取 hotspot 列表
      with open(hotspots_json) as f:
          data = json.load(f)
      # 支持两种格式：{"hotspots": [92, 95, ...]} 或直接 [92, 95, ...]
      hotspot_residues = data.get("hotspots", data) if isinstance(data, dict) else data
  
      # 收集所有结构文件
      struct_files = sorted(gen_dir.rglob(pattern))
      if not struct_files and pattern == "*.cif":
          struct_files = sorted(gen_dir.rglob("*.pdb"))
  
      if not struct_files:
          print(f"[ERROR] 在 {gen_dir} 中未找到 {pattern} 文件", file=sys.stderr)
          return 0, 0
  
      print(f"扫描 {len(struct_files)} 个结构文件 (阈值={threshold}Å, min_contacts={min_contacts})...")
  
      rows = []
      passed = 0
      for f in struct_files:
          result = analyze_structure(f, hotspot_residues, antigen_chain, threshold)
          if result is None:
              continue
          rows.append(result)
          if result["hotspot_contacts"] >= min_contacts:
              passed += 1
  
      # 写 CSV
      out_csv.parent.mkdir(parents=True, exist_ok=True)
      fieldnames = [
          "name", "path", "hotspot_contacts", "contacted_hotspots",
          "cdr1_contacts", "cdr2_contacts", "cdr3_contacts", "cdr3_len", "vhh_seq",
      ]
      with open(out_csv, "w", newline="") as f:
          writer = csv.DictWriter(f, fieldnames=fieldnames)
          writer.writeheader()
          writer.writerows(sorted(rows, key=lambda r: -r["hotspot_contacts"]))
  
      print(f"结果写入: {out_csv}")
      print(f"通过 (contacts>={min_contacts}): {passed}/{len(rows)}")
      return len(rows), passed
  
  
  def main():
      parser = argparse.ArgumentParser(description="L2.5 几何 Hotspot 预筛")
      parser.add_argument("gen_dir", type=Path, help="L2 生成输出目录")
      parser.add_argument("--hotspots", type=Path, required=True,
                          help="hotspots.json 路径（含 hotspot 残基 1-indexed 编号）")
      parser.add_argument("--antigen-chain", default="A", help="抗原链 ID（默认 A）")
      parser.add_argument("--threshold", type=float, default=8.0,
                          help="接触判定距离阈值 Å（默认 8.0）")
      parser.add_argument("--min-contacts", type=int, default=1,
                          help="最少接触 hotspot 数（默认 1）")
      parser.add_argument("--out", type=Path, default=Path("l2p5_prescreen.csv"),
                          help="输出 CSV 路径")
      parser.add_argument("--pattern", default="*.cif",
                          help="文件匹配模式（默认 *.cif）")
      args = parser.parse_args()
  
      total, passed = run_prescreen(
          args.gen_dir, args.hotspots, args.antigen_chain,
          args.threshold, args.min_contacts, args.out, args.pattern,
      )
      # 退出码：0=有通过, 1=全部脱靶（便于 shell 脚本检测）
      sys.exit(0 if passed > 0 else 1)
  
  
  if __name__ == "__main__":
      main()
  ```

- [x] **Step 1.3: 用 gB-VHH 历史数据验证脚本**

  ```bash
  cd ~/protein-design-utils/vhh
  python hotspot_prescreen.py \
    /Users/guoxingchen/claude-project/ab-design-projects/gB-VHH/out/validation_boltz2/boltz_results \
    --hotspots /Users/guoxingchen/claude-project/ab-design-projects/gB-VHH/inputs/hotspots.json \
    --antigen-chain A \
    --threshold 8.0 \
    --min-contacts 1 \
    --out /tmp/test_prescreen.csv
  ```

  预期：脚本运行无报错，输出 CSV，`hotspot_contacts` 列分布与 `top_candidates_v2.csv` 的 `b2_hotspot` 列大致吻合（多数=0）。

  如果 `inputs/hotspots.json` 不存在，先检查：
  ```bash
  ls /Users/guoxingchen/claude-project/ab-design-projects/gB-VHH/inputs/
  ```
  若无 hotspots.json，从项目 memory 创建（hotspot 残基：`[92, 95, 96, 97, 99]`，1-indexed，对应 gB DIV 链内顺序编号）：
  ```bash
  echo '{"hotspots": [92, 95, 96, 97, 99]}' > \
    /Users/guoxingchen/claude-project/ab-design-projects/gB-VHH/inputs/hotspots.json
  ```

- [x] **Step 1.4: 更新 `vhh_max_success_design.md` — 新增 L2P5 config 参数**

  在 `~/claude-project/ProteinMCP/workflow-skills/vhh_max_success_design.md` 的 `# === Layer 3 validation ===` 区块**之前**插入：

  ```yaml
  # === Layer 2.5 hotspot pre-screen ===
  L2P5_HOTSPOT_MIN_CONTACTS: 1          # 最少接触 hotspot 数（contacts=0 → rejected）
  L2P5_DISTANCE_THRESHOLD: 8.0          # 接触判定距离阈值（Å）
  ```

- [x] **Step 1.5: 更新 `vhh_max_success_design.md` — 插入 L2.5 步骤**

  在 `## Layer 2 — Multi-Path Parallel Generation` 与 `## Layer 3` 之间插入新章节：

  ```markdown
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

  **过滤动作：**
  - `hotspot_contacts >= L2P5_HOTSPOT_MIN_CONTACTS` → 进入 L3 验证池
  - `hotspot_contacts < L2P5_HOTSPOT_MIN_CONTACTS` → 移入 `rejected/hotspot_miss/`
  
  **迭代回路：** L2.5 pass rate < 5% → 回 L1.6 重选 hotspot，不调 L2 参数。
  ```

- [x] **Step 1.6: 重装 skill**

  ```bash
  cd ~/claude-project/ProteinMCP && .venv/bin/pskill install vhh_max_success_design
  ```

  预期：输出 `✓ vhh_max_success_design installed`，无报错。

- [x] **Step 1.7: Commit**

  ```bash
  cd ~/protein-design-utils
  git add vhh/hotspot_prescreen.py
  git commit -m "feat(vhh): add L2.5 geometric hotspot pre-screen script

  Filters VHH-antigen complexes by CDR-hotspot contact count before
  expensive 4-model L3 validation. Zero Modal compute, BioPython only.
  Reuses WG[QR]GT VHH chain detection and CDR boundary logic."

  cd ~/claude-project/ProteinMCP
  git add workflow-skills/vhh_max_success_design.md
  git commit -m "feat(skill): insert L2.5 hotspot pre-screen into vhh_max_success_design"
  ```

---

## Task 2: Boltz-2 Affinity 移到 L3.5c

**目标：** 将 Boltz-2 affinity 预测从 L5 提前至 L3.5，与 ipSAE/dSASA 并行，早期剔除低亲和力候选。

**Files:**
- Modify: `~/claude-project/ProteinMCP/workflow-skills/vhh_max_success_design.md`（L3.5 区块 + L5 删除重复调用）

---

- [x] **Step 2.1: 定位 skill 中 L3.5 和 L5 的 Boltz-2 相关内容**

  ```bash
  grep -n "L3.5\|boltz2_mcp\|affinity\|L5" \
    ~/claude-project/ProteinMCP/workflow-skills/vhh_max_success_design.md | head -30
  ```

  记录：L3.5 节在第几行，L5 中 boltz2 affinity 调用在第几行。

- [x] **Step 2.2: 在 L3.5 区块末尾新增 L3.5c 子节**

  找到 L3.5b（dSASA filter）所在位置，在其后插入：

  ```markdown
  ### Step 3.5c — Boltz-2 Affinity Prediction (parallel with 3.5a/b)

  **Tool:** `mcp__boltz2_mcp__boltz2_predict_affinity`

  - Input: top candidates from L3.2 ipSAE intersection（与 L3.5a/b 同一批）
  - Run in parallel with L3.5a and L3.5b
  - Output: `predicted_ddg` column（kcal/mol，负值 = 更强结合）
  - 加入 composite score：`affinity_rank`（rank-based，不用绝对值）

  **Composite score 权重（首次 campaign 后校准）：**
  - ipSAE rank (L3.5a): 权重 0.4
  - dSASA ratio (L3.5b): 权重 0.3
  - Boltz-2 affinity rank (L3.5c): 权重 0.3

  **注意：** `predicted_ddg` 绝对值不可跨项目比较；仅作为当前 campaign 内部排名依据。
  ```

- [x] **Step 2.3: 删除 L5 中的重复 Boltz-2 affinity 调用**

  找到 L5 中的 boltz2 affinity 步骤，将其删除（或注释为 `<!-- removed: moved to L3.5c -->`）。保留 L5 中 MBER 后的 L3 四模型重验证步骤（不动）。

- [x] **Step 2.4: 重装 skill**

  ```bash
  cd ~/claude-project/ProteinMCP && .venv/bin/pskill install vhh_max_success_design
  ```

- [x] **Step 2.5: Commit**

  ```bash
  cd ~/claude-project/ProteinMCP
  git add workflow-skills/vhh_max_success_design.md
  git commit -m "feat(skill): move Boltz-2 affinity prediction from L5 to L3.5c

  Earlier affinity screening reduces candidates entering MBER.
  Removes duplicate boltz2 call in L5."
  ```

---

## Task 3: MBER Oracle 替换为 Boltz-2

**目标：** 将 MBER 进化优化回路的评分 oracle 从 AF2-Multimer 换成 Boltz-2，消除 optimize/validate 信号错位。

**Files:**
- Read: `~/biomodals/modal_mber.py`（审查 oracle 耦合程度）
- Create: `~/biomodals/modal_boltz2_mber.py`（新脚本）
- Modify: `~/claude-project/ProteinMCP/workflow-skills/vhh_max_success_design.md`（L5 调用改为新脚本）

---

- [x] **Step 3.1: 审查 `modal_mber.py` 的 EvaluationModule 结构**

  ```bash
  grep -n "EvaluationConfig\|EvaluationModule\|af_params\|alphafold\|score\|iptm" \
    ~/biomodals/modal_mber.py | head -30
  ```

  重点确认：
  1. `EvaluationConfig` 是否有 oracle 参数（如 `model_type` 字段）
  2. AF2 params 路径是硬编码（`/germinal-models/alphafold_params`）还是可配置
  3. MBER 输出哪些列（ipTM? iptm_af2? esm_score?）

- [x] **Step 3.2: 确认结论并选择实现路径**

  根据 Step 3.1 的结果，确认走哪条路：
  - `EvaluationConfig` 有 `model_type` 参数 → 直接加 `--oracle boltz2` 参数到 `modal_mber.py`
  - AF2 硬编码但模块化 → 在 `modal_mber.py` 中加 `--oracle {af2,boltz2}` 分支
  - AF2 深度耦合（likely）→ 新建 `modal_boltz2_mber.py`（继续 Step 3.3）

- [x] **Step 3.3: 创建 `modal_boltz2_mber.py`**

  保存到 `~/biomodals/modal_boltz2_mber.py`：

  ```python
  """Boltz-2 oracle MBER — Boltz-2 作为评分函数的 VHH 进化优化
  
  替代 modal_mber.py 中的 AF2-Multimer oracle。
  使用 Boltz-2 ipTM + predicted_ddg 作为适应度函数，
  消除 optimize（AF2）vs validate（Boltz-2）的信号错位。
  
  用法：
    modal run modal_boltz2_mber.py \\
      --target-cif target.cif \\
      --input-fasta candidates.fasta \\
      --hotspot-residues "92,95,96,97,99" \\
      --n-rounds 3 \\
      --top-n 10 \\
      --output-dir ./out/boltz2_mber
  
  优化回路（每轮）：
    1. 对当前候选池运行 Boltz-2 complex prediction
    2. 按 ipTM + predicted_ddg 排名（rank-based composite）
    3. 取 top-N，在 CDR 位置引入点突变（扫描 20 种氨基酸）
    4. 下一轮候选 = top-N 原始 + 突变体
    5. 重复 n_rounds 轮
  
  References:
    - MBER (mber-open): https://github.com/manifoldbio/mber-open
    - Boltz-2: https://github.com/jwohlwend/boltz
  """
  from __future__ import annotations
  
  import os
  import json
  import random
  from pathlib import Path
  from typing import Optional
  
  from modal import App, Image, Volume, Mount
  
  GPU = os.environ.get("GPU", "A100")
  TIMEOUT = int(os.environ.get("TIMEOUT", 120))
  
  BOLTZ2_VOLUME_NAME = "boltz2-weights"
  boltz2_volume = Volume.from_name(BOLTZ2_VOLUME_NAME, create_if_missing=False)
  
  app = App("boltz2-mber")
  
  image = (
      Image.micromamba(python_version="3.11")
      .apt_install("git", "wget")
      .pip_install(
          "boltz",
          "biopython",
          "pandas",
          "numpy",
      )
  )
  
  AMINO_ACIDS = list("ACDEFGHIKLMNPQRSTVWY")
  
  # CDR 区 1-indexed 残基范围（基于 canonical VHH scaffold）
  # 运行时从 cdr_boundaries.py 动态获取，此为 fallback
  _DEFAULT_CDR_RANGES = {
      "cdr1": (26, 35),
      "cdr2": (50, 58),
      "cdr3": (97, 117),
  }
  
  
  def _get_cdr_positions(seq: str) -> list[int]:
      """获取序列中 CDR1+2+3 的 1-indexed 位置列表。"""
      try:
          import sys
          sys.path.insert(0, str(Path(__file__).parent.parent / "protein-design-utils" / "vhh"))
          from cdr_boundaries import get_cdr_boundaries
          bounds = get_cdr_boundaries(seq)
          positions = []
          for region in ("cdr1", "cdr2", "cdr3"):
              s, e = bounds[region]
              positions.extend(range(s, e + 1))
          return positions
      except Exception:
          # Fallback to default CDR ranges
          positions = []
          for s, e in _DEFAULT_CDR_RANGES.values():
              positions.extend(range(s, min(e + 1, len(seq) + 1)))
          return positions
  
  
  def _generate_single_mutants(seq: str, cdr_positions: list[int]) -> list[tuple[str, str]]:
      """
      在 CDR 位置生成单点突变体。
      Returns: list of (mutant_seq, mutation_label)
      """
      mutants = []
      for pos in cdr_positions:
          idx = pos - 1  # 0-indexed
          if idx < 0 or idx >= len(seq):
              continue
          original_aa = seq[idx]
          for aa in AMINO_ACIDS:
              if aa == original_aa:
                  continue
              mutant = seq[:idx] + aa + seq[idx + 1:]
              label = f"{original_aa}{pos}{aa}"
              mutants.append((mutant, label))
      return mutants
  
  
  @app.function(
      timeout=TIMEOUT * 60,
      gpu=GPU,
      volumes={f"/{BOLTZ2_VOLUME_NAME}": boltz2_volume},
      image=image,
  )
  def score_with_boltz2(
      target_cif_content: bytes,
      vhh_sequences: list[str],
      hotspot_residues: list[int],
      target_chain: str = "A",
  ) -> list[dict]:
      """
      用 Boltz-2 对一批 VHH 序列评分（complex prediction）。
  
      Args:
          target_cif_content: 目标蛋白 CIF 内容
          vhh_sequences: VHH 序列列表
          hotspot_residues: hotspot 残基 1-indexed 编号（用于计算接触数）
          target_chain: 目标蛋白链 ID
  
      Returns:
          list of dicts with keys: seq, iptm, ptm, predicted_ddg, hotspot_contacts
      """
      import tempfile
      from pathlib import Path
  
      results = []
  
      with tempfile.TemporaryDirectory() as tmpdir:
          tmpdir = Path(tmpdir)
  
          # 写目标 CIF
          target_path = tmpdir / "target.cif"
          target_path.write_bytes(target_cif_content)
  
          for i, seq in enumerate(vhh_sequences):
              try:
                  # 构建 Boltz-2 输入 FASTA（目标 + VHH）
                  input_fasta = tmpdir / f"input_{i}.fasta"
                  input_fasta.write_text(
                      f">target|{target_chain}\n{_extract_target_seq(target_cif_content, target_chain)}\n"
                      f">vhh\n{seq}\n"
                  )
  
                  out_dir = tmpdir / f"out_{i}"
                  out_dir.mkdir()
  
                  # 运行 Boltz-2（使用预装权重）
                  import subprocess
                  result = subprocess.run(
                      [
                          "boltz", "predict", str(input_fasta),
                          "--out_dir", str(out_dir),
                          "--cache", f"/{BOLTZ2_VOLUME_NAME}",
                          "--override",
                      ],
                      capture_output=True, text=True, timeout=300,
                  )
  
                  if result.returncode != 0:
                      print(f"  Boltz-2 失败 seq_{i}: {result.stderr[-500:]}")
                      results.append({"seq": seq, "iptm": 0.0, "ptm": 0.0,
                                      "predicted_ddg": 0.0, "hotspot_contacts": 0, "error": True})
                      continue
  
                  # 解析 Boltz-2 输出
                  scores = _parse_boltz2_output(out_dir, hotspot_residues, target_chain)
                  scores["seq"] = seq
                  results.append(scores)
  
              except Exception as e:
                  print(f"  评分异常 seq_{i}: {e}")
                  results.append({"seq": seq, "iptm": 0.0, "ptm": 0.0,
                                  "predicted_ddg": 0.0, "hotspot_contacts": 0, "error": True})
  
      return results
  
  
  def _extract_target_seq(cif_content: bytes, chain_id: str) -> str:
      """从 CIF 内容提取指定链的序列。"""
      from Bio.PDB import MMCIFParser
      from io import StringIO
      import warnings
  
      _THREE_TO_ONE = {
          "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
          "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
          "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
          "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
      }
      with warnings.catch_warnings():
          warnings.simplefilter("ignore")
          import tempfile, os
          with tempfile.NamedTemporaryFile(suffix=".cif", delete=False) as f:
              f.write(cif_content)
              fname = f.name
          try:
              parser = MMCIFParser(QUIET=True)
              struct = parser.get_structure("target", fname)
          finally:
              os.unlink(fname)
  
      model = next(struct.get_models())
      chain = model[chain_id]
      return "".join(
          _THREE_TO_ONE.get(r.get_resname(), "X")
          for r in chain.get_residues()
          if r.id[0] == " "
      )
  
  
  def _parse_boltz2_output(out_dir: Path, hotspot_residues: list[int], target_chain: str) -> dict:
      """解析 Boltz-2 输出目录，返回评分 dict。"""
      import json
  
      # Boltz-2 输出 confidence JSON
      conf_files = list(out_dir.rglob("confidence_*.json"))
      if not conf_files:
          return {"iptm": 0.0, "ptm": 0.0, "predicted_ddg": 0.0, "hotspot_contacts": 0}
  
      with open(conf_files[0]) as f:
          conf = json.load(f)
  
      iptm = conf.get("iptm", 0.0)
      ptm = conf.get("ptm", 0.0)
      predicted_ddg = conf.get("affinity", {}).get("affinity_pred_value", 0.0)
  
      # hotspot 接触数（从输出 CIF 计算）
      cif_files = list(out_dir.rglob("*.cif"))
      hotspot_contacts = 0
      if cif_files:
          try:
              from hotspot_prescreen import analyze_structure
              result = analyze_structure(cif_files[0], hotspot_residues, target_chain)
              if result:
                  hotspot_contacts = result["hotspot_contacts"]
          except Exception:
              pass
  
      return {
          "iptm": iptm,
          "ptm": ptm,
          "predicted_ddg": predicted_ddg,
          "hotspot_contacts": hotspot_contacts,
      }
  
  
  def _composite_score(r: dict) -> float:
      """rank-based composite（此处简化为加权和，pipeline 中用 rank）。"""
      return 0.6 * r.get("iptm", 0.0) - 0.4 * max(0, r.get("predicted_ddg", 0.0))
  
  
  @app.local_entrypoint()
  def main(
      target_cif: str,
      input_fasta: str,
      hotspot_residues: str = "92,95,96,97,99",
      n_rounds: int = 3,
      top_n: int = 10,
      output_dir: str = "./out/boltz2_mber",
      target_chain: str = "A",
  ):
      """
      Boltz-2 oracle MBER 进化优化主入口。
  
      Args:
          target_cif: 目标蛋白 CIF 路径
          input_fasta: 初始 VHH 候选 FASTA（来自 L4 developability 过滤后）
          hotspot_residues: 逗号分隔的 hotspot 残基编号（1-indexed）
          n_rounds: 进化轮数（默认 3）
          top_n: 每轮保留的 top 候选数（默认 10）
          output_dir: 输出目录
          target_chain: 目标蛋白链 ID
      """
      import re
  
      out_dir = Path(output_dir)
      out_dir.mkdir(parents=True, exist_ok=True)
  
      # 解析输入
      target_cif_content = Path(target_cif).read_bytes()
      hotspots = [int(x.strip()) for x in hotspot_residues.split(",")]
  
      # 读取初始序列
      seqs = []
      current_id = None
      for line in Path(input_fasta).read_text().splitlines():
          if line.startswith(">"):
              current_id = line[1:].strip()
          elif current_id and line.strip():
              seqs.append(line.strip())
              current_id = None
  
      print(f"初始候选数: {len(seqs)}, 进化轮数: {n_rounds}, top_n: {top_n}")
  
      current_pool = seqs[:top_n] if len(seqs) > top_n else seqs
  
      for round_idx in range(n_rounds):
          print(f"\n=== 第 {round_idx + 1}/{n_rounds} 轮 ===")
          print(f"候选池大小: {len(current_pool)}")
  
          # 生成突变体
          mutants = []
          for seq in current_pool:
              cdr_positions = _get_cdr_positions(seq)
              # 每个序列采样最多 20 个突变（避免组合爆炸）
              all_muts = _generate_single_mutants(seq, cdr_positions)
              random.shuffle(all_muts)
              mutants.extend(m[0] for m in all_muts[:20])
  
          all_candidates = list(set(current_pool + mutants))
          print(f"评分候选总数（原始+突变）: {len(all_candidates)}")
  
          # Boltz-2 评分
          results = score_with_boltz2.remote(
              target_cif_content, all_candidates, hotspots, target_chain
          )
  
          # 过滤错误 + 按 composite 排名
          valid = [r for r in results if not r.get("error")]
          valid.sort(key=_composite_score, reverse=True)
  
          # 保存本轮结果
          round_out = out_dir / f"round_{round_idx + 1:02d}_scores.json"
          with open(round_out, "w") as f:
              json.dump(valid, f, indent=2)
          print(f"本轮结果写入: {round_out}")
          if valid:
              print(f"本轮 top1: iptm={valid[0]['iptm']:.4f}, ddg={valid[0]['predicted_ddg']:.2f}, contacts={valid[0]['hotspot_contacts']}")
  
          # 下一轮候选 = top_n
          current_pool = [r["seq"] for r in valid[:top_n]]
  
      # 输出最终候选 FASTA
      final_fasta = out_dir / "final_candidates.fasta"
      with open(final_fasta, "w") as f:
          for i, seq in enumerate(current_pool):
              f.write(f">boltz2_mber_{i + 1:03d}\n{seq}\n")
      print(f"\n最终候选写入: {final_fasta}")
  ```

- [x] **Step 3.4: 更新 skill L5 调用**

  在 `vhh_max_success_design.md` 的 L5 MBER 章节，将调用命令从：
  ```bash
  modal run ~/biomodals/modal_mber.py ...
  ```
  改为：
  ```bash
  modal run ~/biomodals/modal_boltz2_mber.py \
    --target-cif inputs/target.cif \
    --input-fasta {RESULTS_DIR}/l4_filtered.fasta \
    --hotspot-residues "{HOTSPOT_RESIDUES}" \
    --n-rounds 3 \
    --top-n {L5_MBER_TOP_N} \
    --output-dir {RESULTS_DIR}/boltz2_mber/
  ```

  在调用命令下方加注：
  ```
  > **Oracle 一致性：** Boltz-2 同时作为 L3 主力验证模型和 L5 优化 oracle，
  > 消除 AF2/Boltz-2 排名倒序问题（`domain_protein_design_gotchas #2`）。
  > L5.1 MBER 完成后仍强制重走 L3 四模型验证（`gotchas #2` 要求不变）。
  ```

- [x] **Step 3.5: 重装 skill + commit**

  ```bash
  cd ~/claude-project/ProteinMCP && .venv/bin/pskill install vhh_max_success_design

  cd ~/biomodals
  git add modal_boltz2_mber.py
  git commit -m "feat: add modal_boltz2_mber.py — Boltz-2 oracle MBER

  Replaces AF2-Multimer oracle with Boltz-2 ipTM+ΔΔG fitness function.
  Resolves optimize/validate signal mismatch documented in
  domain_protein_design_gotchas #2 (gB-VHH Task 9-1)."

  cd ~/claude-project/ProteinMCP
  git add workflow-skills/vhh_max_success_design.md
  git commit -m "feat(skill): update L5 MBER to use Boltz-2 oracle"
  ```

---

## Task 4: IgGM 路径独立 L3 过滤阈值

**目标：** 为 IgGM 路径设置宽松 L3 阈值（2/4 模型通过），避免通用阈值系统性误杀 IgGM 独特候选。

**Files:**
- Modify: `~/claude-project/ProteinMCP/workflow-skills/vhh_max_success_design.md`

---

- [x] **Step 4.1: 定位 skill 中 L3_MIN_MODELS_PASS 配置和 L3 过滤逻辑**

  ```bash
  grep -n "L3_MIN_MODELS\|min_models\|iggm\|source=\|path_source" \
    ~/claude-project/ProteinMCP/workflow-skills/vhh_max_success_design.md
  ```

- [x] **Step 4.2: 在 config 区块新增 IgGM 阈值参数**

  在现有 `L3_MIN_MODELS_PASS: 3` 行下方插入：

  ```yaml
  L3_MIN_MODELS_PASS_IGGM: 2     # IgGM 路径单独阈值（分布外构象容忍）
  ```

- [x] **Step 4.3: 更新 L3 过滤逻辑说明**

  找到 L3 过滤说明段落（含"3 of 4 models"或类似描述），修改为：

  ```markdown
  **L3 过滤阈值（按来源路径）：**
  - BoltzGen / Germinal / BindCraft / RFdiffusion 路径：`L3_MIN_MODELS_PASS` (默认 3/4)
  - IgGM 路径：`L3_MIN_MODELS_PASS_IGGM` (默认 2/4，IgGM 生成的构象在 AF2/Protenix 训练分布外概率较高)

  通过宽松阈值的 IgGM 候选，在候选列表中标注 `relaxed_filter=True`，便于后续分析。
  ```

- [x] **Step 4.4: 重装 skill + commit**

  ```bash
  cd ~/claude-project/ProteinMCP && .venv/bin/pskill install vhh_max_success_design

  git add workflow-skills/vhh_max_success_design.md
  git commit -m "feat(skill): add per-path L3 filter threshold for IgGM

  IgGM epitope-conditioned designs may not be well-represented in
  AF2/Protenix training data. Relaxed threshold (2/4 models) prevents
  systematic over-filtering of IgGM-specific conformations."
  ```

---

## Task 5: 阈值校准分析脚本

**目标：** 用 gB-VHH 200 候选数据对 ipTM 和 hotspot_contacts 两个关键阈值做伪 AUC 校准。

**Files:**
- Create: `~/protein-design-utils/vhh/calibrate_thresholds.py`
- Create: `~/protein-design-utils/vhh/calibration_output/`（运行时自动创建）

**数据路径：**
- `top_candidates_v2.csv`: `/Users/guoxingchen/claude-project/ab-design-projects/gB-VHH/out/results/top_candidates_v2.csv`
- 列：`seq_id, b2_iptm, b2_hotspot, bio_pass, ...`

---

- [x] **Step 5.1: 写 `calibrate_thresholds.py`**

  保存到 `~/protein-design-utils/vhh/calibrate_thresholds.py`：

  ```python
  #!/usr/bin/env python3
  """
  calibrate_thresholds.py — VHH pipeline 阈值校准
  =================================================
  用 gB-VHH 历史数据（N=200 候选）对两个关键阈值做伪 AUC 校准：
    1. Boltz-2 ipTM 阈值（L4_IPTM_MIN）
    2. hotspot contact 计数阈值（L2P5_HOTSPOT_MIN_CONTACTS）
  
  伪标签定义：
    正例（弱阳性）：hotspot_contacts >= 2
    负例：hotspot_contacts == 0
  
  用法：
    python calibrate_thresholds.py \\
      --csv /path/to/top_candidates_v2.csv \\
      --out-dir ./calibration_output
  """
  from __future__ import annotations
  
  import argparse
  import json
  from pathlib import Path
  
  import numpy as np
  import pandas as pd
  import matplotlib
  matplotlib.use("Agg")
  import matplotlib.pyplot as plt
  from sklearn.metrics import roc_curve, auc
  
  
  def load_data(csv_path: Path) -> pd.DataFrame:
      """加载并清洗数据。"""
      df = pd.read_csv(csv_path)
      # 确认关键列存在
      required = ["seq_id", "b2_iptm", "b2_hotspot"]
      missing = [c for c in required if c not in df.columns]
      if missing:
          raise ValueError(f"CSV 缺少列: {missing}。现有列: {list(df.columns)}")
  
      df = df.dropna(subset=["b2_iptm", "b2_hotspot"])
      df["b2_hotspot"] = pd.to_numeric(df["b2_hotspot"], errors="coerce").fillna(0).astype(int)
      df["b2_iptm"] = pd.to_numeric(df["b2_iptm"], errors="coerce")
      df = df.dropna(subset=["b2_iptm"])
      return df
  
  
  def module1_iptm_calibration(df: pd.DataFrame, out_dir: Path) -> dict:
      """
      模块 1：Boltz-2 ipTM 阈值校准。
      Returns: {"recommended_iptm_min": float, "youden_j": float, "auc": float}
      """
      print("\n=== 模块 1：ipTM 阈值校准 ===")
  
      # 伪标签：contacts >= 2 为正例，contacts == 0 为负例（排除 contacts == 1 的模糊例）
      df_clean = df[df["b2_hotspot"] != 1].copy()
      df_clean["label"] = (df_clean["b2_hotspot"] >= 2).astype(int)
  
      n_pos = df_clean["label"].sum()
      n_neg = (df_clean["label"] == 0).sum()
      print(f"正例（contacts>=2）: {n_pos}，负例（contacts=0）: {n_neg}，排除 contacts=1: {len(df) - len(df_clean)}")
  
      if n_pos < 3:
          print("[WARN] 正例数量不足（<3），校准结果不可靠。建议降低正例阈值到 contacts>=1。")
          # 退回到 contacts >= 1
          df_clean = df.copy()
          df_clean["label"] = (df_clean["b2_hotspot"] >= 1).astype(int)
          n_pos = df_clean["label"].sum()
          print(f"回退到 contacts>=1：正例 {n_pos}，负例 {(df_clean['label']==0).sum()}")
  
      y_true = df_clean["label"].values
      y_score = df_clean["b2_iptm"].values
  
      fpr, tpr, thresholds = roc_curve(y_true, y_score)
      roc_auc = auc(fpr, tpr)
  
      # Youden's J = sensitivity + specificity - 1 = TPR + (1-FPR) - 1 = TPR - FPR
      j_scores = tpr - fpr
      best_idx = np.argmax(j_scores)
      best_threshold = thresholds[best_idx]
      best_j = j_scores[best_idx]
  
      print(f"ROC AUC: {roc_auc:.3f}")
      print(f"Youden's J 最优阈值: {best_threshold:.4f}（J={best_j:.3f}）")
      print(f"  对应 TPR={tpr[best_idx]:.3f}，FPR={fpr[best_idx]:.3f}")
  
      # 图 1：ipTM 分组分布
      fig, axes = plt.subplots(1, 2, figsize=(12, 5))
  
      groups = {
          "contacts=0（负例）": df[df["b2_hotspot"] == 0]["b2_iptm"],
          "contacts=1（模糊）": df[df["b2_hotspot"] == 1]["b2_iptm"],
          "contacts>=2（正例）": df[df["b2_hotspot"] >= 2]["b2_iptm"],
      }
      colors = ["#d62728", "#ff7f0e", "#2ca02c"]
      for (label, data), color in zip(groups.items(), colors):
          if len(data) > 0:
              axes[0].hist(data, bins=20, alpha=0.6, label=f"{label} (n={len(data)})", color=color)
      axes[0].axvline(best_threshold, color="black", linestyle="--", linewidth=2,
                      label=f"推荐阈值={best_threshold:.3f}")
      axes[0].axvline(0.50, color="gray", linestyle=":", linewidth=1.5, label="当前阈值=0.50")
      axes[0].set_xlabel("Boltz-2 ipTM")
      axes[0].set_ylabel("候选数")
      axes[0].set_title("ipTM 分布（按 hotspot contacts 分组）")
      axes[0].legend(fontsize=9)
  
      # 图 2：ROC 曲线
      axes[1].plot(fpr, tpr, color="#1f77b4", lw=2, label=f"ROC (AUC={roc_auc:.3f})")
      axes[1].scatter(fpr[best_idx], tpr[best_idx], color="red", s=100, zorder=5,
                      label=f"最优阈值={best_threshold:.3f}")
      axes[1].plot([0, 1], [0, 1], "k--", lw=1, alpha=0.5)
      axes[1].set_xlabel("FPR（1 - 特异性）")
      axes[1].set_ylabel("TPR（敏感性）")
      axes[1].set_title("ROC 曲线（ipTM 阈值，伪标签 contacts>=2）")
      axes[1].legend()
  
      plt.tight_layout()
      out_path = out_dir / "figures" / "iptm_calibration.png"
      out_path.parent.mkdir(parents=True, exist_ok=True)
      plt.savefig(out_path, dpi=150, bbox_inches="tight")
      plt.close()
      print(f"图表保存: {out_path}")
  
      return {
          "recommended_iptm_min": round(float(best_threshold), 4),
          "youden_j": round(float(best_j), 4),
          "roc_auc": round(float(roc_auc), 4),
          "n_pos": int(n_pos),
          "n_neg": int(n_neg),
          "current_threshold": 0.50,
          "current_tpr": float(tpr[np.searchsorted(thresholds[::-1], 0.50, side="left")]) if 0.50 in thresholds else None,
      }
  
  
  def module2_contacts_calibration(df: pd.DataFrame, out_dir: Path) -> dict:
      """
      模块 2：hotspot contact 阈值校准。
      Returns: {"recommended_min_contacts": int, "natural_breakpoint": int}
      """
      print("\n=== 模块 2：Hotspot Contact 阈值校准 ===")
  
      # 各 contact 档位的 ipTM 分布
      contacts_range = sorted(df["b2_hotspot"].unique())
      medians = []
      counts = []
      for c in contacts_range:
          subset = df[df["b2_hotspot"] == c]["b2_iptm"]
          medians.append(float(subset.median()))
          counts.append(int(len(subset)))
          print(f"  contacts={c}: n={len(subset)}, ipTM 中位数={subset.median():.4f}, "
                f"mean={subset.mean():.4f}")
  
      # 找 ipTM 中位数的自然断点（最大跳升）
      jumps = [medians[i+1] - medians[i] for i in range(len(medians)-1)]
      if jumps:
          max_jump_idx = np.argmax(jumps)
          breakpoint_contacts = contacts_range[max_jump_idx + 1]
          print(f"最大 ipTM 跳升：contacts {contacts_range[max_jump_idx]} → {contacts_range[max_jump_idx+1]} "
                f"（+{jumps[max_jump_idx]:.4f}）")
          print(f"推荐 hotspot_min_contacts: {breakpoint_contacts}")
      else:
          breakpoint_contacts = 1
          print("跳升分析数据不足，使用默认值 1")
  
      # 图 3：contacts vs ipTM 中位数
      fig, axes = plt.subplots(1, 2, figsize=(12, 5))
  
      axes[0].bar(contacts_range, medians, color="#1f77b4", alpha=0.8)
      axes[0].set_xlabel("hotspot_contacts")
      axes[0].set_ylabel("Boltz-2 ipTM 中位数")
      axes[0].set_title("Hotspot Contact 档位 vs ipTM 中位数")
      axes[0].set_xticks(contacts_range)
      for x, y, n in zip(contacts_range, medians, counts):
          axes[0].text(x, y + 0.005, f"n={n}", ha="center", fontsize=9)
  
      axes[1].bar(contacts_range, counts, color="#ff7f0e", alpha=0.8)
      axes[1].set_xlabel("hotspot_contacts")
      axes[1].set_ylabel("候选数")
      axes[1].set_title("Hotspot Contact 分布（N=200 候选）")
      axes[1].set_xticks(contacts_range)
  
      plt.tight_layout()
      out_path = out_dir / "figures" / "contacts_calibration.png"
      plt.savefig(out_path, dpi=150, bbox_inches="tight")
      plt.close()
      print(f"图表保存: {out_path}")
  
      return {
          "recommended_min_contacts": int(breakpoint_contacts),
          "contacts_distribution": dict(zip([int(c) for c in contacts_range], counts)),
          "iptm_medians_by_contacts": dict(zip([int(c) for c in contacts_range], [round(m, 4) for m in medians])),
      }
  
  
  def write_report(results: dict, out_dir: Path):
      """写 calibration_report.md。"""
      m1 = results["module1"]
      m2 = results["module2"]
  
      report = f"""# VHH 阈值校准报告
  
  **数据来源**：gB-VHH 项目 Task 5-8，N=200 候选
  **伪标签**：hotspot_contacts >= 2 为弱阳性（无实验 ground truth）
  **日期**：{pd.Timestamp.now().strftime('%Y-%m-%d')}
  
  ---
  
  ## 模块 1：Boltz-2 ipTM 阈值
  
  | 指标 | 值 |
  |------|-----|
  | **推荐 L4_IPTM_MIN** | **{m1['recommended_iptm_min']}** |
  | 当前阈值 | {m1['current_threshold']} |
  | ROC AUC | {m1['roc_auc']} |
  | Youden's J | {m1['youden_j']} |
  | 正例数（contacts>=2） | {m1['n_pos']} |
  | 负例数（contacts=0） | {m1['n_neg']} |
  
  ![ipTM 校准图](figures/iptm_calibration.png)
  
  **解读**：ROC AUC={m1['roc_auc']} 表明 ipTM 对"是否有 hotspot 接触"有
  {"一定" if m1['roc_auc'] > 0.6 else "有限"}的判别力。
  {"当前阈值 0.50 偏保守，推荐提高至 " + str(m1['recommended_iptm_min']) if m1['recommended_iptm_min'] > 0.50 else "当前阈值 0.50 偏宽松，推荐提高至 " + str(m1['recommended_iptm_min'])}.
  
  ---
  
  ## 模块 2：Hotspot Contact 阈值
  
  | 指标 | 值 |
  |------|-----|
  | **推荐 L2P5_HOTSPOT_MIN_CONTACTS** | **{m2['recommended_min_contacts']}** |
  | 自然断点 | contacts >= {m2['recommended_min_contacts']} 时 ipTM 中位数显著跳升 |
  
  **Contact 分布：**
  {chr(10).join(f"  - contacts={k}: n={v}（ipTM 中位数={m2['iptm_medians_by_contacts'].get(k, 'N/A')}）" for k, v in m2['contacts_distribution'].items())}
  
  ![Contact 校准图](figures/contacts_calibration.png)
  
  ---
  
  ## 下一步
  
  1. 将推荐阈值更新到 skill（Task 6）：
     - `L4_IPTM_MIN: {m1['recommended_iptm_min']}`
     - `L2P5_HOTSPOT_MIN_CONTACTS: {m2['recommended_min_contacts']}`
  2. 首次实验（SPR/BLI）数据回来后，用实验阳性/阴性替换伪标签重新校准
  
  ---
  *注：本校准基于无实验 ground truth 的伪标签分析，仅作为初步参考。*
  """
  
      report_path = out_dir / "calibration_report.md"
      report_path.write_text(report)
      print(f"\n报告写入: {report_path}")
  
      # 同时写 JSON（供 Task 6 直接读取）
      json_path = out_dir / "calibration_results.json"
      with open(json_path, "w") as f:
          json.dump(results, f, indent=2)
      print(f"JSON 结果写入: {json_path}")
  
  
  def main():
      parser = argparse.ArgumentParser(description="VHH 阈值校准分析")
      parser.add_argument(
          "--csv",
          type=Path,
          default=Path("/Users/guoxingchen/claude-project/ab-design-projects/gB-VHH/out/results/top_candidates_v2.csv"),
          help="top_candidates_v2.csv 路径",
      )
      parser.add_argument(
          "--out-dir",
          type=Path,
          default=Path("~/protein-design-utils/vhh/calibration_output").expanduser(),
          help="输出目录",
      )
      args = parser.parse_args()
  
      args.out_dir.mkdir(parents=True, exist_ok=True)
  
      print(f"加载数据: {args.csv}")
      df = load_data(args.csv)
      print(f"有效候选数: {len(df)}")
      print(f"b2_iptm 范围: {df['b2_iptm'].min():.4f} – {df['b2_iptm'].max():.4f}")
      print(f"b2_hotspot 分布:\n{df['b2_hotspot'].value_counts().sort_index()}")
  
      m1 = module1_iptm_calibration(df, args.out_dir)
      m2 = module2_contacts_calibration(df, args.out_dir)
  
      write_report({"module1": m1, "module2": m2}, args.out_dir)
  
      print("\n✓ 校准分析完成")
      print(f"  推荐 L4_IPTM_MIN: {m1['recommended_iptm_min']}")
      print(f"  推荐 L2P5_HOTSPOT_MIN_CONTACTS: {m2['recommended_min_contacts']}")
  
  
  if __name__ == "__main__":
      main()
  ```

- [x] **Step 5.2: 安装依赖并运行**

  ```bash
  # 检查依赖
  python3.12 -c "import pandas, matplotlib, sklearn, numpy; print('依赖 OK')"
  # 若缺失：pip install pandas matplotlib scikit-learn numpy

  cd ~/protein-design-utils/vhh
  python3.12 calibrate_thresholds.py
  ```

  预期输出：
  ```
  加载数据: .../top_candidates_v2.csv
  有效候选数: 200
  === 模块 1：ipTM 阈值校准 ===
  ROC AUC: 0.xxx
  Youden's J 最优阈值: 0.xxxx
  === 模块 2：Hotspot Contact 阈值校准 ===
  推荐 hotspot_min_contacts: N
  报告写入: .../calibration_report.md
  ✓ 校准分析完成
  ```

- [x] **Step 5.3: 审阅输出报告和图表**

  ```bash
  cat ~/protein-design-utils/vhh/calibration_output/calibration_report.md
  open ~/protein-design-utils/vhh/calibration_output/figures/  # macOS
  ```

  确认：
  - 推荐 ipTM 阈值和当前 0.50 的差异合理
  - Contact 分布图显示大部分候选 contacts=0（与 gB-VHH 已知结论一致）

- [x] **Step 5.4: Commit**

  ```bash
  cd ~/protein-design-utils
  git add vhh/calibrate_thresholds.py vhh/calibration_output/
  git commit -m "feat(vhh): add threshold calibration script

  Pseudo-AUC calibration for Boltz-2 ipTM and hotspot contact thresholds
  using gB-VHH N=200 historical data. Replaces adaptyv:protein-qc defaults
  with VHH-specific values."
  ```

---

## Task 6: 用校准结果更新 Skill

**目标：** 将 T5 校准结果写入 skill config，重装，并更新 memory 记录阈值状态。

**前置条件：** T5 必须完成，`calibration_output/calibration_results.json` 存在。

**Files:**
- Modify: `~/claude-project/ProteinMCP/workflow-skills/vhh_max_success_design.md`
- Modify: `~/.claude/memory/reference_vhh_max_success_skill.md`

---

- [x] **Step 6.1: 读取校准结果**

  ```bash
  cat ~/protein-design-utils/vhh/calibration_output/calibration_results.json
  ```

  记录：
  - `recommended_iptm_min`（替换 skill 中的 `L4_IPTM_MIN: 0.50`）
  - `recommended_min_contacts`（替换 skill 中的 `L2P5_HOTSPOT_MIN_CONTACTS: 1`）

- [x] **Step 6.2: 更新 skill config 中的两个阈值**

  在 `vhh_max_success_design.md` 的 config 区块，更新：

  ```yaml
  L4_IPTM_MIN: <recommended_iptm_min>   # gB-VHH N=200 伪AUC校准 2026-04-xx，AUC=xxx
  L2P5_HOTSPOT_MIN_CONTACTS: <recommended_min_contacts>  # gB-VHH N=200 自然断点校准 2026-04-xx
  ```

  将 `<...>` 替换为 Step 6.1 中读到的实际数值。

- [x] **Step 6.3: 更新 memory 阈值状态节**

  编辑 `~/.claude/memory/reference_vhh_max_success_skill.md`，找到"阈值状态"节，将：

  > 所有 9 个阈值（...）**借自 `adaptyv:protein-qc`，未经 VHH 校准**

  替换为：

  > **ipTM + hotspot_contacts 已校准**（gB-VHH N=200 伪 AUC，2026-04-xx，见 `~/protein-design-utils/vhh/calibration_output/calibration_report.md`）；其余 7 个阈值仍借自 `adaptyv:protein-qc`，待首次实验数据后重新校准。

- [x] **Step 6.4: 重装 skill**

  ```bash
  cd ~/claude-project/ProteinMCP && .venv/bin/pskill install vhh_max_success_design
  ```

  预期：输出 `✓ vhh_max_success_design installed`。

- [x] **Step 6.5: Commit**

  ```bash
  cd ~/claude-project/ProteinMCP
  git add workflow-skills/vhh_max_success_design.md
  git commit -m "feat(skill): update L4_IPTM_MIN and L2P5_HOTSPOT_MIN_CONTACTS with calibrated values

  Source: gB-VHH N=200 pseudo-AUC calibration (2026-04-xx).
  Replaces adaptyv:protein-qc defaults for these two thresholds."

  cd ~/.claude
  git add memory/reference_vhh_max_success_skill.md
  git commit -m "docs(memory): update VHH threshold calibration status"
  ```

---

## 任务依赖总结

```
T1 (L2.5 脚本)         ─ 独立，可先做
T2 (Boltz-2 位置)      ─ 独立，可先做
T3 (MBER oracle)       ─ 独立，可先做（最耗时）
T4 (IgGM 阈值)         ─ 独立，可先做（最简单，5 min）
T5 (校准分析)          ─ 独立，需要 sklearn/matplotlib
T6 (阈值更新)          ─ 依赖 T5 产出

推荐执行顺序: T4 → T2 → T1 → T5 → T6 → T3（T3 最耗时，最后单独对话）
```

---

## 验收清单

- [ ] T1: `hotspot_prescreen.py` 在 gB-VHH 数据上运行无报错，contacts 分布合理
- [ ] T2: skill 中 L3.5c 有 Boltz-2 affinity，L5 重复调用已删除
- [x] T3: `modal_boltz2_mber.py` 通过本地 import 检查，skill L5 调用更新
- [ ] T4: skill config 含 `L3_MIN_MODELS_PASS_IGGM: 2`
- [x] T5: `calibration_report.md` + 2 张图存在，推荐阈值合理
- [x] T6: skill config 含校准值（双轨 L2P5 + ipTM 0.9175），memory 阈值状态节更新，skill 重装成功
