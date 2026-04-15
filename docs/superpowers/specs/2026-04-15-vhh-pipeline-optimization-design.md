# VHH Pipeline Optimization — Design Spec

**日期**：2026-04-15  
**作者**：星辰  
**状态**：已确认，待实现  
**关联 skill**：`~/.claude/skills/vhh-max-success-design/SKILL.md`  
**关联源文件**：`~/claude-project/ProteinMCP/workflow-skills/vhh_max_success_design.md`

---

## 背景与动机

通过对当前 VHH 从头设计 pipeline 的系统审查（2026-04-15），识别出以下需改进的问题：

1. **Hotspot 接触验证窗口太靠后**：gB-VHH 实证显示 10 个 bio_pass 候选中 8 个 `hotspot_contacts=0`，这些候选在进入 L3 四模型验证（算力重）之后才被发现脱靶，造成大量无效计算。
2. **Boltz-2 affinity 使用时机偏晚**：目前在 L5（MBER 之后）才跑 affinity 预测，错失了在 L3 阶段早期剔除低亲和力候选的机会。
3. **MBER oracle 与 validator 不一致**：MBER 用 AF2-Multimer 优化，L3 验证用 Boltz-2/Chai-1，历史技术债导致 optimize/validate 信号错位（gB-VHH Task 9-1 已有实证：AF2 最优 → Chai-1 垫底）。
4. **IgGM 路径被通用阈值系统性过滤**：IgGM 生成的 CDR 构象在 AF2/Protenix 训练分布外概率更高，统一的 `L3_MIN_MODELS_PASS: 3` 会误杀 IgGM 独特候选。
5. **阈值缺乏 VHH 特异性校准**：9 个阈值全部借自 `adaptyv:protein-qc`，基于 gB-VHH 历史数据可对最关键的两个指标（ipTM、hotspot contacts）做伪 AUC 校准。
6. **Germinal 路径缺乏 MCP 包装**（Backlog）：唯一仍用 `modal run` 直接调用的路径，可靠性和可观测性落后于其他路径。

---

## 范围

**纳入本次实现**：T1–T6（6 个任务）  
**不纳入**：Germinal MCP 化（T7，Backlog，见下文触发条件）  
**不受影响**：gB-VHH 当前项目进度——pipeline 改进与 gB-VHH 路径决策解耦

---

## T1：L2.5 几何 Hotspot 预筛脚本

### 问题
所有 5 条 L2 生成路径都输出复合物结构（BoltzGen/IgGM/BindCraft 输出 CIF 复合物，Germinal/RFdiffusion 输出带抗原的骨架 CIF），可以在进入 L3 昂贵验证之前做纯几何分析——零额外 Modal 计算。

### 新脚本

**位置**：`~/protein-design-utils/vhh/hotspot_prescreen.py`

**复用基础设施**：
- VHH 链自动识别（`WG[QR]GT` motif），来自 `filter_dsasa.py`
- CDR 边界检测（IMGT，兼容 longcdr3 `[A-Z]RF[TN]ISRDNAK` FR3 变体），来自 `cdr_boundaries.py`

**算法**：
```
对每个复合物 CIF/PDB：
  1. 自动识别 VHH 链（WG[QR]GT motif）
  2. 识别 CDR1/2/3 残基范围（IMGT 规则）
  3. 从 hotspots.json 读取 hotspot 残基列表（抗原链编号）
  4. 计算 CDR 残基（全重原子）与 hotspot 残基（全重原子）的最近原子距离
  5. 距离 ≤ 8Å 计为一个有效接触
  6. 统计 hotspot_contacts 数（接触的 hotspot 残基个数）
```

**输出 CSV 列**：
```
name, path, hotspot_contacts, contacted_hotspots, cdr1_contacts, cdr2_contacts, cdr3_contacts, cdr3_len, vhh_seq
```

**CLI 接口**：
```bash
python ~/protein-design-utils/vhh/hotspot_prescreen.py \
  <gen_dir> \
  --hotspots inputs/hotspots.json \
  --antigen-chain A \
  --threshold 8.0 \
  --out results/l2p5_prescreen.csv
```

**默认过滤阈值**：`hotspot_contacts >= 1`（宽松——仅排除完全脱靶，不误杀弱接触候选）  
**可由 skill config 覆盖**：`L2P5_HOTSPOT_MIN_CONTACTS: 1`

