"""qodercli 本地二进制客户端。

真实 qodercli 是通用 AI 助手 CLI（qodercli -p ...）。
这里通过构造结构化 prompt，让它输出 JSON，再从 stdout 解析结果。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from typing import Any, List, Optional

from promptops.domain.models import RiskLevel, SemanticDiffFinding


class QoderCliError(Exception):
    pass


class QoderCliClient:
    """调用本地 qodercli/qoder-cli 二进制，通过 -p 非交互模式执行 prompt。"""

    def __init__(self, binary: str | None = None) -> None:
        self._binary = binary or self._detect_binary()

    @staticmethod
    def _detect_binary() -> str:
        for name in ["qodercli", "qoder-cli"]:
            if shutil.which(name):
                return name
        raise QoderCliError(
            "qodercli/qoder-cli binary not found in PATH. "
            "Install it or set the binary path explicitly."
        )

    def _call(self, prompt: str) -> str:
        if self._binary is None:
            raise QoderCliError("qodercli binary not configured.")
        proc = subprocess.run(
            [self._binary, "-p", "--output-format", "json", prompt],
            capture_output=True,
        )
        stderr = proc.stderr.decode("utf-8", errors="replace").strip()
        if stderr:
            # qodercli 在未登录等场景会把错误写到 stderr/stdout
            if "not logged in" in stderr.lower() or "login" in stderr.lower():
                raise QoderCliError(
                    f"qodercli is not authenticated: {stderr}. "
                    "Run 'qodercli login' first."
                )
        stdout_text = proc.stdout.decode("utf-8", errors="replace").strip()
        if proc.returncode != 0:
            # 尝试解析 stdout JSON，里面可能包含 is_error + 登录提示
            try:
                err_payload = json.loads(stdout_text) if stdout_text else {}
            except json.JSONDecodeError:
                err_payload = {}
            if err_payload.get("is_error"):
                result = err_payload.get("result", "")
                if "login" in str(result).lower() or "not logged in" in str(result).lower():
                    raise QoderCliError(
                        f"qodercli is not authenticated: {result}. "
                        "Run 'qodercli login' first."
                    )
                raise QoderCliError(f"qodercli returned error: {result}")
            raise QoderCliError(f"qodercli failed (code {proc.returncode}): {stderr or stdout_text}")

        try:
            payload = json.loads(stdout_text)
        except json.JSONDecodeError as exc:
            raise QoderCliError(f"qodercli returned invalid JSON: {exc}") from exc

        if payload.get("is_error"):
            result = payload.get("result", "")
            if "login" in str(result).lower() or "not logged in" in str(result).lower():
                raise QoderCliError(
                    f"qodercli is not authenticated: {result}. "
                    "Run 'qodercli login' first."
                )
            raise QoderCliError(f"qodercli returned error: {result}")

        return str(payload.get("result", ""))

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        text = text.strip()
        # 优先匹配 ```json ... ``` 代码块
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL | re.IGNORECASE)
        if match:
            text = match.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise QoderCliError(f"Could not extract JSON from qodercli output: {exc}") from exc

    # ------------------------------------------------------------------
    # optimize
    # ------------------------------------------------------------------

    def optimize(
        self,
        *,
        current_prompt: str,
        section: str,
        failed_samples: List[dict[str, Any]],
        feedback: List[dict[str, Any]],
    ) -> dict[str, Any]:
        prompt = f"""You are a prompt optimization assistant for an AI agent.

Section to optimize: {section}

Current prompt:
---
{current_prompt}
---

Failed evaluation samples:
{json.dumps(failed_samples, ensure_ascii=False, indent=2)}

Human feedback:
{json.dumps(feedback, ensure_ascii=False, indent=2)}

Please return ONLY a JSON object in the following shape (no markdown, no extra text):
{{
  "optimized_prompt": "<the improved prompt text>",
  "reason": "<why this should help>",
  "expected_improvement": "<what metric should improve>",
  "potential_risks": ["<risk 1>", "<risk 2>"]
}}
"""
        result = self._extract_json(self._call(prompt))
        return {
            "after_value": result.get("optimized_prompt", current_prompt),
            "reason": result.get("reason", "Optimized by qodercli."),
            "expected_improvement": result.get("expected_improvement", ""),
            "potential_risks": result.get("potential_risks", []),
        }

    # ------------------------------------------------------------------
    # gate
    # ------------------------------------------------------------------

    def gate(
        self,
        *,
        condition: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        prompt = f"""You are a release gate evaluator for an AI agent prompt change.

Gate condition:
---
{condition}
---

Context:
{json.dumps(context, ensure_ascii=False, indent=2, default=str)}

Please return ONLY a JSON object in the following shape:
{{
  "passed": true,
  "message": "<short explanation>",
  "evidences": [{{"kind": "llm", "detail": "<supporting detail>", "ref": "<optional>"}}]
}}
"""
        return self._extract_json(self._call(prompt))

    # ------------------------------------------------------------------
    # diff
    # ------------------------------------------------------------------

    def diff(
        self,
        *,
        baseline: dict[str, Any],
        candidate: dict[str, Any],
    ) -> List[SemanticDiffFinding]:
        prompt = f"""You are a semantic diff analyzer for AI agent prompt profiles.

Baseline profile:
{json.dumps(baseline, ensure_ascii=False, indent=2, default=str)}

Candidate profile:
{json.dumps(candidate, ensure_ascii=False, indent=2, default=str)}

Please return ONLY a JSON object in the following shape:
{{
  "findings": [
    {{
      "section": "systemPrompt|tools|examples|...",
      "kind": "semantic_change|capability_change|risk_change",
      "description": "<what changed and why it matters>",
      "risk_level": "low|medium|high|critical",
      "affected_samples": ["sample_id_1"],
      "before_text": "<optional short before text>",
      "after_text": "<optional short after text>"
    }}
  ]
}}
"""
        result = self._extract_json(self._call(prompt))
        raw_findings = result.get("findings", [])
        findings: List[SemanticDiffFinding] = []
        for f in raw_findings:
            risk = f.get("risk_level", "low")
            findings.append(SemanticDiffFinding(
                section=f.get("section", "unknown"),
                kind=f.get("kind", "semantic"),
                description=f.get("description", ""),
                riskLevel=RiskLevel(risk) if risk in ["low", "medium", "high", "critical"] else RiskLevel.low,
                affectedSamples=f.get("affected_samples", []),
                beforeText=f.get("before_text"),
                afterText=f.get("after_text"),
            ))
        return findings
