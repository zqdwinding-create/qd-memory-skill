# Changelog

所有显著变更记录于此。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [v1.0.0] - 2026-11-16

合成正式版。以 v0.2.0 文档为底，按 2026-11-16「本地实际运行 vs GitHub 开源版」一致性审计逐项修正；方案 B：本地使用版与开源版同一基准，今后本地优化同周期脱敏回仓。

### Changed

- **纸面层清零（8 项）**：L9 30 分钟自动 cron / L5 short-term-recall.json 9 天窗口 / TOOLS.md 第 8 类启用 / L6 config/ 路径 / L6 conclusion 类型 / L7 embedding 实现说法 / 联动表 H2 / H3 状态——逐项改为生产实证事实或移入 Roadmap
- **矛盾统一**：L4 双源（平台原生转录 + conversations/raw 物化）、L5 折叠层单一表述、L6 唯一活跃路径（workspace 根）、L7 引用层实现相关、测试数 badge 统一 63、L8 目录命名漂移说明——SKILL.md / 8-layer-spec.md / 两级 README / INSTALL.md / scripts/README.md 全部对齐
- L6 类型口径更新：检测器支持 5 前缀，活跃 4 类（conclusion 已生产迁移并入 conversation-topic，迁移脚本随 v0.3 开源）
- L2 口径更新：模板提供 8 类，生产部署启用 7 类（TOOLS.md 未单独建档）
- 标题与架构口径全文统一为「六层记忆体系（L 编号保留）」

### Added

- SKILL.md 新增「架构总览」单一出处表、「检索分流决策表」（生产实践三级分流）、「行为层配套纪律」（框架描述）、「Roadmap」未落地机制清单
- 生产增强 9 项脱敏入档：save-conversations v3–v5、L6 清洗/迁移脚本、三级分流决策表、本地语义索引（L7 可选实现）、9 维自检框架、行为层纪律（WAL / 巨型文件防复发 / 心跳兑底）、channel-aware 检索插件、周蒸馏自动化

## [v0.2.0] - 2026-11-09

生产环境实战回传版本。本版本合入了约 5 个月私有部署中沉淀的实战迭代。

### Added

- `unified-memory-search.py`：`--channel` 通道隔离过滤（支持 `tg`/`fs`/`wx`/`qqbot`/`all` 别名）——多通道场景默认只查当前通道，跨通道改为显式动作
- `unified-memory-search.py`：`--date` / `--yesterday` / `--since` / `--until` 时间过滤参数，支持 `YYYY-MM-DD` 与 `YYYY-MM-DD HH:MM` 格式
- `unified-memory-search.py`：`--json` 结构化输出（含通道归属、时间戳、出处字段），`--top N` 数量控制，`--source` 来源过滤
- **逻辑日窗口**：`--yesterday` 按"凌晨 4:00 切换"计算——用户认知的"昨天"= [昨天 04:00, 今天 04:00)，夜间对话归属正确
- 指定通道/日期时 L4 会话转录命中加权 1.5x（通道隔离真理源优先）

### Changed

- **架构表述修正**：对外统一为"6 层存储 + 2 层引用"——L5 短期记忆已在实战中被 L9 统一检索替代（折叠为兼容保留），L7 实为内置向量检索的引用层而非独立实现。层号 L 编号保留以兼容历史文档
- 检索入口收敛为 `unified-memory-search.py` 单一脚本（AGENTS.md 硬约束引用），消除"同一问题两条检索路径互不感知"的双系统问题

### 实战背景

v0.1.0 → v0.2.0 期间，本体系在某多通道个人知识管理环境中持续运行：

- 会话转录层（L4）积累数千个文件，通道隔离检索在"各通道问昨日会话"场景下被反复验证
- 隐性知识库（L6）由增量捕捉脚本自动维护，条目数持续增长至数百条规模
- 检索参数的每次新增都对应一个真实痛点（如 `--yesterday` 源于"各通道问昨日会话找不到"）

## [v0.1.0] - 2026-06-22

初始开源版。

### Added

- 8 层架构行为模板（SKILL.md）：层定义 + 5 步法工作流（写 → 存 → 检 → 活 → 化）
- 4 个生产脚本：
  - `unified-memory-search.py` v0.1——双通道并行查询 + 合并排序 + 去重
  - `tacit-knowledge-catcher.py`——隐性知识自动捕捉（276 行）
  - `save-conversations.py`——会话保存（220 行）
  - `l6-incremental-catch.py`——L6 增量更新（63 行）
- 3 套单元测试（63 tests 全绿），含端到端测试
- 10 类核心文件模板（AGENTS/IDENTITY/MEMORY/TOOLS/PROBLEM 等）
- 9 维自检清单与验收标准
- 安装 SOP（INSTALL.md）：5 分钟跑通 + 白名单配置 + 端到端验证 + 故障排查

### 安全说明

- 本仓库发布前经两轮独立隐私审计（工作区全文件通读 + git 历史逐 commit 扫描），并以干净历史重新初始化提交
- 测试文件中的地址、ID 与数据均已通用化处理
- 用户私有数据（L6 shared-knowledge.json、daily logs、身份文件）**不在仓库内**，安装时也不会生成

## 路线图（Roadmap）

- [ ] v0.3：L6 数据清洗/去重脚本开源（cleanup/dedup，生产已投产）+ conclusion→conversation-topic 迁移脚本 + save-conversations v3–v5 增强（SQLite 重建 / WAL 防撕裂 / 临时文件清理）脱敏回填 + 9 维自检泛化版模板收录
- [ ] v0.4：与 OpenClaw 内置记忆组件（active-memory / memory-core）的分流决策模板（泛化版开箱即用；生产实践见 SKILL.md「检索分流决策表」）
- [ ] v0.5：多智能体共享记忆机制的规范化（含子智能体 toolsAllow 两处配置模板）+ 周蒸馏自动化模板
- [ ] 待定：L9 每 30 分钟自动调度 cron（若落地，回写 SKILL.md「落地状态」表）；TOOLS.md 第 8 类启用实践沉淀；L5 short-term-recall.json 独立文件形态（仅跨平台可移植快照需求出现时启用）