### Skill 插入位置

```
L2   多路径并行生成（现有）
  ↓
L2.5 几何 hotspot 预筛          ← 新增
  ├── contacts >= L2P5_HOTSPOT_MIN_CONTACTS → 进入 L3 验证池
  └── contacts < 阈值 → 移入 rejected/hotspot_miss/（保留，不删除）
  ↓
L3.0 Ibex 单体 sanity check（现有）
  ↓
L3.1 四模型并行验证（现有）
```

### 预期效果
参照 gB-VHH 数据（10/10 bio_pass 中 8 个 contacts=0），L2.5 可在 L3 前过滤约 80% 无效候选，节省 4 倍以上 L3 算力。

---

## T2：Boltz-2 Affinity 移到 L3.5c

### 改动
将 `boltz2_mcp` affinity 预测从 L5 提前到 **L3.5c**，与 ipSAE（L3.5a）和 dSASA（L3.5b）并行运行。

### 新 L3.5 结构
```
L3.5a  ipSAE rank-based intersection（现有）    ┐
L3.5b  CDR3 dSASA 界面过滤（现有）              ├ 三项并行
L3.5c  Boltz-2 affinity 预测                   ┘  ← 新增
  └── 输出 predicted_ddg 列，加入 composite score 排名（权重 TBD，首次 campaign 后校准）
```

### L5 对应删除
L5 原有的 `boltz2_mcp` affinity 调用步骤移除，避免重复。MBER 后的重验证仍保留 L3 四模型。

---

## T3：MBER Oracle 替换为 Boltz-2

### 问题
MBER（`modal_mber.py`）使用 AF2-Multimer 作为优化 oracle，是历史技术债（AF2 是开发时最优模型）。  
L3 终端验证用 Boltz-2/Chai-1，oracle 和 validator 信号错位，已有实证（gB-VHH Task 9-1）。  
此外，Boltz-2 直接输出 ΔΔG（结合自由能），比 AF2 的 ipTM（结构置信度代理）更适合亲和力成熟优化。

### 两步走

**Step 1 — 审查 `modal_mber.py`**：
- 确认 oracle 是否参数化（有 `--oracle` 参数或可注入评分函数）
- 确认 Boltz-2 ipTM + ΔΔG 可否作为 drop-in 评分信号

**Step 2 — 根据审查结果实现**：

| 情况 | 处理方式 |
|------|---------|
| Oracle 已参数化 | skill 改调用参数 `--oracle boltz2`，无需改脚本 |
| Oracle 硬编码但结构清晰 | `modal_mber.py` 加 `--oracle {af2,boltz2}` 参数 |
| MBER 与 AF2 深度耦合 | 新建 `modal_boltz2_mber.py`，用 Boltz-2 ipTM+ΔΔG 作迭代评分函数 |

### 硬约束不变
L5.1 MBER 完成后仍**强制重走 L3 四模型验证**（`domain_protein_design_gotchas #2` 要求）。oracle 换成 Boltz-2 后，重验证从"救火检查"变为"质量确认"。

---

## T4：IgGM 路径独立 L3 过滤阈值

### 问题
IgGM（epitope-conditioned CDR 设计）生成的构象在 AF2/Protenix 训练分布外概率更高，统一的 `L3_MIN_MODELS_PASS: 3` 会系统性过滤 IgGM 独特候选。

### 改动
在 skill config 新增参数：

```yaml
L3_MIN_MODELS_PASS: 3           # 通用阈值（BoltzGen/Germinal/BindCraft/RFdiffusion）
L3_MIN_MODELS_PASS_IGGM: 2     # IgGM 路径单独阈值
```

L3 过滤逻辑按来源路径选择对应阈值。IgGM 候选通过宽松阈值后，在候选列表中标注：
```
source=iggm, relaxed_filter=True
```
便于后续分析时识别，也可作为校准 IgGM 阈值合理性的元数据。

---

## T5：阈值校准分析脚本

### 数据来源（gB-VHH 200 候选）

| 数据 | 路径 | 说明 |
|------|------|------|
| Boltz-2 ipTM | `ab-design-projects/gB-VHH/out/boltz2/` | Task 5 全量 200 候选 |
| hotspot contacts | `ab-design-projects/gB-VHH/out/results/top_candidates_v2.csv` | Task 8 composite 含 contacts 列 |

