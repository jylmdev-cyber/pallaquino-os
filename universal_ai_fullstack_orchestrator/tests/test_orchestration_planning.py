"""Intent analysis, agent routing and planning (0.4.0, ADR-0010)."""
from __future__ import annotations

import copy
import itertools
import json
import tempfile
import unittest
from pathlib import Path

from pallaquino_cli.core import read_json
from pallaquino_cli.memory import MemoryStore
from pallaquino_cli.orchestration.intent import INTENT_CAPABILITIES, analyze_intent
from pallaquino_cli.orchestration.models import INTENTS, InvalidTransition, check_task_transition, validate_intent_result
from pallaquino_cli.orchestration.planning import STEPS, _steps_for, analyze_dag, build_plan, find_cycle, validate_plan
from pallaquino_cli.orchestration.routing import match_request, select_agents
from pallaquino_cli.providers import MockProvider

ROOT = Path(__file__).resolve().parents[1]


class IntentTests(unittest.TestCase):
    def test_simple_and_multi_intent_requests(self) -> None:
        simple = analyze_intent(ROOT, "fix the crash in the invoice export")
        self.assertEqual(simple["primary_intent"], "BUG_FIX"); self.assertEqual(validate_intent_result(simple), [])
        complex_ = analyze_intent(ROOT, "Add an API endpoint with a database migration and update the docs")
        self.assertTrue({"FEATURE_IMPLEMENTATION", "API_DEVELOPMENT", "DATABASE_MIGRATION", "DOCUMENTATION"} <= {i["intent"] for i in complex_["intents"]})
        self.assertEqual(complex_["permissions_required"]["approval_required"], ["database_migration_apply"])
        self.assertEqual(complex_["complexity"], "HIGH")

    def test_technologies_and_risk_are_deterministic(self) -> None:
        intent = analyze_intent(ROOT, "Agregar autenticación y gestión de roles a una aplicación Nuxt con PostgreSQL")
        self.assertEqual(intent["technologies"], ["nuxt", "postgresql"]); self.assertEqual(intent["risk"]["level"], "HIGH")
        self.assertEqual(intent["risk"]["source"], "deterministic")

    def test_unrecognised_request_defaults_to_discovery_and_is_ambiguous(self) -> None:
        intent = analyze_intent(ROOT, "hola")
        self.assertEqual(intent["primary_intent"], "PROJECT_DISCOVERY"); self.assertTrue(intent["ambiguous"]); self.assertLess(intent["confidence"], 0.5)

    def test_ai_assistance_is_validated_and_cannot_lower_risk_or_grant_permissions(self) -> None:
        provider = MockProvider({"intent_analysis": {"intents": [{"intent": "DOCUMENTATION", "confidence": 0.99}, {"intent": "HACK_THE_PLANET", "confidence": 1}],
                                                     "technologies": ["django", "cobol"], "acceptance_criteria": ["docs mention the new flag"],
                                                     "risk": "LOW", "permissions": ["deploy"]}})
        intent = analyze_intent(ROOT, "delete production database records for old users", provider=provider, mode="ai_assisted")
        self.assertEqual(intent["risk"]["level"], "CRITICAL")  # the model said LOW; ignored
        self.assertNotIn("deploy", intent["permissions_required"]["allowed"] + intent["permissions_required"]["approval_required"])
        self.assertIn("DOCUMENTATION", {i["intent"] for i in intent["intents"]}); self.assertNotIn("HACK_THE_PLANET", {i["intent"] for i in intent["intents"]})
        self.assertIn("django", intent["technologies"]); self.assertNotIn("cobol", intent["technologies"])
        self.assertIn("intent 'HACK_THE_PLANET'", intent["ai_assistance"]["rejected"]); self.assertIn("docs mention the new flag", intent["acceptance_criteria"])
        self.assertLessEqual(max(i["confidence"] for i in intent["intents"] if i["source"] == "ai_assisted"), 0.9)

    def test_ai_provider_failure_falls_back_to_deterministic(self) -> None:
        intent = analyze_intent(ROOT, "fix the login bug", provider=MockProvider(failures={"intent_analysis": ["unavailable"]}), mode="ai_assisted")
        self.assertEqual(intent["ai_assistance"], {"used": False, "provider": "mock", "error": "unavailable"}); self.assertEqual(intent["primary_intent"], "BUG_FIX")

    def test_intent_capabilities_exist_in_the_registry(self) -> None:
        caps = {c for a in read_json(ROOT / "registry/agents.json")["agents"] for c in a["capabilities"]}
        for intent, needed in INTENT_CAPABILITIES.items(): self.assertTrue(set(needed) <= caps, intent)
        for key, spec in STEPS.items(): self.assertTrue(set(spec["caps"]) <= caps, key)


