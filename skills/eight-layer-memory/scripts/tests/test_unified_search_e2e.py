#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D3 · 跨层融合 E2E 单测
"实测"那把尺：每个分数都要有证据 = 每个断言都要验证真实输出

测试覆盖：
1. unified_search 3 通道并行（shared-knowledge + memory-files + session-transcripts）
2. 通道加权（指定 channel 时 L4 +1.5x）
3. 时间近度加权（7d+5 / 30d+2 / 30d+0）
4. 通道隔离（指定 channel 时 channel_isolated=True 排前面）
5. 去重逻辑（相似内容合并）
6. 默认无 channel 过滤时跨通道全搜
7. format_results 文本输出格式

绝不修改 shared-knowledge.json（真实数据）
测试用 mock 替换 3 个 search_* 函数
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

# 用 importlib 直接加载（脚本名带连字符）
import importlib.util
SCRIPTS_DIR = Path(__file__).parent.parent.resolve()
_spec = importlib.util.spec_from_file_location(
    "unified_memory_search",
    SCRIPTS_DIR / "unified-memory-search.py",
)
_ums_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ums_mod)
ums = _ums_mod  # alias

CST = timezone(timedelta(hours=8))
NOW = datetime.now(CST)


def make_sk_result(key, score, type_="system-config", updated="2026-06-22"):
    """生成 mock L6 shared-knowledge 结果"""
    return {
        "score": score,
        "source": "shared-knowledge",
        "type": type_,
        "key": key,
        "answer": f"answer for {key}",
        "conclusion": "",
        "summary": "",
        "updated": updated,
        "source_origin": "test",
    }


def make_mf_result(file, score, line_text=""):
    """生成 mock L3 memory-files 结果"""
    return {
        "score": score,
        "source": "memory-files",
        "file": file,
        "line": 10,
        "text": line_text or f"text in {file}",
    }


def make_st_result(msg_ts, score, channel="telegram"):
    """生成 mock L4 session-transcripts 结果"""
    return {
        "score": score,
        "source": "session-transcripts",
        "file": f"2026-06-{msg_ts[8:10]}_test.jsonl",
        "msg_ts": msg_ts,
        "channel": channel,  # format_results 需此字段
        "text": f"transcript at {msg_ts}",
    }


class TestUnifiedSearchBasic(unittest.TestCase):
    """测试 1：unified_search 3 通道并行 + 合并"""

    def test_three_channels_called(self):
        """3 个 search 函数都被调用"""
        with patch.object(ums, "search_sk", return_value=[]) as mock_sk, \
             patch.object(ums, "search_memory_files", return_value=[]) as mock_mf, \
             patch.object(ums, "search_session_transcripts", return_value=[]) as mock_st:
            ums.unified_search("test query")
        mock_sk.assert_called_once()
        mock_mf.assert_called_once()
        mock_st.assert_called_once()

    def test_combined_results(self):
        """3 通道结果合并"""
        sk = [make_sk_result("sk_key_1", 10)]
        mf = [make_mf_result("memory.md", 8)]
        st = [make_st_result("2026-06-22T08:00:00Z", 5)]
        with patch.object(ums, "search_sk", return_value=sk), \
             patch.object(ums, "search_memory_files", return_value=mf), \
             patch.object(ums, "search_session_transcripts", return_value=st):
            results = ums.unified_search("test")
        # 3 通道都被打 channel tag
        sources = {r.get("source") for r in results}
        self.assertIn("shared-knowledge", sources)
        self.assertIn("memory-files", sources)
        self.assertIn("session-transcripts", sources)
        self.assertEqual(len(results), 3)

    def test_top_n_limit(self):
        """top_n 限制返回数量"""
        sk = [make_sk_result(f"k{i}", 10-i) for i in range(15)]
        mf = [make_mf_result(f"f{i}.md", 10-i) for i in range(15)]
        st = [make_st_result(f"2026-06-{i+10:02d}T08:00:00Z", 5) for i in range(15)]
        with patch.object(ums, "search_sk", return_value=sk), \
             patch.object(ums, "search_memory_files", return_value=mf), \
             patch.object(ums, "search_session_transcripts", return_value=st):
            results = ums.unified_search("test", top_n=5)
        self.assertLessEqual(len(results), 5)