**伪标签**：`hotspot_contacts >= 2` → 弱阳性；`contacts = 0` → 阴性（无实验 ground truth）

### 新脚本
**位置**：`~/protein-design-utils/vhh/calibrate_thresholds.py`

**模块 1 — ipTM 阈值校准**：
```
1. 合并 200 候选的 Boltz-2 ipTM + hotspot_contacts
2. 按 contacts 分组（=0 / =1 / >=2）画 ipTM 分布直方图
3. contacts>=2 为正例，contacts=0 为负例 → ROC 曲线 + Youden's J 最优截断点
4. 输出：推荐 L4_IPTM_MIN 值 + 置信区间
```

**模块 2 — Hotspot contact 阈值校准**：
```
1. 统计 contacts 分布（0/1/2/3/4/5）
2. 计算各 contacts 档位的 Boltz-2 ipTM 中位数
3. 找 ipTM 中位数出现明显跳升的 contacts 档位（自然断点）
4. 输出：推荐 L2P5_HOTSPOT_MIN_CONTACTS 值
```

**输出**：
- `calibration_report.md`（分析结论 + 推荐阈值）
- `figures/iptm_distribution_by_contacts.png`
- `figures/roc_curve_iptm.png`
- `figures/contacts_vs_iptm_median.png`

---

## T6：用校准结果更新 Skill

T5 完成后，用 `calibration_report.md` 中的推荐值更新：

**`vhh_max_success_design.md` config 区**：
```yaml
L4_IPTM_MIN: <校准值>    # 替换 0.50，注明"gB-VHH N=200 伪AUC校准 2026-04-xx"
L2P5_HOTSPOT_MIN_CONTACTS: <校准值>   # 替换默认值 1
```

**`~/.claude/memory/reference_vhh_max_success_skill.md` 阈值状态节**：
- 将"借自 adaptyv:protein-qc，未经 VHH 校准"改为"ipTM + hotspot_contacts 已校准（gB-VHH N=200 伪 AUC，2026-04-xx）；其余 7 个阈值仍待实验数据校准"

安装更新后的 skill：
```bash
cd ~/claude-project/ProteinMCP && .venv/bin/pskill install vhh_max_success_design
```

---

## T7：Germinal MCP 化（Backlog，不纳入实现计划）

**当前状态**：`modal_germinal.py` 用 `modal run` 直接调用，无 pmcp 任务追踪，无统一错误处理。

**不做的原因**：Germinal 生成质量和命中率尚未在项目中实证，工程投入应等验证后再做。

**触发条件**（满足后开新对话启动）：
> 任一 VHH 项目中 Germinal 路径贡献了进入 L4 的候选 ≥5 个 → 参考 `feedback_tool_onboarding.md` 三步闭环启动 MCP 化。

---

## 任务依赖关系

```
T1（L2.5 脚本）──────────────────────────────────────┐
T2（Boltz-2 affinity 移位）──────────────────────────┤
T3（MBER oracle 替换）──── Step 1 审查 → Step 2 实现  ├→ T6（skill 更新 + 重装）
T4（IgGM 独立阈值）──────────────────────────────────┤
T5（阈值校准分析）────────────────────────────────────┘
```

T1–T4 相互独立，可并行实现。T5 依赖 gB-VHH 历史数据（已有，无需等待）。T6 依赖 T5 产出。

---

## 成功标准

| 任务 | 验收条件 |
|------|---------|
| T1 | `hotspot_prescreen.py` 在 gB-VHH out/ 上运行无报错，contacts 列分布与 Task 8 composite 数据吻合 |
| T2 | skill 中 L3.5c 有 Boltz-2 affinity 调用，L5 重复调用已删除 |
| T3 | `modal_mber.py` 或新脚本使用 Boltz-2 作 oracle，smoke test 通过 |
| T4 | skill config 含 `L3_MIN_MODELS_PASS_IGGM: 2`，L3 逻辑按路径分流 |
| T5 | `calibration_report.md` 产出，含推荐 ipTM 阈值和 hotspot 阈值，附 3 张图 |
| T6 | skill 重装成功，两个阈值更新，`reference_vhh_max_success_skill.md` 阈值状态节更新 |