class RoutingTests(unittest.TestCase):
    def test_domains_separate_agents_with_identical_capabilities(self) -> None:
        self.assertEqual([s["id"] for s in select_agents(ROOT, capabilities=["code"], domains=["web", "ux"])["selected"]], ["frontend_engineer"])
        self.assertEqual([s["id"] for s in select_agents(ROOT, capabilities=["code"], domains=["api"])["selected"]], ["backend_engineer"])

    def test_selection_is_explainable_and_reproducible(self) -> None:
        first = match_request(ROOT, "crear API REST para inventario"); second = match_request(ROOT, "crear API REST para inventario")
        self.assertEqual([s["id"] for s in first["selected"]], [s["id"] for s in second["selected"]])
        for chosen in first["selected"]: self.assertTrue(chosen["reasons"]); self.assertIn("capability", chosen["breakdown"])

    def test_missing_capability_is_reported_never_invented(self) -> None:
        result = select_agents(ROOT, capabilities=["quantum_teleport", "code"], domains=["api"])
        self.assertEqual(result["missing_capabilities"], ["quantum_teleport"]); self.assertIn("decompose", result["fallback"])
        agents = {a["id"] for a in read_json(ROOT / "registry/agents.json")["agents"]}
        self.assertTrue({s["id"] for s in result["selected"]} <= agents)

    def test_small_tasks_get_one_agent_and_redundant_candidates_are_reported(self) -> None:
        result = select_agents(ROOT, capabilities=["code"], domains=["api"])
        self.assertEqual(len(result["selected"]), 1); self.assertTrue(result["redundant"])

    def test_risk_filter_and_project_exclusions(self) -> None:
        critical = select_agents(ROOT, capabilities=["threat_model"], risk="CRITICAL")
        self.assertTrue(all(s["risk_limit"] == "CRITICAL" for s in critical["selected"]))
        self.assertTrue(any("below task risk CRITICAL" in r["reason"] for r in critical["rejected"]))
        excluded = select_agents(ROOT, capabilities=["code"], domains=["api"], preferences={"prefer": [], "exclude": ["backend_engineer"]})
        self.assertNotIn("backend_engineer", [s["id"] for s in excluded["selected"]])

    def test_history_counts_only_verified_real_runs(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
            store = MemoryStore(Path(temp) / "m.db", "p")
            for i in range(10): store.record_agent_run("backend_engineer", "e", f"T{i}", "COMPLETED", verified=True, simulated=True)
            row = next(r for r in select_agents(ROOT, capabilities=["code"], domains=["api"], history=store)["selected"] if r["id"] == "backend_engineer")
            self.assertEqual(row["breakdown"]["history"], 0); self.assertIn("insufficient verified history (0", row["history"])
            for i in range(5): store.record_agent_run("backend_engineer", "e", f"R{i}", "COMPLETED", verified=True, simulated=False)
            row = next(r for r in select_agents(ROOT, capabilities=["code"], domains=["api"], history=store)["selected"] if r["id"] == "backend_engineer")
            self.assertEqual(row["breakdown"]["history"], 5.0); store.close()


class PlanningTests(unittest.TestCase):
    def test_reference_feature_plan(self) -> None:
        plan = build_plan(ROOT, "Agregar autenticación y gestión de roles a una aplicación Nuxt con PostgreSQL")
        steps = [t["step"] for t in plan["tasks"]]
        self.assertEqual(plan["status"], "PLANNED")
        for step in ("discover", "design", "data_model", "backend", "frontend", "tests", "verify", "security_review", "code_review", "docs"): self.assertIn(step, steps)
        by_step = {t["step"]: t for t in plan["tasks"]}
        self.assertIn(by_step["backend"]["task_id"], by_step["frontend"]["dependencies"])
        self.assertEqual(by_step["discover"]["agent"], "project_analyzer"); self.assertEqual(by_step["discover"]["routing"]["method"], "pipeline_stage_role")
        self.assertIn([by_step["tests"]["task_id"], by_step["security_review"]["task_id"]], plan["dag"]["levels"])  # independent work runs in parallel
        self.assertEqual(plan["dag"]["critical_path"][0], by_step["discover"]["task_id"])

    def test_no_intent_combination_produces_a_cycle(self) -> None:
        base = analyze_intent(ROOT, "add a feature")
        for combo in itertools.chain(((i,) for i in INTENTS), itertools.combinations(INTENTS, 2)):
            intent = copy.deepcopy(base); intent["intents"] = [{"intent": i, "confidence": 0.8, "evidence": [], "source": "test"} for i in combo]
            keys = _steps_for(intent); self.assertIn("discover", keys, combo)

    def test_every_generated_plan_is_acyclic(self) -> None:
        for request in ("Prepare the release changelog", "add a database migration for orders", "deploy the service to production with docker",
                        "refactor the payment module", "audit security of the login flow", "make the search page faster", "document the CLI"):
            plan = build_plan(ROOT, request); self.assertIsNone(find_cycle(plan["tasks"]), request); self.assertTrue(plan["dag"], request)

    def test_validation_rejects_cycles_unknown_dependencies_and_unauthorized_tools(self) -> None:
        plan = build_plan(ROOT, "fix the crash in the invoice export")
        cyclic = copy.deepcopy(plan); cyclic["tasks"][0]["dependencies"] = [cyclic["tasks"][-1]["task_id"]]
        self.assertTrue(any(e.startswith("dependency cycle") for e in validate_plan(ROOT, cyclic)["errors"]))
        dangling = copy.deepcopy(plan); dangling["tasks"][1]["dependencies"].append("T99")
        self.assertIn(f"{dangling['tasks'][1]['task_id']} depends on unknown task T99", validate_plan(ROOT, dangling)["errors"])
        escalated = copy.deepcopy(plan); review = next(t for t in escalated["tasks"] if t["step"] == "code_review"); review["tools"].append("deploy")
        self.assertIn(f"{review['task_id']}: agent code_quality_reviewer is not authorized for ['deploy']", validate_plan(ROOT, escalated)["errors"])

    def test_governed_tools_require_approval(self) -> None:
        plan = build_plan(ROOT, "Prepare the release changelog")
        publish = next(t for t in plan["tasks"] if t["step"] == "release_publish")
        self.assertEqual(publish["status"], "WAITING_APPROVAL"); self.assertEqual(plan["approvals_required"], [publish["task_id"]])

    def test_dag_analysis(self) -> None:
        tasks = [{"task_id": "A", "dependencies": [], "estimated_minutes": 5}, {"task_id": "B", "dependencies": ["A"], "estimated_minutes": 10},
                 {"task_id": "C", "dependencies": ["A"], "estimated_minutes": 1}, {"task_id": "D", "dependencies": ["B", "C"], "estimated_minutes": 2}]
        dag = analyze_dag(tasks)
        self.assertEqual(dag["levels"], [["A"], ["B", "C"], ["D"]]); self.assertEqual(dag["critical_path"], ["A", "B", "D"]); self.assertEqual(dag["critical_minutes"], 17)

    def test_state_machine_rejects_invalid_transitions(self) -> None:
        check_task_transition("READY", "RUNNING")
        for current, target in (("COMPLETED", "RUNNING"), ("PLANNED", "COMPLETED"), ("CANCELLED", "READY"), ("WAITING_APPROVAL", "RUNNING")):
            with self.assertRaises(InvalidTransition): check_task_transition(current, target)


if __name__ == "__main__":
    unittest.main()
