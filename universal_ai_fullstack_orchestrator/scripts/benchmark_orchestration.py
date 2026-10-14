#!/usr/bin/env python3
"""Reproducible baseline for the orchestration engine with simulated providers (no network, no paid APIs).

Prints JSON. Numbers depend on the machine; compare runs only on the same host and Python version.
"""
import argparse, json, platform, shutil, statistics, sys, tempfile, time, tracemalloc
from pathlib import Path
from _bootstrap import ROOT
from pallaquino_cli.memory import MemoryStore
from pallaquino_cli.orchestration.models import new_id, new_task, utc_now
from pallaquino_cli.orchestration.planning import build_plan, validate_plan
from pallaquino_cli.orchestration.routing import select_agents
from pallaquino_cli.orchestration.scheduler import Scheduler
from pallaquino_cli.providers import MockProvider

REQUESTS = ["Agregar autenticación y gestión de roles a una aplicación Nuxt con PostgreSQL", "fix the crash in the invoice export",
            "add a database migration for orders", "Prepare the release changelog", "make the search page faster"]


def timed(fn, repeat):
    samples = []
    for _ in range(repeat):
        start = time.perf_counter(); fn(); samples.append((time.perf_counter() - start) * 1000)
    samples.sort()
    return {"runs": repeat, "median_ms": round(statistics.median(samples), 3), "p95_ms": round(samples[int(len(samples) * 0.95) - 1], 3), "max_ms": round(samples[-1], 3)}


def flat_plan(workspace, n):
    tasks = []
    for i in range(n):
        t = new_task(f"T{i + 1:03d}", f"task {i}", objective="bench", intent="FEATURE_IMPLEMENTATION", capabilities=["code"], domains=["api"],
                     executor={"kind": "agent"}, tools=["read_repository"], acceptance_criteria=["done"], risk="LOW", estimated_minutes=1)
        t.update(agent="backend_engineer", routing={"method": "bench"}, step=f"s{i}", review=False, idempotency_key=str(i), status="PLANNED"); tasks.append(t)
    plan = {"contract": "plan", "version": 1, "plan_id": new_id("plan"), "request_id": new_id("req"), "created_at": utc_now(), "request": "benchmark",
            "workspace": str(workspace), "intent": {"primary_intent": "FEATURE_IMPLEMENTATION", "risk": {"level": "LOW"}}, "tasks": tasks, "revisions": []}
    plan["validation"] = validate_plan(ROOT, plan); plan["status"] = "PLANNED"; return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0]); parser.add_argument("--quick", action="store_true", help="fewer repetitions"); a = parser.parse_args()
    reps = 5 if a.quick else 20; results = {"host": {"python": sys.version.split()[0], "platform": platform.platform(), "machine": platform.machine()}}
    results["planning"] = {req[:40]: timed(lambda r=req: build_plan(ROOT, r), reps) for req in REQUESTS}
    results["router"] = timed(lambda: select_agents(ROOT, capabilities=["design", "code", "test"], domains=["api"], technologies=["postgresql"], risk="HIGH"), reps * 10)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
        base = Path(temp); workspace = base / "ws"; shutil.copytree(ROOT / "evaluation/reference_scenario/fixture", workspace)
        store = MemoryStore(base / "memory.db", "bench")
        start = time.perf_counter()
        for i in range(1000): store.put_record("execution", "note", f"k{i}", {"text": f"record {i} about module {i % 50}"}, f"note {i} module {i % 50}", tags=["bench"])
        write_ms = (time.perf_counter() - start) * 1000
        results["memory"] = {"write_1000_records_ms": round(write_ms, 1), "per_record_ms": round(write_ms / 1000, 3),
                             "search_over_1000": timed(lambda: store.search("module 7", limit=10), reps), "bytes_on_disk": store.status()["bytes_on_disk"]}
        throughput = {}
        for workers in (1, 4, 8):
            plan = flat_plan(workspace, 100); store.save_plan(plan)
            scheduler = Scheduler(ROOT, store, workspace=workspace, providers={"mock": MockProvider(delay_seconds=0.01)}, settings={"max_workers": workers})
            eid = scheduler.create_execution(plan)["execution_id"]; start = time.perf_counter(); report = scheduler.run(eid); seconds = time.perf_counter() - start
            throughput[f"workers_{workers}"] = {"tasks": 100, "status": report["status"], "seconds": round(seconds, 3), "tasks_per_second": round(100 / seconds, 1),
                                                "note": "each simulated task sleeps 10 ms"}
        results["scheduler_throughput"] = throughput
        responses = json.loads((ROOT / "evaluation/reference_scenario/responses.json").read_text(encoding="utf-8"))
        outcomes = []; tracemalloc.start(); start = time.perf_counter(); runs = 3 if a.quick else 10
        for i in range(runs):
            ws = base / f"load{i}"; shutil.copytree(ROOT / "evaluation/reference_scenario/fixture", ws)
            plan = build_plan(ROOT, "add a multiply function to the calculator module with tests", workspace=ws); store.save_plan(plan)
            scheduler = Scheduler(ROOT, store, workspace=ws, providers={"mock": MockProvider(responses)})
            outcomes.append(scheduler.run(scheduler.create_execution(plan)["execution_id"])["status"])
        peak = tracemalloc.get_traced_memory()[1]; tracemalloc.stop()
        results["load_reference_scenario"] = {"executions": runs, "completed": outcomes.count("COMPLETED"), "completion_rate": outcomes.count("COMPLETED") / runs,
                                              "seconds": round(time.perf_counter() - start, 2), "peak_python_heap_mb": round(peak / 1e6, 2),
                                              "note": "includes a real unittest subprocess per execution"}
        plan = flat_plan(workspace, 50); store.save_plan(plan)
        scheduler = Scheduler(ROOT, store, workspace=workspace, providers={"mock": MockProvider()}); eid = scheduler.create_execution(plan)["execution_id"]
        for task in store.load_tasks(eid):
            task["history"].append({"from": "PLANNED", "to": "RUNNING", "at": utc_now(), "reason": "simulated crash"}); task["status"] = "RUNNING"; task["attempts"] = 1; store.save_task(eid, task)
        execution = store.load_execution(eid); execution["status"] = "RUNNING"; execution["runner"] = {"id": "dead", "pid": 0, "lease_expires": "2000-01-01T00:00:00+00:00"}; store.save_execution(execution)
        start = time.perf_counter(); report = scheduler.run(eid)
        results["crash_recovery"] = {"orphaned_tasks": 50, "status": report["status"], "reconciled_notes": len(report["reconciliation"]), "seconds": round(time.perf_counter() - start, 3)}
        store.close()
    print(json.dumps(results, indent=2))  # ASCII: portable across console encodings


if __name__ == "__main__":
    main()
