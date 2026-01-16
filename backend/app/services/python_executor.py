"""Utility service for executing Python-based analytical scripts."""

from __future__ import annotations

import asyncio
import contextlib
import functools
import io
import logging
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.pwerm_service import pwerm_service
from app.services.valuation_engine_service import (
    Stage,
    ValuationEngineService,
    ValuationRequest,
)

logger = logging.getLogger(__name__)


class PythonExecutorService:
    """Execute vetted scripts and expose higher-level analytical helpers."""

    _DEFAULT_TIMEOUT = 45  # seconds

    def __init__(self, scripts_root: Optional[Path] = None) -> None:
        self._scripts_root = scripts_root or Path(__file__).resolve().parents[2]
        self._valuation_engine = ValuationEngineService()
        self._registered_scripts: Dict[str, str] = {
            "pwerm_analysis": "Probability-weighted valuation model",
            "crewai_agents": "CrewAI multi-agent orchestration pipeline",
            "market_search": "Market intelligence helper",
            "kyc_processor": "Compliance and KYC screening workflow",
            "scenario_analysis": "Scenario generation via valuation engine",
        }

    # ------------------------------------------------------------------
    # Generic script execution helpers
    # ------------------------------------------------------------------

    def _resolve_script_path(self, script_name: str) -> Optional[Path]:
        """Locate a script file under the allowed roots."""

        if not script_name:
            return None

        candidate_names = [script_name]
        if not script_name.endswith(".py"):
            candidate_names.append(f"{script_name}.py")

        search_roots = [
            self._scripts_root,
            self._scripts_root / "scripts",
            self._scripts_root / "analysis",
        ]

        for name in candidate_names:
            for root in search_roots:
                path = (root / name).resolve()
                try:
                    path.relative_to(self._scripts_root)
                except ValueError:
                    # Prevent escaping the scripts root
                    continue
                if path.exists() and path.is_file():
                    return path
        return None

    def _execute_file_sync(self, script_path: Path, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a script synchronously and capture stdout."""

        namespace: Dict[str, Any] = {"__name__": "__main__", "__file__": str(script_path)}
        buffer = io.StringIO()
        try:
            compiled = compile(script_path.read_text(), str(script_path), "exec")
            with contextlib.redirect_stdout(buffer):
                exec(compiled, namespace)
                if callable(namespace.get("main")):
                    result = namespace["main"](**arguments)
                elif callable(namespace.get("run")):
                    result = namespace["run"](**arguments)
                else:
                    result = namespace.get("RESULT")
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.exception("Script %s execution failed", script_path.name)
            return {
                "success": False,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "output": buffer.getvalue(),
            }

        return {
            "success": True,
            "output": buffer.getvalue(),
            "result": result,
        }

    async def execute_script(
        self,
        script_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run an arbitrary script if it is present on disk."""

        resolved = self._resolve_script_path(script_name)
        if not resolved:
            raise FileNotFoundError(f"Script '{script_name}' not found under {self._scripts_root}")

        loop = asyncio.get_running_loop()
        worker = functools.partial(self._execute_file_sync, resolved, arguments or {})
        exec_timeout = timeout or self._DEFAULT_TIMEOUT

        try:
            payload = await asyncio.wait_for(loop.run_in_executor(None, worker), exec_timeout)
        except asyncio.TimeoutError as exc:
            logger.warning("Script %s exceeded timeout (%ss)", script_name, exec_timeout)
            raise TimeoutError(f"Script '{script_name}' timed out after {exec_timeout}s") from exc

        return {"script": resolved.name, **payload}

    # ------------------------------------------------------------------
    # High-level analytical helpers
    # ------------------------------------------------------------------

    async def execute_pwerm_analysis(
        self,
        *,
        company_name: str,
        arr: Optional[float] = None,
        growth_rate: Optional[float] = None,
        scenarios: int = 499,
        sector: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Delegate PWERM analysis to the dedicated service."""

        result = await pwerm_service.analyze_company(
            company_name=company_name,
            arr=arr,
            growth_rate=growth_rate,
            sector=sector,
        )
        return {
            "success": True,
            "analysis": result,
            "scenarios_requested": scenarios,
        }

    async def execute_crew_agents(
        self,
        *,
        query: str,
        company_name: Optional[str] = None,
        analysis_type: str = "comprehensive",
    ) -> Dict[str, Any]:
        """Attempt to run CrewAI helpers if the script exists."""

        script_path = self._resolve_script_path("crewai_agents")
        if not script_path:
            logger.info("CrewAI script not present; returning informative response")
            return {
                "success": False,
                "message": "CrewAI agents script not configured in this environment.",
                "query": query,
                "company": company_name,
                "analysis_type": analysis_type,
            }

        return await self.execute_script(
            "crewai_agents",
            {
                "query": query,
                "company_name": company_name,
                "analysis_type": analysis_type,
            },
        )

    async def execute_market_search(
        self,
        *,
        query: str,
        deep_search: bool = True,
    ) -> Dict[str, Any]:
        """Run a market search helper script when available."""

        script_path = self._resolve_script_path("market_search")
        if not script_path:
            return {
                "success": False,
                "message": "Market search script not found; falling back to manual process.",
                "query": query,
                "deep_search": deep_search,
            }

        return await self.execute_script(
            "market_search",
            {
                "query": query,
                "deep_search": deep_search,
            },
        )

    async def execute_kyc_check(
        self,
        *,
        entity_name: str,
        check_type: str = "full",
    ) -> Dict[str, Any]:
        """Run KYC/compliance script if configured."""

        script_path = self._resolve_script_path("kyc_processor")
        if not script_path:
            return {
                "success": False,
                "message": "KYC processor script not available.",
                "entity": entity_name,
                "check_type": check_type,
            }

        return await self.execute_script(
            "kyc_processor",
            {
                "entity_name": entity_name,
                "check_type": check_type,
            },
        )

    # Scenario analysis -------------------------------------------------

    def _map_stage(self, stage_str: Optional[str]) -> Stage:
        if not stage_str:
            return Stage.SERIES_A
        normalized = stage_str.strip().lower()
        if "pre" in normalized and "seed" in normalized:
            return Stage.SEED
        if "seed" in normalized:
            return Stage.SEED
        if "series a" in normalized or normalized in {"a", "series_a"}:
            return Stage.SERIES_A
        if "series b" in normalized or normalized in {"b", "series_b"}:
            return Stage.SERIES_B
        if "series c" in normalized or normalized in {"c", "series_c"}:
            return Stage.SERIES_C
        if "series d" in normalized or "growth" in normalized:
            return Stage.GROWTH
        if "late" in normalized:
            return Stage.LATE
        if "public" in normalized:
            return Stage.PUBLIC
        return Stage.SERIES_A

    def _fallback_total_raised(self, stage: Stage) -> float:
        return {
            Stage.SEED: 5_000_000,
            Stage.SERIES_A: 15_000_000,
            Stage.SERIES_B: 40_000_000,
            Stage.SERIES_C: 75_000_000,
            Stage.GROWTH: 120_000_000,
            Stage.LATE: 200_000_000,
            Stage.PUBLIC: 250_000_000,
        }.get(stage, 20_000_000)

    async def execute_scenario_analysis(
        self,
        *,
        company_data: Dict[str, Any],
        num_scenarios: int = 100,
    ) -> Dict[str, Any]:
        """Use the valuation engine to build scenarios for a company."""

        company = company_data or {}

        stage = self._map_stage(
            company.get("stage")
            or company.get("funding_stage")
            or company.get("stage_name")
        )

        def _coerce_float(value: Any, fallback: float) -> float:
            try:
                return float(value)
            except (TypeError, ValueError):
                return fallback

        revenue = _coerce_float(
            company.get("revenue")
            or company.get("inferred_revenue"),
            10_000_000,
        )
        growth_rate = _coerce_float(
            company.get("growth_rate")
            or company.get("revenue_growth")
            or company.get("inferred_growth_rate"),
            0.5,
        )
        valuation = _coerce_float(
            company.get("valuation")
            or company.get("current_valuation")
            or company.get("inferred_valuation"),
            100_000_000,
        )
        total_raised = _coerce_float(
            company.get("total_funding")
            or company.get("total_raised")
            or company.get("inferred_total_funding"),
            self._fallback_total_raised(stage),
        )

        request_payload = ValuationRequest(
            company_name=company.get("company") or company.get("name") or "Unknown Company",
            stage=stage,
            revenue=revenue,
            growth_rate=growth_rate,
            last_round_valuation=valuation,
            total_raised=total_raised,
            business_model=company.get("business_model"),
            industry=company.get("sector") or company.get("industry"),
            category=company.get("category"),
            ai_component_percentage=company.get("ai_component_percentage")
            or company.get("ai_percentage"),
        )

        valuation_result = await self._valuation_engine.calculate_valuation(request_payload)
        scenarios = valuation_result.scenarios or []
        if not scenarios:
            return {
                "success": False,
                "message": "Valuation engine did not return scenarios",
            }

        payload = [
            {
                "scenario": s.scenario,
                "probability": s.probability,
                "exit_value": s.exit_value,
                "present_value": getattr(s, "present_value", None),
                "moic": getattr(s, "moic", None),
                "time_to_exit": s.time_to_exit,
                "funding_path": s.funding_path,
                "exit_type": s.exit_type,
            }
            for s in scenarios[:num_scenarios]
        ]

        expected_exit = sum(s.exit_value * s.probability for s in scenarios)
        expected_present = sum(
            getattr(s, "present_value", 0) * s.probability for s in scenarios
        )

        return {
            "success": True,
            "company": request_payload.company_name,
            "fair_value": valuation_result.fair_value,
            "method": valuation_result.method_used,
            "assumptions": valuation_result.assumptions,
            "expected_exit": expected_exit,
            "expected_present_value": expected_present,
            "scenarios": payload,
        }

    # ------------------------------------------------------------------

    def get_available_scripts(self) -> List[Dict[str, Any]]:
        """Describe the scripts and helpers exposed by this service."""

        scripts: List[Dict[str, Any]] = []
        for name, description in self._registered_scripts.items():
            path = self._resolve_script_path(name)
            scripts.append(
                {
                    "name": name,
                    "description": description,
                    "has_file": bool(path),
                    "path": str(path) if path else None,
                }
            )
        return scripts


python_executor = PythonExecutorService()


__all__ = ["python_executor", "PythonExecutorService"]

