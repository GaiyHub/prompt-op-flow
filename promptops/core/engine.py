"""Pipeline 核心引擎：所有 governance 操作。"""
from __future__ import annotations

from typing import Any, List, Optional

from promptops.adapters.contract import EvalSample, PublishRequest, TargetPlatformAdapter
from promptops.adapters.registry import AdapterRegistry
from promptops.core.ledger import Ledger
from promptops.core.planner import auto_runnable, plan_steps
from promptops.core.policy import evaluate_action
from promptops.core.steps import DiffAnalyzerRegistry, EvaluatorRegistry, OptimizerRegistry, is_interactive
from promptops.core.template import TemplateResolver, required_evidence
from promptops.domain.hashing import content_hash
from promptops.domain.models import (
    AgentProfile,
    AgentProfileVersion,
    ChangeStatus,
    ConnectResult,
    DriftEvent,
    EvalRun,
    GateReport,
    HumanFeedback,
    PatchProposal,
    ProfileStatus,
    PromptProfileChange,
    PublishResult,
    RemoteProfile,
    ReviewDecision,
    ReviewDecisionType,
    SemanticDiff,
)
from promptops.services.diff import QoderCliSemanticDiffAnalyzer, build_semantic_diff, render_diff_markdown
from promptops.services.drift import build_drift_event, detect_drift
from promptops.services.evaluator import LocalEvaluator, build_eval_run
from promptops.services.gate import DEFAULT_GATE_RULES, evaluate_gate
from promptops.services.gate_executors.registry import GateExecutorRegistry
from promptops.services.optimizer import OptimizerContext, QoderCliOptimizer, RuleBasedOptimizer, build_patch_from_optimizer
from promptops.services.profile import apply_patch, clone_profile
from promptops.services.publish import check_publish_evidence
from promptops.storage.workspace import Workspace
from promptops.util import gen_id, now


