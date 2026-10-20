import unittest

import app


class RoutingDecisionTests(unittest.TestCase):
    def test_none_from_router_is_handled(self):
        decision = app.normalize_routing_decision(None)
        self.assertEqual(decision.agents, [])
        self.assertIn("No routing decision", decision.reason)

    def test_dict_decision_is_accepted(self):
        decision = app.normalize_routing_decision({"agents": ["research"], "reason": "test"})
        self.assertEqual(decision.agents, ["research"])
        self.assertEqual(decision.reason, "test")


if __name__ == "__main__":
    unittest.main()
