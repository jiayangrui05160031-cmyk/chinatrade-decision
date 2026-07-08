"""Tests for agent/agent.py _extract_pseudo_tool_call.

MiniMax LLM 经常把 function call 写在文本里, 不走标准 tool_calls 字段.
这个函数负责兜底解析.
"""

from __future__ import annotations

from wto_policy.agent.agent import _extract_pseudo_tool_call


class TestPseudoToolCall:
    def test_tool_call_xml(self) -> None:
        """Qwen/Llama 风格: <tool_call>{...}</tool_call>"""
        text = '分析: <tool_call>{"name": "lookup_tariff", "arguments": {"hs_code": "9405408000"}}</tool_call>'
        result = _extract_pseudo_tool_call(text)
        assert result is not None
        name, args = result
        assert name == "lookup_tariff"
        assert args["hs_code"] == "9405408000"

    def test_tool_call_xml_with_string_args(self) -> None:
        """arguments 是 string 的情况."""
        text = '<tool_call>{"name": "search_hs_codes", "arguments": "{\\"query\\": \\"led\\"}"}</tool_call>'
        result = _extract_pseudo_tool_call(text)
        assert result is not None
        name, args = result
        assert name == "search_hs_codes"
        assert args["query"] == "led"

    def test_functions_dot_call(self) -> None:
        """MiniMax 风格: functions.NAME({...})"""
        text = '接下来调: functions.lookup_tariff({"hs_code": "9405408000", "cif_value_usd": 50000, "destination": "US"})'
        result = _extract_pseudo_tool_call(text)
        assert result is not None
        name, args = result
        assert name == "lookup_tariff"
        assert args["hs_code"] == "9405408000"
        assert args["cif_value_usd"] == 50000

    def test_tools_dot_call(self) -> None:
        """通用: tools.NAME({...})"""
        text = 'tools.search_hs_codes({"query": "LED"})'
        result = _extract_pseudo_tool_call(text)
        assert result is not None
        name, args = result
        assert name == "search_hs_codes"
        assert args["query"] == "LED"

    def test_no_pseudo_call(self) -> None:
        """普通文本, 没 function call."""
        text = "这是一个普通的回答, 没有 function call"
        result = _extract_pseudo_tool_call(text)
        assert result is None

    def test_empty(self) -> None:
        assert _extract_pseudo_tool_call("") is None
        assert _extract_pseudo_tool_call(None) is None  # type: ignore[arg-type]

    def test_malformed_json(self) -> None:
        text = 'functions.lookup_tariff({broken json})'
        result = _extract_pseudo_tool_call(text)
        assert result is None  # JSON 坏了解不出

    def test_realistic_agent_response(self) -> None:
        """真实场景: 之前 LLM 返回的完整文本."""
        text = """根据您提供的产品描述, 我找到了几个可能的 HS 编码:
1. 9405408000 - 其他 LED 灯具

接下来, 我将为您计算关税:

```typescript
functions.lookup_tariff({"hs_code": "9405408000", "cif_value_usd": 50000, "destination": "US"})
```
"""
        result = _extract_pseudo_tool_call(text)
        assert result is not None
        name, args = result
        assert name == "lookup_tariff"
        assert args["hs_code"] == "9405408000"
        assert args["cif_value_usd"] == 50000
