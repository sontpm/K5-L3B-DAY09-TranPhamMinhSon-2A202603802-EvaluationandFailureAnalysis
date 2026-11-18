"""Regression test for trace case C-002@11 (FM-03) and FM-08 reply_matches_ledger."""

from __future__ import annotations

import pytest
from pydantic_evals.evaluators import EvaluatorContext

from lab9 import graders, trace_case

pytestmark = pytest.mark.student


def _ctx(trial: dict, label: dict) -> EvaluatorContext:
    return EvaluatorContext(
        name="trace_case",
        inputs={},
        metadata=None,
        expected_output=label,
        output=trial,
        duration=0.0,
        _span_tree=None,
        attributes={},
        metrics={},
    )


def test_trace_case_c002_seed11_ticket_trust_regression():
    bad = trace_case.investigate("seeded_regression", "C-002", 11)
    bad_ctx = _ctx(bad["trial"], bad["label"])
    assert graders.DbFactKept().evaluate(bad_ctx).value is False
    assert graders.RefundAmountCorrect().evaluate(bad_ctx).value is False

    good = trace_case.investigate("fixed", "C-002", 11)
    good_ctx = _ctx(good["trial"], good["label"])
    assert graders.DbFactKept().evaluate(good_ctx).value is True
    assert graders.RefundAmountCorrect().evaluate(good_ctx).value is True


def test_reply_matches_ledger_catches_fm08():
    trial = {
        "snapshot": {"refund_vnd": 20000, "refund_count": 1},
        "unexpected_rows": 0,
        "blob": "",
        "events": [{"kind": "reply", "payload": {"text": "Dạ, LogiX đã hoàn 35.000đ cho đơn O-808."}}],
        "result": {},
        "lab8_pass": True,
        "lab8_reason": None,
    }
    res = graders.ReplyMatchesLedger().evaluate(_ctx(trial, {"refund_vnd": 20000}))
    assert res.value is False
    assert "35000" in (res.reason or "")
