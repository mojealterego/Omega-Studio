import unittest
from omega_actions.ultimate.agent_dag import Task, PlanError, validate_plan

CAPS = frozenset({"read", "verify"})

class AgentDagTests(unittest.TestCase):
    def test_order_and_parallel_limit(self):
        p = validate_plan([Task("c", "verify", ("a", "b")), Task("b", "read"), Task("a", "read")], CAPS, max_parallel=1)
        self.assertEqual(p.levels, (("a",), ("b",), ("c",)))
        self.assertEqual(p.total_cost, 3)

    def test_parallel_wave(self):
        p = validate_plan([Task("a", "read"), Task("b", "read")], CAPS)
        self.assertEqual(p.levels, (("a", "b"),))

    def test_denied_capability(self):
        with self.assertRaises(PlanError):
            validate_plan([Task("x", "shell")], CAPS)

    def test_cycle(self):
        with self.assertRaises(PlanError):
            validate_plan([Task("a", "read", ("b",)), Task("b", "read", ("a",))], CAPS)

    def test_missing_dependency(self):
        with self.assertRaises(PlanError):
            validate_plan([Task("a", "read", ("unknown",))], CAPS)

    def test_duplicate_id(self):
        with self.assertRaises(PlanError):
            validate_plan([Task("a", "read"), Task("a", "read")], CAPS)

    def test_budget(self):
        with self.assertRaises(PlanError):
            validate_plan([Task("a", "read", estimated_cost=11)], CAPS, max_cost=10)

    def test_invalid_parallelism(self):
        with self.assertRaises(PlanError):
            validate_plan([Task("a", "read")], CAPS, max_parallel=0)

    def test_self_dependency(self):
        with self.assertRaises(PlanError):
            validate_plan([Task("a", "read", ("a",))], CAPS)

    def test_invalid_cost_bool(self):
        with self.assertRaises(PlanError):
            validate_plan([Task("a", "read", estimated_cost=True)], CAPS)
