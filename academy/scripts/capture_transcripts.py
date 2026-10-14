#!/usr/bin/env python3
"""Capture real CLI transcripts for the academy's terminal simulator and tutorials.

    python academy/scripts/capture_transcripts.py

Clones the current repository (HEAD) into a temporary directory, exactly as a new user would get it, and runs a fixed list of
read-only or self-contained commands there. Host-specific paths are replaced with neutral placeholders and the result goes to
`src/data/transcripts.json` together with the date and platform of the capture. The simulator labels every output as a recorded
simulation. Nothing runs outside the temporary clone, and the temporary clone is deleted afterwards.
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ACADEMY = Path(__file__).resolve().parents[1]
REPO = ACADEMY.parent
OUT = ACADEMY / "src" / "data" / "transcripts.json"
MAX_LINES = 60
SAMPLE_REQUEST = "Analiza el repositorio actual, identifica problemas de calidad, revisa el estado de Git y genera un informe técnico"

# (id, arguments after `python -m pallaquino_cli`, working directory label, note shown by the simulator)
COMMANDS = [
    ("version", ["--version"], "framework", "Versión instalada."),
    ("help", ["--help"], "framework", "Lista de comandos disponibles."),
    ("doctor", ["doctor"], "framework", "Diagnóstico completo de un clon recién descargado, sin la identidad Git del proyecto."),
    ("validate-json", ["validate", "--json"], "framework", "Todas las validaciones, incluida la identidad Git (de entorno)."),
    ("validate-integrity", ["validate", "--integrity-only", "--json"], "framework", "Solo validaciones de contenido, independientes del equipo."),
    ("identity", ["identity", "--json"], "framework", "Identidad de commits esperada y la configurada en este clon."),
    ("analyze", ["analyze"], "framework", "Mapa del repositorio actual (escribe repository/REPOSITORY_MAP.*)."),
    ("risk", ["risk", "agregar autenticación basada en roles", "--json"], "framework", "Clasificación determinista del riesgo de una solicitud."),
    ("risk-critical", ["risk", "borrar la base de datos de producción", "--json"], "framework", "Una solicitud crítica exige aprobación humana."),
    ("agents-match", ["agents", "match", "agregar autenticación basada en roles", "--json"], "framework", "Agentes que el router propone para la solicitud."),
    ("stack", ["stack", "--json"], "framework", "Frescura del snapshot de versiones verificado."),
    ("status", ["status", "--json"], "framework", "Estado del pipeline y locks."),
    ("init-dry-run", ["init", "--target", "../mi-proyecto", "--dry-run", "--json"], "framework", "Simulación de instalación en un proyecto: no escribe nada."),
    ("tools-list", ["tools", "list", "--no-plugins"], "framework", "Herramientas registradas (builtin; plugins y MCP solo si se configuran)."),
    ("tools-check-write", ["tools", "check", "core.files.write", "--no-plugins", "--args", "{\"path\": \"a.txt\", \"content\": \"x\"}", "--json"], "framework",
     "Comprobación en seco: una escritura sin grant queda denegada."),
    ("security-audit", ["security", "audit", "--target", "..", "--json"], "framework", "Escaneo de secretos de solo lectura del repositorio."),
    ("plan", ["plan", SAMPLE_REQUEST, "--json"], "framework", "Plan (DAG) validado para una solicitud; no ejecuta nada."),
]


PROJECT_REQUEST = "add a multiply function to the calculator module with tests"

# The real-project walkthrough: the reference fixture (a small Python calculator with unittest tests) copied next to the clone,
# initialized with `init`, then planned and executed from its `.pallaquino` directory. `{plan}` and `{execution}` are filled in
# from the previous outputs.
PROJECT_COMMANDS = [
    ("project-init", ["init", "--target", "../calc", "--json"], "framework", "Instala el framework en el proyecto de ejemplo."),
    ("project-plan", ["plan", PROJECT_REQUEST, "--workspace", "..", "--json"], "project", "Plan validado para el proyecto; no ejecuta nada."),
    ("project-dry-run", ["run", "--plan", "{plan}", "--dry-run", "--json"], "project", "Qué se ejecutaría, sin ejecutarlo."),
    ("project-run", ["run", "--plan", "{plan}", "--json"], "project", "Ejecución real con el proveedor mock: las tareas de agente quedan simulated."),
    ("project-status", ["status", "--execution", "{execution}", "--json"], "project", "Estado y métricas de la ejecución."),
    ("project-report", ["executions", "report", "{execution}", "--json"], "project", "Informe de solicitud a resultado."),
    ("project-memory", ["memory", "search", "tests", "--json"], "project", "Memoria del proyecto tras la ejecución (datos no confiables)."),
]


def sanitize(text: str, clone: Path, project: Path | None = None) -> str:
    places = ([(project, "<ruta>/pallaquino-os/calc")] if project else []) + [(clone, "<ruta>/pallaquino-os")]
    for place, label in places:
        variants = {str(place), str(place).replace("\\", "/"), str(place).replace("\\", "\\\\")}
        for variant in sorted(variants, key=len, reverse=True): text = text.replace(variant, label)
    home = str(Path.home())
    for variant in {home, home.replace("\\", "/"), home.replace("\\", "\\\\")}: text = text.replace(variant, "<home>")
    text = re.sub(r"[A-Za-z]:\\\\[^\"\s]*Temp[^\"\s]*", "<tmp>", text)
    # Windows separators inside placeholder paths become "/" so outputs read the same on every platform.
    text = re.sub(r"(<ruta>/pallaquino-os|<home>)((?:\\\\|\\|/)[^\"\s,]*)", lambda m: m.group(1) + m.group(2).replace("\\\\", "/").replace("\\", "/"), text)
    text = re.sub(r"(execution|exec|plan|req|call|grant|appr)-[0-9a-f]{12}", r"\1-xxxxxxxxxxxx", text)
    text = re.sub(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:\+00:00|Z)?", "2026-10-14T00:00:00+00:00", text)
    return text


def os_label() -> str:
    """Readable OS name. On Windows 11, platform.release() still reports "10"; the build number (22000+) tells them apart."""
    if platform.system() == "Windows":
        build = int(platform.version().split(".")[-1] or 0)
        return "Windows 11" if build >= 22000 else f"Windows {platform.release()}"
    return f"{platform.system()} {platform.release()}"


def capture_project(clone: Path, framework: Path, env: dict[str, str]) -> list[dict]:
    project = clone / "calc"  # `../calc` seen from the framework directory, as in the lesson
    shutil.copytree(framework / "evaluation" / "reference_scenario" / "fixture", project)
    ids: dict[str, str] = {}
    records = []
    for cid, args, cwd_label, note in PROJECT_COMMANDS:
        args = [a.format(**ids) if a in ("{plan}", "{execution}") else a for a in args]
        cwd = framework if cwd_label == "framework" else project / ".pallaquino"
        run_env = env if cwd_label == "framework" else {**env, "PYTHONPATH": str(cwd)}
        proc = subprocess.run([sys.executable, "-m", "pallaquino_cli", *args], cwd=cwd, env=run_env, capture_output=True, text=True, encoding="utf-8")
        if cid == "project-plan": ids["plan"] = json.loads(proc.stdout)["plan_id"]
        if cid == "project-run": ids["execution"] = json.loads(proc.stdout)["execution_id"]
        output = sanitize((proc.stdout + proc.stderr).rstrip(), clone, project)
        lines = output.splitlines(); truncated = len(lines) > MAX_LINES * 2
        shown = [re.sub(r"(plan|exec)-[0-9a-f]{12}", r"\1-xxxxxxxxxxxx", a) for a in args]
        quoted = [f"'{a}'" if '"' in a else f'"{a}"' if " " in a else a for a in shown]
        records.append({"id": cid, "command": "python -m pallaquino_cli " + " ".join(quoted), "cwd": cwd_label, "exit_code": proc.returncode,
                        "note": note, "output": "\n".join(lines[:MAX_LINES * 2]) + ("\n…" if truncated else ""), "truncated": truncated})
    return records


def main() -> int:
    temp = Path(tempfile.mkdtemp(prefix="pq-academy-"))
    clone = temp / "pallaquino-os"
    try:
        subprocess.run(["git", "-c", "core.longpaths=true", "clone", "-q", str(REPO), str(clone)], check=True)
        framework = clone / "universal_ai_fullstack_orchestrator"
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONPATH": str(framework)}
        env.pop("PALLAQUINO_ROOT", None)
        records = []
        for cid, args, cwd_label, note in COMMANDS:
            proc = subprocess.run([sys.executable, "-m", "pallaquino_cli", *args], cwd=framework, env=env, capture_output=True, text=True, encoding="utf-8")
            output = sanitize((proc.stdout + proc.stderr).rstrip(), clone)
            lines = output.splitlines(); truncated = len(lines) > MAX_LINES
            if cid == "plan":  # keep the full plan for the DAG walkthrough, a short excerpt for the terminal
                plan = json.loads(proc.stdout)
                (ACADEMY / "src" / "data" / "plan_example.json").write_text(json.dumps({
                    "request": plan["request"], "status": plan["status"], "primary_intent": plan["intent"]["primary_intent"], "risk": plan["intent"]["risk"]["level"],
                    "dag": plan["dag"], "warnings": plan["validation"]["warnings"],
                    "tasks": [{"task_id": t["task_id"], "step": t["step"], "title": t["title"], "agent": t["agent"], "executor": t["executor"]["kind"],
                               "dependencies": t["dependencies"], "tools": [r.get("tool_id") for r in t["executor"].get("resolved", [])] or None,
                               "permissions": t["permissions"], "status": t["status"]} for t in plan["tasks"]]}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
            quoted = [f"'{a}'" if '"' in a else f'"{a}"' if " " in a else a for a in args]  # as a user would type it in a POSIX shell
            records.append({"id": cid, "command": "python -m pallaquino_cli " + " ".join(quoted),
                            "cwd": cwd_label, "exit_code": proc.returncode, "note": note, "output": "\n".join(lines[:MAX_LINES]) + ("\n…" if truncated else ""),
                            "truncated": truncated})
        project = capture_project(clone, framework, env)
        payload = {"captured_on": date.today().isoformat(), "platform": f"{os_label()}, Python {platform.python_version()}",
                   "source": "git clone of this repository; outputs recorded, then sanitized", "commands": records, "project": project}
        OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print(f"captured {len(records)} transcripts -> {OUT.relative_to(REPO)}")
        return 0
    finally:
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