class TestChannelIsolation(unittest.TestCase):
    """测试 2：通道隔离（指定 channel 时 L4 加权）"""

    def test_channel_filter_boosts_l4(self):
        """指定 channel 时 L4 +1.5x 加权 + 时间近度 +5（今天 = 7d 内）"""
        # 用 60 天前的消息避免 7d bonus 干扰
        ts = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
        st = [make_st_result(ts, 10)]
        with patch.object(ums, "search_sk", return_value=[]), \
             patch.object(ums, "search_memory_files", return_value=[]), \
             patch.object(ums, "search_session_transcripts", return_value=st):
            results = ums.unified_search("test", channel="telegram")
        # L4 原始 score=10，int(10*1.5) + 2 = 17（60 天前无 time_bonus）
        l4 = [r for r in results if r["source"] == "session-transcripts"]
        self.assertEqual(l4[0]["score"], 17)  # 10*1.5 + 2 = 17 (老消息无 time bonus)

    def test_channel_isolated_flag(self):
        """指定 channel 时 L4 标记 channel_isolated=True"""
        sk = [make_sk_result("sk1", 10)]
        st = [make_st_result("2026-06-22T08:00:00Z", 10)]
        with patch.object(ums, "search_sk", return_value=sk), \
             patch.object(ums, "search_memory_files", return_value=[]), \
             patch.object(ums, "search_session_transcripts", return_value=st):
            results = ums.unified_search("test", channel="telegram")
        # L4 (channel_isolated=True) 应排在 L6 (channel_isolated=False) 前面
        # 原因：isolated_bonus=1000 + score
        l4_first = results[0]["source"] == "session-transcripts"
        self.assertTrue(l4_first)

    def test_no_filter_all_isolated(self):
        """无 channel 过滤时全部 channel_isolated=True"""
        sk = [make_sk_result("sk1", 10)]
        st = [make_st_result("2026-06-22T08:00:00Z", 5)]
        with patch.object(ums, "search_sk", return_value=sk), \
             patch.object(ums, "search_memory_files", return_value=[]), \
             patch.object(ums, "search_session_transcripts", return_value=st):
            results = ums.unified_search("test")
        # 无 channel 过滤时，3 通道都标记 channel_isolated=True
        for r in results:
            self.assertTrue(r.get("channel_isolated"))


