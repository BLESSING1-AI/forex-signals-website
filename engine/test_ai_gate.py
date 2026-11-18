"""Unit tests for AI gate logic (no network)."""
import unittest
from ai_verifier import apply_ai_gate, _validate, _empty


class TestAIGate(unittest.TestCase):
    def test_approve_ok(self):
        setup = {"action": "signal", "tier": "A", "direction": "BUY", "score": 80}
        ai = {
            "decision": "APPROVE",
            "confidence": 80,
            "direction": "BUY",
            "ai_status": "ok",
            "confirmations": [],
            "warnings": [],
            "rejection_reasons": [],
            "explanation": "ok",
        }
        out = apply_ai_gate(setup, ai, strict=True)
        self.assertEqual(out["action"], "signal")

    def test_reject_strict(self):
        setup = {"action": "signal", "tier": "A", "direction": "SELL"}
        ai = _empty("REJECT", "late entry", 10)
        out = apply_ai_gate(setup, ai, strict=True)
        self.assertEqual(out["action"], "reject")

    def test_watch(self):
        setup = {"action": "signal", "tier": "A"}
        ai = {
            "decision": "WATCH",
            "confidence": 50,
            "ai_status": "ok",
            "confirmations": [],
            "warnings": [],
            "rejection_reasons": [],
            "explanation": "wait",
        }
        out = apply_ai_gate(setup, ai, strict=True)
        self.assertEqual(out["action"], "watchlist")

    def test_validate_requires_decision(self):
        setup = {"direction": "BUY"}
        self.assertIsNone(_validate({"confidence": 50}, setup))

    def test_validate_ok(self):
        setup = {"direction": "BUY"}
        obj = {
            "decision": "APPROVE",
            "confidence": 77,
            "direction": "BUY",
            "setup_quality": "high",
            "confirmations": ["H4"],
            "warnings": [],
            "rejection_reasons": [],
            "explanation": "aligned",
        }
        v = _validate(obj, setup)
        self.assertIsNotNone(v)
        self.assertEqual(v["decision"], "APPROVE")


if __name__ == "__main__":
    unittest.main()
