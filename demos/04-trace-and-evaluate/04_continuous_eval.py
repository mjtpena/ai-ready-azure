"""Continuous evaluation: score a sample of the production agent's real responses as they happen.

    python 04_continuous_eval.py            # create (or update) the rule hbl-ce-rule on FOUNDRY_AGENT_NAME
    python 04_continuous_eval.py --show     # print the rule
    python 04_continuous_eval.py --delete   # remove it

The rule points a Foundry evaluation (``hbl-continuous-safety``: violence and hate/unfairness checks; ``--with-quality`` adds task adherence) at the
``responseCompleted`` event of the agent, with a sampling rate and an hourly cap. Scores appear on the agent's Monitor
tab in the Foundry portal after a few turns of traffic (run ``../03-grounded-foundry-agent/03_chat.py`` to generate some).

Prerequisite: the project's managed identity holds the Foundry User role on the account (granted by
``infra/modules/foundry.bicep``). Preview API: the data source shape of the evaluation is the documented one for
continuous evaluation (``azure_ai_source``, scenario ``responses``); if the service rejects it, the error names the
expected shape and nothing else in this course depends on the rule.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import _shared  # noqa: F401
from azure.ai.projects.models import (
    ContinuousEvaluationRuleAction,
    EvaluationRule,
    EvaluationRuleEventType,
    EvaluationRuleFilter,
)
from foundry_util import agent_name, load_env, project_client

RULE_ID = "hbl-ce-rule"
EVAL_NAME = "hbl-continuous-safety"


def criteria(judge: str, with_quality: bool) -> list[dict]:
    """Safety checks need no judge model (the documented continuous-evaluation shape); the quality judges are optional."""
    out = [
        {"type": "azure_ai_evaluator", "name": "violence", "evaluator_name": "builtin.violence"},
        {"type": "azure_ai_evaluator", "name": "hate_unfairness", "evaluator_name": "builtin.hate_unfairness"},
    ]
    if with_quality:
        out.append({"type": "azure_ai_evaluator", "name": "task_adherence", "evaluator_name": "builtin.task_adherence",
                    "initialization_parameters": {"deployment_name": judge}})
    return out


def find_or_create_eval(oc, judge: str, with_quality: bool):
    name = EVAL_NAME + ("-quality" if with_quality else "")
    for ev in oc.evals.list(limit=100):
        if ev.name == name:
            return ev
    return oc.evals.create(
        name=name,
        data_source_config={"type": "azure_ai_source", "scenario": "responses"},
        testing_criteria=criteria(judge, with_quality),
        metadata={"agent": agent_name(), "purpose": "continuous evaluation"},
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sampling-rate", type=float, default=50.0, help="percentage of responses evaluated (default 50)")
    ap.add_argument("--max-hourly-runs", type=int, default=20)
    ap.add_argument("--with-quality", action="store_true", help="also score task adherence with the judge model")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--delete", action="store_true")
    args = ap.parse_args()
    load_env()
    judge = os.environ.get("FOUNDRY_EVAL_MODEL_NAME", os.environ.get("FOUNDRY_MODEL_NAME", "gpt-5"))
    with project_client() as client:
        if args.delete:
            client.evaluation_rules.delete(RULE_ID)
            print(f"deleted evaluation rule {RULE_ID}")
            return 0
        if args.show:
            rule = client.evaluation_rules.get(RULE_ID)
            print(json.dumps(rule.as_dict(), indent=2, default=str))
            return 0
        with client.get_openai_client() as oc:
            ev = find_or_create_eval(oc, judge, args.with_quality)
        rule = EvaluationRule(
            display_name="Harbourline advisor: continuous evaluation",
            description=f"Scores {args.sampling_rate:.0f}% of {agent_name()} responses (violence, hate/unfairness{', task adherence' if args.with_quality else ''}).",
            action=ContinuousEvaluationRuleAction(eval_id=ev.id, max_hourly_runs=args.max_hourly_runs, sampling_rate=args.sampling_rate),
            filter=EvaluationRuleFilter(agent_name=agent_name()),
            event_type=EvaluationRuleEventType.RESPONSE_COMPLETED,
            enabled=True,
        )
        created = client.evaluation_rules.create_or_update(RULE_ID, rule)
        print(f"Continuous evaluation rule {created.id} created for agent {agent_name()}: eval {ev.id} ({EVAL_NAME}), "
              f"{args.sampling_rate:.0f}% sampling, at most {args.max_hourly_runs} runs per hour.")
        print("Foundry portal > Build > Agents > the agent > Monitor shows the scores as traffic arrives.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