class TestTimeDecay(unittest.TestCase):
    """测试 3：时间近度加权（7d+5 / 30d+2 / 30d+0）"""

    def test_recent_7d_bonus(self):
        """7 天内：+5"""
        # 构造 3 天前的消息
        three_days_ago = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        st = [make_st_result(three_days_ago, 10)]
        with patch.object(ums, "search_sk", return_value=[]), \
             patch.object(ums, "search_memory_files", return_value=[]), \
             patch.object(ums, "search_session_transcripts", return_value=st):
            results = ums.unified_search("test", channel="telegram")
        # score: 10*1.5 + 2 + 5(time_bonus 7d) = 22
        l4 = [r for r in results if r["source"] == "session-transcripts"]
        self.assertEqual(l4[0]["score"], 22)  # 15 + 2 + 5

    def test_30d_bonus(self):
        """30 天内：+2"""
        # 构造 15 天前的消息
        fifteen_days_ago = (datetime.now(timezone.utc) - timedelta(days=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
        st = [make_st_result(fifteen_days_ago, 10)]
        with patch.object(ums, "search_sk", return_value=[]), \
             patch.object(ums, "search_memory_files", return_value=[]), \
             patch.object(ums, "search_session_transcripts", return_value=st):
            results = ums.unified_search("test", channel="telegram")
        # score: 10*1.5 + 2 + 2(time_bonus 30d) = 19
        l4 = [r for r in results if r["source"] == "session-transcripts"]
        self.assertEqual(l4[0]["score"], 19)  # 15 + 2 + 2

    def test_old_no_bonus(self):
        """30 天以上：+0"""
        # 构造 60 天前的消息
        sixty_days_ago = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
        st = [make_st_result(sixty_days_ago, 10)]
        with patch.object(ums, "search_sk", return_value=[]), \
             patch.object(ums, "search_memory_files", return_value=[]), \
             patch.object(ums, "search_session_transcripts", return_value=st):
            results = ums.unified_search("test", channel="telegram")
        # score: 10*1.5 + 2 + 0(time_bonus 老) = 17
        l4 = [r for r in results if r["source"] == "session-transcripts"]
        self.assertEqual(l4[0]["score"], 17)  # 15 + 2 + 0


class TestDeduplication(unittest.TestCase):
    """测试 4：去重逻辑（相似内容合并）"""

    def test_duplicate_content_deduped(self):
        """相似 content 去重（保留高 score）"""
        # 两结果 answer 一样
        sk = [make_sk_result("sk1", 10)]
        sk[0]["answer"] = "identical content"
        mf = [make_mf_result("memory.md", 5)]
        mf[0]["answer"] = "identical content"  # 同 answer
        with patch.object(ums, "search_sk", return_value=sk), \
             patch.object(ums, "search_memory_files", return_value=mf), \
             patch.object(ums, "search_session_transcripts", return_value=[]):
            results = ums.unified_search("test")
        # 去重：sk（score=10）保留，mf（score=5）被去重
        sources = [r.get("source") for r in results]
        self.assertEqual(sources.count("shared-knowledge"), 1)
        self.assertNotIn("memory-files", sources)

    def test_unique_content_kept(self):
        """不同 content 都保留"""
        sk = [make_sk_result("sk1", 10)]
        sk[0]["answer"] = "content A"
        mf = [make_mf_result("memory.md", 5)]
        mf[0]["answer"] = "content B"
        with patch.object(ums, "search_sk", return_value=sk), \
             patch.object(ums, "search_memory_files", return_value=mf), \
             patch.object(ums, "search_session_transcripts", return_value=[]):
            results = ums.unified_search("test")
        self.assertEqual(len(results), 2)


class TestFormatResults(unittest.TestCase):
    """测试 5：format_results 文本输出"""

    def test_format_empty(self):
        """空结果格式"""
        output = ums.format_results([], "test query")
        self.assertIn("test query", output)
        # 应该有"未找到"或类似提示
        self.assertTrue(len(output) > 0)

    def test_format_with_results(self):
        """有结果格式（需打 channel + source 字段走 format_results 路径）"""
        sk = [make_sk_result("记忆 SKILL", 15, type_="capability", updated="2026-06-22")]
        # format_results 需 channel 字段（在 unified_search 内部设置）
        sk[0]["channel"] = "shared-knowledge"
        output = ums.format_results(sk, "记忆 SKILL")
        # 应含 key + type + updated
        self.assertIn("记忆 SKILL", output)
        self.assertIn("capability", output)
        self.assertIn("2026-06-22", output)


class TestEndToEndScenarios(unittest.TestCase):
    """测试 6：端到端场景（实际查询流）"""

    def test_scenario_1_recall_recent(self):
        """场景 1：回忆"昨天聊过什么"（指定 channel + date）"""
        # 模拟真实 L4 + L6 融合
        sk = [make_sk_result("6 层体系 SKILL 化", 5, type_="project-state", updated="2026-06-22")]
        # 3 天前 L4 transcript
        ts = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        st = [make_st_result(ts, 5)]
        with patch.object(ums, "search_sk", return_value=sk), \
             patch.object(ums, "search_memory_files", return_value=[]), \
             patch.object(ums, "search_session_transcripts", return_value=st):
            results = ums.unified_search("6 层体系", channel="telegram")
        # L4 (3d ago, score 5*1.5+2+5=14.5→15) 应比 L6 (score 5) 高
        # 但 L6 无 channel_isolated bonus (0)，L4 有 (1000)
        self.assertEqual(results[0]["source"], "session-transcripts")

    def test_scenario_2_cross_channel(self):
        """场景 2：跨通道搜索（无 channel 过滤）"""
        sk = [make_sk_result("telegram 概念", 10)]
        mf = [make_mf_result("memory.md", 8)]
        st = [make_st_result("2026-06-22T08:00:00Z", 5)]
        with patch.object(ums, "search_sk", return_value=sk), \
             patch.object(ums, "search_memory_files", return_value=mf), \
             patch.object(ums, "search_session_transcripts", return_value=st):
            results = ums.unified_search("telegram")
        # 3 通道全返回
        self.assertEqual(len(results), 3)
        # score 排序：sk(10) > mf(8) > st(5)
        scores = [r["score"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))


if __name__ == "__main__":
    print("=" * 60)
    print("D3 · 跨层融合 E2E 单测('实测'那把尺)")
    print("=" * 60)
    unittest.main(verbosity=2)