class Engine:
    """Engine 是唯一的共享状态层。"""

    def __init__(
        self,
        ws: Workspace,
        adapters: AdapterRegistry,
        template_resolver: TemplateResolver,
        evaluator: LocalEvaluator | None = None,
        optimizer: RuleBasedOptimizer | None = None,
        gate_rules: list | None = None,
        qodercli_binary: str | None = None,
    ) -> None:
        self.ws = ws
        self.adapters = adapters
        self.templates = template_resolver
        self.qodercli_binary = qodercli_binary

        # 可插拔 Registry
        self.evaluator_registry = EvaluatorRegistry()
        self.evaluator_registry.register("local", evaluator or LocalEvaluator())
        self.optimizer_registry = OptimizerRegistry()
        self.optimizer_registry.register("rule-based", optimizer or RuleBasedOptimizer())
        self.optimizer_registry.register("qoder-cli", QoderCliOptimizer(binary=qodercli_binary))
        self.diff_analyzer_registry = DiffAnalyzerRegistry()
        self.diff_analyzer_registry.register("heuristic", None)  # 占位，实际在 diff() 中默认使用
        self.diff_analyzer_registry.register("qoder-cli", QoderCliSemanticDiffAnalyzer(binary=qodercli_binary))

        self.evaluator = evaluator or LocalEvaluator()
        self.optimizer = optimizer or RuleBasedOptimizer()
        self.gate_rules = gate_rules or DEFAULT_GATE_RULES
        self.gate_executor_registry = GateExecutorRegistry(qodercli_binary=qodercli_binary)
        self.ledger = Ledger(ws)

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _adapter(self, change_id: str) -> TargetPlatformAdapter:
        data = self._run_for_change(change_id)
        return self.adapters.get(data["platform"])

    def _run_for_change(self, change_id: str) -> dict[str, Any]:
        rows = self.ws.db.all_records(change_id)
        for r in reversed(rows):
            if r.event == "pipeline_started":
                return r.data
        raise ValueError(f"No pipeline metadata found for change '{change_id}'.")

    def _candidate_profile(self, change_id: str) -> dict[str, Any]:
        """返回 {baseline, candidate, patches}。"""
        change = self.ws.db.get_change(change_id)
        baseline = self.ws.db.get_version(change.sourceVersionId)
        if baseline is None:
            raise ValueError("Baseline version not found.")
        patches = self.ws.db.all_patches(change_id)
        candidate = clone_profile(baseline.normalized)
        for p in patches:
            candidate = apply_patch(candidate, p)
        return {"baseline": baseline, "candidate": candidate, "patches": patches}

    def _guard(self, action: str, human: bool) -> None:
        verdict = evaluate_action(action, human)
        if not verdict.allowed:
            raise PermissionError(verdict.reason)

    def _guard_step_by_type(self, change_id: str, step_type_name: str) -> None:
        plan = self.plan(change_id)
        for p in plan:
            if p["type"] == step_type_name and p["status"] != "ready":
                raise ValueError(
                    f"Step '{p['id']}' is {p['status']}. Blocked by: {p['blocked_by']}"
                )

    def _template(self, change_id: str) -> Any:
        data = self._run_for_change(change_id)
        return self.templates.resolve(data["platform"], data["platformAgentId"], data.get("templateId"))

    # ------------------------------------------------------------------
    # connect
    # ------------------------------------------------------------------

    async def connect(
        self,
        *,
        platform: str,
        platform_agent_id: str,
        reason: str,
        template: str | None = None,
        created_by: str = "system",
    ) -> ConnectResult:
        adapter = self.adapters.get(platform)
        resolved_template = self.templates.resolve(platform, platform_agent_id, template)

        status = adapter.connect(platform_agent_id)
        if not status.connected:
            raise ConnectionError(status.message)

        change_id = gen_id("change")
        change = PromptProfileChange(
            id=change_id,
            agentId=f"{platform}:{platform_agent_id}",
            reason=reason,
            status=ChangeStatus.open,
            createdBy=created_by,
            createdAt=now(),
            updatedAt=now(),
        )
        self.ws.db.save_change(change)

        # ledger: pipeline started
        self.ledger.append(change_id, "pipeline_started", {
            "platform": platform,
            "platformAgentId": platform_agent_id,
            "templateId": resolved_template.id,
            "changeId": change_id,
        })

        # fetch profile + drift check
        fetched = adapter.fetch_profile(platform_agent_id)
        remote_hash = content_hash(fetched.remote.raw)

        latest_published = self.ws.db.latest_production_version(change.agentId)
        drift_detected = detect_drift(remote=fetched.remote, latest_production=latest_published)
        drift_event_id = None
        if drift_detected:
            drift = build_drift_event(
                change_id=change_id,
                agent_id=change.agentId,
                baseline_hash=latest_published.remoteHash if latest_published else "",
                remote_hash=remote_hash,
            )
            self.ws.db.save_drift_event(drift)
            drift_event_id = drift.id

        baseline_version = AgentProfileVersion(
            id=gen_id("version"),
            agentId=change.agentId,
            status=ProfileStatus.baseline,
            normalized=fetched.normalized,
            remote=fetched.remote,
            normalizedHash=content_hash(fetched.normalized.model_dump()),
            remoteHash=remote_hash,
            platformVersionId=fetched.platformVersionId,
            createdBy=created_by,
            createdAt=now(),
            changeId=change_id,
        )
        self.ws.db.save_version(baseline_version)
        change.sourceVersionId = baseline_version.id
        change.updatedAt = now()
        self.ws.db.save_change(change)

        # registry evidence
        self.ws.registry.write_yaml(f"changes/{change_id}/pipeline.yaml", resolved_template.model_dump())
        self.ws.registry.write_yaml(f"changes/{change_id}/baseline/profile.normalized.yaml", fetched.normalized.model_dump())
        self.ws.registry.write_json(f"changes/{change_id}/baseline/profile.remote.json", fetched.remote.raw)

        self.ledger.append(change_id, "step_completed", {"step": "connect", "baseline_version_id": baseline_version.id})
        self.ws.registry.commit(f"connect: baseline for {change_id}")

        return ConnectResult(
            changeId=change_id,
            baselineVersionId=baseline_version.id,
            driftDetected=drift_detected,
            driftEventId=drift_event_id,
        )

    # ------------------------------------------------------------------
    # accept_drift_as_baseline
    # ------------------------------------------------------------------

    async def accept_drift_as_baseline(
        self,
        change_id: str,
        actor: str,
    ) -> ConnectResult:
        self._guard("accept_drift_as_baseline", human=True)
        drift = self.ws.db.unaccepted_drift(change_id)
        if drift is None:
            raise ValueError("No unaccepted drift for this change.")

        change = self.ws.db.get_change(change_id)
        run_meta = self._run_for_change(change_id)
        platform = run_meta["platform"]
        platform_agent_id = run_meta["platformAgentId"]
        adapter = self.adapters.get(platform)

        # 拉取当前远程 profile 作为新 baseline
        fetched = adapter.fetch_profile(platform_agent_id)
        remote_hash = content_hash(fetched.remote.raw)

        # 标记 drift 已接受
        drift.accepted = True
        drift.acceptedBy = actor
        drift.acceptedAt = now()
        self.ws.db.save_drift_event(drift)

        # 创建新的 baseline version 并原地更新当前 change
        baseline_version = AgentProfileVersion(
            id=gen_id("version"),
            agentId=change.agentId,
            status=ProfileStatus.baseline,
            normalized=fetched.normalized,
            remote=fetched.remote,
            normalizedHash=content_hash(fetched.normalized.model_dump()),
            remoteHash=remote_hash,
            platformVersionId=fetched.platformVersionId,
            createdBy=actor,
            createdAt=now(),
            changeId=change_id,
        )
        self.ws.db.save_version(baseline_version)

        change.sourceVersionId = baseline_version.id
        change.targetVersionId = None
        change.status = ChangeStatus.open
        change.updatedAt = now()
        self.ws.db.save_change(change)

        # 覆盖 baseline 证据目录
        self.ws.registry.write_yaml(f"changes/{change_id}/baseline/profile.normalized.yaml", fetched.normalized.model_dump())
        self.ws.registry.write_json(f"changes/{change_id}/baseline/profile.remote.json", fetched.remote.raw)

        self.ledger.append(change_id, "action", {
            "type": "accept_drift_as_baseline",
            "drift_id": drift.id,
            "new_baseline_version_id": baseline_version.id,
        })
        self.ws.registry.commit(f"accept-drift: {change_id}")

        return ConnectResult(
            changeId=change_id,
            baselineVersionId=baseline_version.id,
            driftDetected=False,
            driftEventId=drift.id,
        )

    # ------------------------------------------------------------------
    # evaluate
    # ------------------------------------------------------------------

    async def evaluate(
        self,
        change_id: str,
        samples: List[EvalSample],
        role: str = "baseline",
        suite: str = "default",
        implementation: str | None = None,
    ) -> EvalRun:
        adapter = self._adapter(change_id)
        evaluator = self.evaluator

        override = None
        profile_ref = "baseline"
        if role == "candidate":
            cdata = self._candidate_profile(change_id)
            override = cdata["candidate"]
            profile_ref = "candidate"

        self.ledger.append(change_id, "step_started", {"step": f"{role}_eval"})
        results = adapter.run_batch(self._run_for_change(change_id)["platformAgentId"], samples, override)
        scored = evaluator.score(samples, results)
        run = build_eval_run(
            change_id=change_id,
            profile_ref=profile_ref,
            suite=suite,
            role=role,  # type: ignore
            sample_results=scored,
        )
        self.ws.db.save_eval_run(run)

        detail_ref = self.ws.artifacts.put_json(f"eval/{role}", [s.model_dump() for s in run.samples])
        summary = {
            "id": run.id,
            "role": role,
            "suite": suite,
            "passRate": run.passRate,
            "dimensionScores": run.dimensionScores,
            "sampleCount": len(run.samples),
            "detailRef": detail_ref,
        }
        if role == "baseline":
            self.ws.registry.write_yaml(f"changes/{change_id}/baseline/eval-summary.yaml", summary)
        else:
            self.ws.registry.write_yaml(f"changes/{change_id}/patch/candidate-eval-summary.yaml", summary)

        self.ledger.append(change_id, "step_completed", {"step": f"{role}_eval", "eval_run_id": run.id})
        self.ws.registry.commit(f"{role} eval: {change_id}")
        return run

    # ------------------------------------------------------------------
    # feedback
    # ------------------------------------------------------------------

    async def submit_feedback(
        self,
        change_id: str,
        *,
        source: str,
        issue_type: str,
        severity: str,
        expected: str,
        section: str | None = None,
        sample_id: str | None = None,
        created_by: str = "human",
    ) -> HumanFeedback:
        self._guard("submit_feedback", human=True)
        feedback = HumanFeedback(
            id=gen_id("feedback"),
            changeId=change_id,
            source=source,
            issueType=issue_type,
            severity=severity,
            expected=expected,
            section=section,
            sampleId=sample_id,
            createdBy=created_by,
            createdAt=now(),
        )
        self.ws.db.save_feedback(feedback)
        self.ledger.append(change_id, "action", {"type": "submit_feedback", "feedback_id": feedback.id})
        self.ws.registry.commit(f"feedback: {change_id}")
        return feedback

    # ------------------------------------------------------------------
    # patch
    # ------------------------------------------------------------------

    async def propose_patch(
        self,
        change_id: str,
        *,
        section: str,
        after: Any,
        reason: str,
        before: Any | None = None,
        resolves: list[str] | None = None,
        created_by: str = "human",
    ) -> PatchProposal:
        self._guard("propose_patch", human=True)
        cdata = self._candidate_profile(change_id)
        if before is None:
            from promptops.services.profile import section_value
            before = section_value(cdata["baseline"].normalized, section)
        patch = PatchProposal(
            id=gen_id("patch"),
            changeId=change_id,
            targetSection=section,
            beforeValue=before,
            afterValue=after,
            reason=reason,
            linkedFailures=resolves or [],
            expectedImprovement="",
            potentialRisks=[],
            source="human_feedback",
            createdBy=created_by,
            createdAt=now(),
        )
        self.ws.db.save_patch(patch)
        self.ws.registry.write_yaml(f"changes/{change_id}/patch/patch.yaml", patch.model_dump())
        self.ledger.append(change_id, "action", {"type": "propose_patch", "patch_id": patch.id})
        self.ws.registry.commit(f"patch: {change_id}")
        return patch

    async def optimize_patch(
        self,
        change_id: str,
        *,
        section: str = "systemPrompt",
        implementation: str = "rule-based",
        created_by: str = "optimizer",
    ) -> PatchProposal:
        self._guard("optimize_patch", human=False)
        cdata = self._candidate_profile(change_id)
        baseline_eval = self.ws.db.latest_eval_run(change_id, "baseline")
        if baseline_eval is None:
            raise ValueError("Baseline eval required before optimization.")
        feedback = self.ws.db.all_feedback(change_id)
        run_meta = self._run_for_change(change_id)
        background = self.templates.background(
            run_meta["platform"],
            run_meta["platformAgentId"],
        )
        ctx = OptimizerContext(
            change_id=change_id,
            baseline_profile=cdata["baseline"].normalized,
            baseline_eval=baseline_eval,
            feedback=feedback,
            target_section=section,
            background=background,
        )
        optimizer = self.optimizer_registry.get(implementation)
        opt_input = optimizer.optimize(ctx)
        patch = build_patch_from_optimizer(ctx, opt_input, created_by=created_by)
        self.ws.db.save_patch(patch)
        self.ws.registry.write_yaml(f"changes/{change_id}/patch/patch.yaml", patch.model_dump())
        self.ledger.append(change_id, "action", {"type": "optimize_patch", "patch_id": patch.id})
        self.ws.registry.commit(f"optimize: {change_id}")
        return patch

    # ------------------------------------------------------------------
    # diff
    # ------------------------------------------------------------------

    async def diff(
        self,
        change_id: str,
        *,
        implementation: str = "heuristic",
    ) -> SemanticDiff:
        cdata = self._candidate_profile(change_id)
        findings = None
        if implementation == "qoder-cli":
            analyzer = self.diff_analyzer_registry.get("qoder-cli")
            findings = analyzer.analyze(cdata["baseline"].normalized, cdata["candidate"])
        diff = build_semantic_diff(
            change_id=change_id,
            agent_id=cdata["baseline"].agentId,
            baseline=cdata["baseline"].normalized,
            candidate=cdata["candidate"],
            baseline_ref=cdata["baseline"].id,
            candidate_ref="candidate",
            findings=findings,
        )
        self.ws.db.save_semantic_diff(diff)
        self.ws.registry.write_text(f"changes/{change_id}/patch/semantic-diff.md", render_diff_markdown(diff))
        self.ledger.append(change_id, "step_completed", {"step": "diff", "diff_id": diff.id})
        self.ws.registry.commit(f"diff: {change_id}")
        return diff

    # ------------------------------------------------------------------
    # gate
    # ------------------------------------------------------------------

    async def gate(
        self,
        change_id: str,
        *,
        stage: str = "candidate",
    ) -> GateReport:
        baseline_eval = self.ws.db.latest_eval_run(change_id, "baseline")
        candidate_eval = self.ws.db.latest_eval_run(change_id, "candidate")
        diff = self.ws.db.latest_semantic_diff(change_id)
        feedback = self.ws.db.all_feedback(change_id)
        report = evaluate_gate(
            change_id=change_id,
            baseline_eval=baseline_eval,
            candidate_eval=candidate_eval,
            diff=diff,
            feedback=feedback,
            rules=self.gate_rules,
            stage=stage,
            executor_registry=self.gate_executor_registry,
        )
        self.ws.db.save_gate_report(report)
        self.ws.registry.write_yaml(f"changes/{change_id}/patch/gate-report.yaml", report.model_dump())
        self.ledger.append(change_id, "step_completed", {"step": "gate", "gate_report_id": report.id})
        self.ws.registry.commit(f"gate: {change_id}")
        return report

    # ------------------------------------------------------------------
    # review
    # ------------------------------------------------------------------

    async def review(
        self,
        change_id: str,
        *,
        decision: ReviewDecisionType,
        reviewer: str,
        comment: str = "",
        waiver: str | None = None,
    ) -> ReviewDecision:
        self._guard("review", human=True)
        self._guard_step_by_type(change_id, "review")
        rd = ReviewDecision(
            id=gen_id("review"),
            changeId=change_id,
            decision=decision,
            reviewer=reviewer,
            comment=comment,
            waiver=waiver,
            createdAt=now(),
        )
        self.ws.db.save_review_decision(rd)
        self.ws.registry.write_yaml(f"changes/{change_id}/patch/review.yaml", rd.model_dump())
        if decision == ReviewDecisionType.approve or decision == ReviewDecisionType.approve_with_waiver:
            self.ws.db.update_change_status(change_id, ChangeStatus.in_review)
        elif decision == ReviewDecisionType.reject:
            self.ws.db.update_change_status(change_id, ChangeStatus.rejected)
        self.ledger.append(change_id, "action", {"type": "review", "decision": decision.value, "review_id": rd.id})
        self.ws.registry.commit(f"review: {change_id}")
        return rd

    # ------------------------------------------------------------------
    # publish
    # ------------------------------------------------------------------

    async def publish(
        self,
        change_id: str,
        *,
        publisher: str,
    ) -> PublishResult:
        self._guard("publish", human=True)
        self._guard_step_by_type(change_id, "publish")

        cdata = self._candidate_profile(change_id)
        baseline_eval = self.ws.db.latest_eval_run(change_id, "baseline")
        candidate_eval = self.ws.db.latest_eval_run(change_id, "candidate")
        diff = self.ws.db.latest_semantic_diff(change_id)
        gate_report = self.ws.db.latest_gate_report(change_id)
        review_decision = self.ws.db.latest_review_decision(change_id)

        # drift block
        drift = self.ws.db.unaccepted_drift(change_id)
        if drift is not None:
            raise ValueError("Publish blocked: unresolved external drift.")

        # gate block (waiver check)
        if gate_report and gate_report.outcome == "blocked":
            if not (review_decision and review_decision.decision == ReviewDecisionType.approve_with_waiver):
                raise ValueError("Publish blocked: gate blocked without waiver.")

        # evidence check
        tpl = self._template(change_id)
        evidence = {
            "baseline_eval": baseline_eval,
            "candidate_eval": candidate_eval,
            "diff": diff,
            "gate_report": gate_report,
            "review_decision": review_decision,
        }
        check = check_publish_evidence(evidence, required_evidence(tpl))
        if not check.ok:
            raise ValueError(f"Publish blocked: missing evidence {check.missing}.")

        # adapter publish
        data = self._run_for_change(change_id)
        adapter = self.adapters.get(data["platform"])
        outcome = adapter.publish(
            data["platformAgentId"],
            request=PublishRequest(
                normalized=cdata["candidate"],
                remote=cdata["baseline"].remote,
                note="Published by PromptOps",
            ),
        )
        if not outcome.success:
            raise RuntimeError(f"Publish failed: {outcome.error}")

        # immutable production version
        version = AgentProfileVersion(
            id=gen_id("version"),
            agentId=cdata["baseline"].agentId,
            status=ProfileStatus.production,
            normalized=cdata["candidate"],
            remote=cdata["baseline"].remote,
            normalizedHash=content_hash(cdata["candidate"].model_dump()),
            remoteHash=cdata["baseline"].remoteHash,
            platformVersionId=outcome.platformVersionId,
            createdBy=publisher,
            createdAt=now(),
            changeId=change_id,
        )
        self.ws.db.save_version(version)

        result = PublishResult(
            id=gen_id("publish"),
            changeId=change_id,
            publisher=publisher,
            publishedAt=now(),
            productionVersionId=version.id,
            platformResponse=outcome.platformResponse,
        )
        self.ws.db.save_publish_result(result)
        self.ws.db.update_change_status(change_id, ChangeStatus.published)

        self.ledger.append(change_id, "step_completed", {"step": "publish", "publish_result_id": result.id})
        self.ws.registry.commit(f"publish: {change_id}")
        return result

    # ------------------------------------------------------------------
    # plan / advance / status
    # ------------------------------------------------------------------

    def plan(self, change_id: str) -> list[dict[str, Any]]:
        tpl = self._template(change_id)
        return plan_steps(tpl, self.ws, change_id)

    async def advance(self, change_id: str) -> list[str]:
        executed: list[str] = []
        while True:
            plan = self.plan(change_id)
            runnable = auto_runnable(plan)
            if not runnable:
                break
            step_entry = runnable[0]
            step_id = step_entry["id"]
            if step_id.startswith("connect"):
                # connect 不支持 re-advance
                break
            if step_id.startswith("baseline_eval"):
                # 需要 samples，不支持无参自动执行
                break
            if step_id.startswith("candidate_eval"):
                break
            if step_id.startswith("patch"):
                await self.optimize_patch(change_id)
            elif step_id.startswith("diff"):
                await self.diff(change_id)
            elif step_id.startswith("gate"):
                await self.gate(change_id)
            executed.append(step_id)
        return executed

    def status(self, change_id: str) -> dict[str, Any]:
        change = self.ws.db.get_change(change_id)
        plan = self.plan(change_id)
        return {
            "change": change.model_dump(),
            "plan": plan,
            "drift": self.ws.db.unaccepted_drift(change_id) is not None,
        }
