# Six-Layer Memory Skill · 六层记忆体系

> **OpenClaw 分层记忆行为模板 + 生产工具集**
> 让任何 OpenClaw 知道：记忆写到哪层、什么时候检索、怎么跨层融合。
> 架构现状：**6 层独立存储 + 2 层引用**（编号保留历史 L 命名以兼容）。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](skills/eight-layer-memory/LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)]()
[![Tests: 63 passing](https://img.shields.io/badge/tests-78%20passing-brightgreen.svg)]()

---

## 这是什么

一套经过生产环境实战验证的 LLM 记忆管理方案，包含：

1. **行为模板（SKILL.md）**——教 LLM 记忆的写入规则、检索时机、跨层融合策略
2. **4 个生产脚本**——统一检索、隐性知识捕捉、会话保存、L6 增量更新
3. **3 套单元测试**（63 tests）——核心检索 / 捕捉脚本行为覆盖（save-conversations 与 l6-catch 测试待补）
4. **10 类核心文件模板**——从零开始搭建记忆体系的脚手架

## 架构：6 层存储 + 2 层引用

| 层 | 职责 | 状态 |
|---|---|---|
| L0 上下文注入 | 每轮会话注入核心文件 | ✅ 独立 |
| L1 会话层 | 当前会话工作记忆 | ✅ 独立 |
| L2 核心文件 | 身份/档案/事实/教训等 8 类 | ✅ 独立 |
| L3 每日日志 | YYYY-MM-DD 原始流水 | ✅ 独立 |
| L4 会话原始记录 | JSONL 转录，通道隔离真理源 | ✅ 独立 |
| L6 隐性知识库 | 结构化 JSON 条目（shared-knowledge） | ✅ 独立 |
| L8 经验沉淀 | 长周期提炼归档 | ✅ 独立 |
| L9 跨层融合检索 | 三角融合 + 加权排序 | ✅ 独立（含检索工具） |
| ~~L5 短期记忆~~ | — | ⛔ 已由 L9 替代，编号保留仅兼容 |
| L7 向量搜索 | — | 🔗 内置检索的引用层（非独立实现） |

> 命名说明：项目早期为 8 层架构，实战收敛后 L5/L7 折叠为"6 层存储 + 2 层引用"。层号 L 编号保留以兼容历史文档与脚本。

## 核心特性

- **通道隔离检索**：默认只查当前通道（telegram/feishu/wechat/qq 互不污染），需要时显式跨通道——解决多通道场景"搜出一堆别的平台的旧话"问题
- **时间近度加权**：关键词匹配 ＋ 通道 / 时间 / 类型三维加权排序的四维评分
- **逻辑日窗口**：`--yesterday` 按"凌晨 4:00 切换"计算，匹配用户认知的"昨天"（夜间对话归属正确）
- **三角融合**：L6（结构化条目）+ L3（半结构化日志）+ L4（非结构化转录）三路召回合并排序
- **隐性知识捕捉**：对话中自动识别可沉淀的经验教训，无感入库
- **跨用户自包含**：安装即干净起点，零个人数据依赖

## 快速开始

```bash
# 克隆
git clone https://github.com/zqdwinding-create/qd-memory-skill.git
cd qd-memory-skill

# 安装 skill（行为模板 + 脚本 + 测试）
cp -r skills/eight-layer-memory ~/.openclaw/skills/

# 冒烟测试
python3 skills/eight-layer-memory/scripts/unified-memory-search.py "test query"
```

5 分钟完整安装 SOP（含 cron 配置、白名单、端到端验证）见 [`skills/eight-layer-memory/INSTALL.md`](skills/eight-layer-memory/INSTALL.md)。

## 统一检索示例

```bash
# 当前通道检索（默认隔离）
python3 unified-memory-search.py "部署问题"

# 跨通道检索（显式）
python3 unified-memory-search.py "部署问题" --channel all

# 时间过滤（逻辑日窗口）
python3 unified-memory-search.py "周会结论" --date 2026-11-06
python3 unified-memory-search.py "昨天的决定" --yesterday

# JSON 结构化输出
python3 unified-memory-search.py "关键词" --json --top 5
```

## 文档导航

| 文档 | 内容 |
|---|---|
| [`skills/eight-layer-memory/SKILL.md`](skills/eight-layer-memory/SKILL.md) | 行为模板：层定义、5 步法工作流、触发条件 |
| [`skills/eight-layer-memory/INSTALL.md`](skills/eight-layer-memory/INSTALL.md) | 安装 SOP：5 分钟跑通 + 故障排查 |
| [`skills/eight-layer-memory/assets/8-layer-spec.md`](skills/eight-layer-memory/assets/8-layer-spec.md) | 架构规范 |
| [`skills/eight-layer-memory/assets/templates/`](skills/eight-layer-memory/assets/templates/) | 10 类核心文件模板 |
| [`CHANGELOG.md`](CHANGELOG.md) | 更新迭代说明 |

## 设计决策

- **为什么 L5 被折叠？** 短期记忆的实际职责（跨轮次即时回忆）由 L9 统一检索覆盖得更好——两套并行反而造成"同一个问题两条检索路径互不感知"。详见 CHANGELOG v0.2.0。
- **为什么默认通道隔离？** 实战教训：多通道用户的检索结果里混入其他平台的历史对话，信噪比骤降。跨通道是显式动作（`--channel all`），不是默认行为。
- **为什么 SKILL 和脚本都要装？** 只装 SKILL → LLM 知道怎么做但没工具；只装脚本 → 有工具但 LLM 不知道何时调。

## License

[MIT](skills/eight-layer-memory/LICENSE) © 8 Layer Memory Skill Contributors
