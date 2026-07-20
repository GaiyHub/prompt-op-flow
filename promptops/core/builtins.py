"""内置模板 + TemplateResolver。"""
from __future__ import annotations

from promptops.domain.models import PipelineTemplate, StepDef, StepType


# ---------------------------------------------------------------------------
# interactive-release：人工反馈 + 人工 patch + 人工 review + 人工 publish
# ---------------------------------------------------------------------------

INTERACTIVE_RELEASE = PipelineTemplate(
    id="interactive-release",
    version=1,
    description="人工反馈 + 人工 patch + 人工 review + 人工 publish",
    steps=[
        StepDef(
            id="connect",
            type=StepType.connect,
            depends=[],
            outputs=["baseline_version", "change"],
        ),
        StepDef(
            id="baseline_eval",
            type=StepType.eval,
            depends=["connect"],
            config={"role": "baseline"},
            outputs=["baseline_eval_run"],
        ),
        StepDef(
            id="feedback",
            type=StepType.feedback,
            depends=["baseline_eval"],
            outputs=["feedback_items"],
        ),
        StepDef(
            id="patch",
            type=StepType.patch,
            depends=["baseline_eval"],
            outputs=["patch_proposal", "candidate_version"],
        ),
        StepDef(
            id="candidate_eval",
            type=StepType.eval,
            depends=["patch"],
            config={"role": "candidate"},
            outputs=["candidate_eval_run"],
        ),
        StepDef(
            id="diff",
            type=StepType.diff,
            depends=["candidate_eval"],
            outputs=["semantic_diff"],
        ),
        StepDef(
            id="gate",
            type=StepType.gate,
            depends=["candidate_eval"],
            outputs=["gate_report"],
        ),
        StepDef(
            id="review",
            type=StepType.review,
            depends=["diff", "gate"],
            outputs=["review_decision"],
        ),
        StepDef(
            id="publish",
            type=StepType.publish,
            depends=["review"],
            outputs=["publish_result", "production_version"],
        ),
    ],
)


# ---------------------------------------------------------------------------
# ci-regression：全自动连续 patch + eval + gate + publish，无 review 步骤
# ---------------------------------------------------------------------------

CI_REGRESSION = PipelineTemplate(
    id="ci-regression",
    version=1,
    description="全自动连续 patch + eval + gate + publish，无 review 步骤",
    steps=[
        StepDef(
            id="connect",
            type=StepType.connect,
            depends=[],
            outputs=["baseline_version", "change"],
        ),
        StepDef(
            id="baseline_eval",
            type=StepType.eval,
            depends=["connect"],
            config={"role": "baseline"},
            outputs=["baseline_eval_run"],
        ),
        StepDef(
            id="patch",
            type=StepType.patch,
            depends=["baseline_eval"],
            implementation="rule-based",
            outputs=["patch_proposal", "candidate_version"],
        ),
        StepDef(
            id="candidate_eval",
            type=StepType.eval,
            depends=["patch"],
            config={"role": "candidate"},
            outputs=["candidate_eval_run"],
        ),
        StepDef(
            id="diff",
            type=StepType.diff,
            depends=["candidate_eval"],
            outputs=["semantic_diff"],
        ),
        StepDef(
            id="gate",
            type=StepType.gate,
            depends=["candidate_eval"],
            outputs=["gate_report"],
        ),
        StepDef(
            id="publish",
            type=StepType.publish,
            depends=["gate"],
            outputs=["publish_result", "production_version"],
        ),
    ],
)


BUILTIN_TEMPLATES: dict[str, PipelineTemplate] = {
    "interactive-release": INTERACTIVE_RELEASE,
    "ci-regression": CI_REGRESSION,
}
