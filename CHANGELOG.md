# Changelog

所有显著变更记录于此。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

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

- [ ] v0.3：L6 数据清洗/去重脚本开源（cleanup/dedup）
- [ ] v0.4：与 OpenClaw 内置记忆组件（active-memory / memory-core）的分流决策模板
- [ ] v0.5：多智能体共享记忆机制的规范化

