"""
Parallel multi-provider document processor for concurrent VDR ingestion.

Two modes:
  1. ingest_batch  — full structured extraction from N documents, fanned across providers.
  2. targeted_search — ask one question across N documents concurrently (boolean/text/numeric).

Both stream progress events so the frontend can render live status.
"""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default per-task timeout (seconds) — prevents a single hung LLM call from freezing the batch
DEFAULT_TASK_TIMEOUT = 300  # 5 minutes


class ParallelDocProcessor:
    """Concurrent multi-provider document processor.

    Uses ModelRouter.get_available_providers() to fan work across providers
    with a semaphore to cap concurrent LLM calls.
    """

    def __init__(self, model_router: Any, max_concurrent: int = 10, task_timeout: int = DEFAULT_TASK_TIMEOUT):
        from app.services.model_router import ModelCapability
        self.router = model_router
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._ModelCapability = ModelCapability
        self._task_timeout = task_timeout

    # ------------------------------------------------------------------
    # Mode 1: Full extraction
    # ------------------------------------------------------------------

    async def ingest_batch(
        self,
        documents: List[Dict[str, Any]],
        extraction_schema: Optional[Dict] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Extract structured data from multiple documents concurrently.

        Args:
            documents: List of dicts with keys: doc_id, text, file_name, doc_type (optional).
            extraction_schema: Optional override schema; defaults per doc_type.

        Yields:
            Progress events: {type, completed, total, current_doc, provider, ...}
            Per-doc results: {type: "doc_extracted", doc_id, extracted_data, provider}
            Errors:          {type: "doc_error", doc_id, error}
            Final summary:   {type: "batch_complete", summary}
        """
        available = self.router.get_available_providers()
        if not available:
            # Fallback: try all providers — let the router handle failures
            available = ["anthropic"]
            logger.warning("[PARALLEL_DOC] No providers from get_available_providers, falling back to anthropic")

        total = len(documents)
        completed = 0
        results: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        yield {
            "type": "doc_processing_progress",
            "completed": 0,
            "total": total,
            "current_doc": documents[0]["file_name"] if documents else "",
            "provider": available[0] if available else "unknown",
            "stage": "starting",
        }

        # Create tasks — round-robin across available providers
        async def _extract_one(doc: Dict, provider: str) -> Dict[str, Any]:
            async with self._semaphore:
                return await self._extract_single(doc, provider, extraction_schema)

        tasks = []
        for i, doc in enumerate(documents):
            provider = available[i % len(available)]
            tasks.append((doc, provider, asyncio.ensure_future(
                _extract_one(doc, provider)
            )))

        # Yield results as they complete
        pending = {t[2] for t in tasks}
        task_to_doc = {t[2]: (t[0], t[1]) for t in tasks}

        while pending:
            try:
                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED, timeout=self._task_timeout
                )
            except Exception as e:
                logger.exception(f"[PARALLEL_DOC] asyncio.wait() failed: {e}")
                # Cancel remaining tasks and break
                for task in pending:
                    task.cancel()
                errors.append({"doc_id": "batch", "error": f"Wait loop error: {e}"})
                yield {"type": "doc_error", "doc_id": "batch", "error": f"Wait loop error: {e}"}
                break

            if not done:
                # Timeout — no tasks completed within the window
                logger.error(f"[PARALLEL_DOC] Timeout: {len(pending)} tasks still pending after {self._task_timeout}s")
                for task in pending:
                    doc_info, provider = task_to_doc.get(task, ({}, "unknown"))
                    task.cancel()
                    completed += 1
                    errors.append({
                        "doc_id": doc_info.get("doc_id", "unknown") if isinstance(doc_info, dict) else "unknown",
                        "error": f"Timed out after {self._task_timeout}s",
                    })
                    yield {
                        "type": "doc_error",
                        "doc_id": doc_info.get("doc_id", "unknown") if isinstance(doc_info, dict) else "unknown",
                        "file_name": doc_info.get("file_name", "") if isinstance(doc_info, dict) else "",
                        "error": f"Timed out after {self._task_timeout}s",
                    }
                pending = set()
                break

            for future in done:
                doc_info, provider = task_to_doc[future]
                completed += 1
                try:
                    result = future.result()
                    if result.get("error"):
                        errors.append({
                            "doc_id": doc_info.get("doc_id", "unknown"),
                            "file_name": doc_info.get("file_name", ""),
                            "error": result["error"],
                        })
                        yield {
                            "type": "doc_error",
                            "doc_id": doc_info.get("doc_id", "unknown"),
                            "file_name": doc_info.get("file_name", ""),
                            "error": result["error"],
                        }
                    else:
                        results.append(result)
                        yield {
                            "type": "doc_extracted",
                            "doc_id": doc_info.get("doc_id", "unknown"),
                            "file_name": doc_info.get("file_name", ""),
                            "extracted_data": result.get("extracted_data", {}),
                            "provider": provider,
                        }
                except Exception as e:
                    completed_err = str(e)
                    errors.append({
                        "doc_id": doc_info.get("doc_id", "unknown"),
                        "error": completed_err,
                    })
                    yield {
                        "type": "doc_error",
                        "doc_id": doc_info.get("doc_id", "unknown"),
                        "file_name": doc_info.get("file_name", ""),
                        "error": completed_err,
                    }

                # Progress update
                yield {
                    "type": "doc_processing_progress",
                    "completed": completed,
                    "total": total,
                    "current_doc": doc_info.get("file_name", ""),
                    "provider": provider,
                    "stage": "extracting" if completed < total else "complete",
                }

        # Final summary
        yield {
            "type": "batch_complete",
            "summary": {
                "total": total,
                "succeeded": len(results),
                "failed": len(errors),
                "providers_used": list(set(t[1] for t in tasks)),
                "errors": errors,
            },
        }

    async def _extract_single(
        self,
        doc: Dict[str, Any],
        provider: str,
        extraction_schema: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Extract structured data from a single document using a specific provider.

        Reuses the same prompt builders and schemas from document_process_service
        — legal clause extraction, signal extraction, memo extraction, etc. —
        but routes through the shared ModelRouter with provider-specific model
        selection for concurrent multi-provider fan-out.
        """
        from app.services.document_process_service import (
            LEGAL_DOC_TYPES,
            COMPANY_UPDATE_SIGNAL_SCHEMA,
            INVESTMENT_MEMO_SCHEMA,
            _get_legal_schema,
            _legal_extraction_prompt,
            _signal_first_prompt,
            _memo_prompt,
            _normalize_legal_extraction,
            _normalize_extraction,
            _extract_json_object,
            _empty_legal_extraction,
            _empty_signal_extraction,
            _empty_memo_extraction,
        )

        text = doc.get("text", "")
        doc_type = (doc.get("doc_type") or "contract").strip().lower()
        doc_id = doc.get("doc_id", "unknown")

        if not text:
            return {"doc_id": doc_id, "error": "No text content provided"}

        # Get provider-specific model for round-robin distribution
        model_info = self.router.get_model_for_provider(provider)
        preferred_models = [model_info["name"]] if model_info else None

        # Build extraction prompt using the SAME logic as
        # document_process_service._extract_document_structured_async
        if doc_type in LEGAL_DOC_TYPES:
            legal_schema = extraction_schema or _get_legal_schema(doc_type)
            schema_desc = json.dumps(legal_schema, indent=2)
            system_prompt, user_prompt = _legal_extraction_prompt(
                text, doc_type, schema_desc
            )
            empty = _empty_legal_extraction()
            max_tok = 8192
        elif doc_type == "investment_memo":
            memo_schema = extraction_schema or INVESTMENT_MEMO_SCHEMA
            schema_desc = json.dumps(memo_schema, indent=2)
            system_prompt, user_prompt = _memo_prompt(text, schema_desc)
            empty = _empty_memo_extraction()
            max_tok = 4096
        else:
            signal_schema = extraction_schema or COMPANY_UPDATE_SIGNAL_SCHEMA
            schema_desc = json.dumps(signal_schema, indent=2)
            system_prompt, user_prompt = _signal_first_prompt(
                text, doc_type, schema_desc, None
            )
            empty = _empty_signal_extraction()
            max_tok = 4096

        try:
            result = await self.router.get_completion(
                prompt=user_prompt,
                system_prompt=system_prompt,
                capability=self._ModelCapability.STRUCTURED,
                max_tokens=max_tok,
                temperature=0.2,
                json_mode=True,
                preferred_models=preferred_models,
                caller_context=f"parallel_doc_processor.extract:{doc_id}",
            )
            raw = (result.get("response") or "").strip()
            if not raw:
                return {"doc_id": doc_id, "error": "Empty LLM response"}

            parsed = _extract_json_object(raw)
            if isinstance(parsed, dict):
                if doc_type in LEGAL_DOC_TYPES:
                    parsed = _normalize_legal_extraction(parsed)
                else:
                    parsed = _normalize_extraction(parsed, document_type=doc_type)
                return {
                    "doc_id": doc_id,
                    "extracted_data": parsed,
                    "model_used": result.get("model_used", ""),
                }
            return {"doc_id": doc_id, "error": "Failed to parse JSON from LLM response"}
        except Exception as e:
            logger.exception(f"[PARALLEL_DOC] Extract failed for {doc_id}: {e}")
            return {"doc_id": doc_id, "error": str(e)}

    # ------------------------------------------------------------------
    # Mode 2: Targeted search across documents
    # ------------------------------------------------------------------

    async def targeted_search(
        self,
        documents: List[Dict[str, Any]],
        query: str,
        answer_type: str = "text",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Ask one question across N documents concurrently.

        Args:
            documents: List of dicts with keys: doc_id, text, file_name.
            query: The question to ask of every document.
            answer_type: "boolean" | "text" | "numeric"

        Yields:
            Progress events and per-doc answers with reasoning + source location.
        """
        available = self.router.get_available_providers()
        if not available:
            available = ["anthropic"]

        total = len(documents)
        completed = 0
        answers: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        yield {
            "type": "doc_processing_progress",
            "completed": 0,
            "total": total,
            "current_doc": "",
            "provider": "",
            "stage": "searching",
        }

        async def _search_one(doc: Dict, provider: str) -> Dict[str, Any]:
            async with self._semaphore:
                return await self._search_single(doc, query, answer_type, provider)

        tasks = []
        for i, doc in enumerate(documents):
            provider = available[i % len(available)]
            tasks.append((doc, provider, asyncio.ensure_future(
                _search_one(doc, provider)
            )))

        pending = {t[2] for t in tasks}
        task_to_doc = {t[2]: (t[0], t[1]) for t in tasks}

        while pending:
            try:
                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED, timeout=self._task_timeout
                )
            except Exception as e:
                logger.exception(f"[PARALLEL_DOC] asyncio.wait() failed in search: {e}")
                for task in pending:
                    task.cancel()
                errors.append({"doc_id": "batch", "error": f"Wait loop error: {e}"})
                yield {"type": "doc_error", "doc_id": "batch", "error": f"Wait loop error: {e}"}
                break

            if not done:
                # Timeout — cancel remaining
                logger.error(f"[PARALLEL_DOC] Search timeout: {len(pending)} tasks pending after {self._task_timeout}s")
                for task in pending:
                    doc_info, provider = task_to_doc.get(task, ({}, "unknown"))
                    task.cancel()
                    completed += 1
                    errors.append({
                        "doc_id": doc_info.get("doc_id", "unknown") if isinstance(doc_info, dict) else "unknown",
                        "error": f"Timed out after {self._task_timeout}s",
                    })
                    yield {
                        "type": "doc_error",
                        "doc_id": doc_info.get("doc_id", "unknown") if isinstance(doc_info, dict) else "unknown",
                        "file_name": doc_info.get("file_name", "") if isinstance(doc_info, dict) else "",
                        "error": f"Timed out after {self._task_timeout}s",
                    }
                pending = set()
                break

            for future in done:
                doc_info, provider = task_to_doc[future]
                completed += 1
                try:
                    result = future.result()
                    # Check for soft errors from _search_single
                    if result.get("error"):
                        errors.append({
                            "doc_id": doc_info.get("doc_id", "unknown"),
                            "file_name": doc_info.get("file_name", ""),
                            "error": result["error"],
                        })
                        yield {
                            "type": "doc_error",
                            "doc_id": doc_info.get("doc_id", "unknown"),
                            "file_name": doc_info.get("file_name", ""),
                            "error": result["error"],
                        }
                    else:
                        answers.append(result)
                        yield {
                            "type": "doc_search_result",
                            "doc_id": doc_info.get("doc_id", "unknown"),
                            "file_name": doc_info.get("file_name", ""),
                            "answer": result.get("answer"),
                            "reasoning": result.get("reasoning", ""),
                            "source_location": result.get("source_location", ""),
                            "provider": provider,
                        }
                except Exception as e:
                    errors.append({
                        "doc_id": doc_info.get("doc_id", "unknown"),
                        "error": str(e),
                    })
                    yield {
                        "type": "doc_error",
                        "doc_id": doc_info.get("doc_id", "unknown"),
                        "file_name": doc_info.get("file_name", ""),
                        "error": str(e),
                    }

                yield {
                    "type": "doc_processing_progress",
                    "completed": completed,
                    "total": total,
                    "current_doc": doc_info.get("file_name", ""),
                    "provider": provider,
                    "stage": "searching" if completed < total else "complete",
                }

        # Final summary with error aggregation
        yield {
            "type": "search_complete",
            "query": query,
            "answer_type": answer_type,
            "total_docs": total,
            "succeeded": len(answers),
            "failed": len(errors),
            "answers": answers,
            "errors": errors,
        }

    async def _search_single(
        self,
        doc: Dict[str, Any],
        query: str,
        answer_type: str,
        provider: str,
    ) -> Dict[str, Any]:
        """Ask a question of a single document using a specific provider."""
        from app.services.document_process_service import _extract_json_object

        text = doc.get("text", "")
        doc_id = doc.get("doc_id", "unknown")

        if not text:
            return {"doc_id": doc_id, "answer": None, "error": "No text content", "reasoning": "No text content", "source_location": ""}

        model_info = self.router.get_model_for_provider(provider)
        preferred_models = [model_info["name"]] if model_info else None

        # Build targeted search prompt
        type_instruction = {
            "boolean": 'Return answer as true or false (JSON boolean).',
            "numeric": 'Return answer as a number (JSON number). null if not found.',
            "text": 'Return answer as a string. null if not found.',
        }.get(answer_type, 'Return answer as a string. null if not found.')

        system_prompt = (
            "You are a legal document analyst. Answer the question about the document precisely. "
            "Return ONLY valid JSON with keys: answer, reasoning, source_location."
        )
        user_prompt = (
            f"Question: {query}\n\n"
            f"{type_instruction}\n\n"
            "Return JSON:\n"
            '{"answer": <your answer>, "reasoning": "<1-2 sentence explanation>", '
            '"source_location": "<section/clause/page where you found it>"}\n\n'
            f"Document text:\n---\n{text[:80000]}\n---"
        )

        try:
            result = await self.router.get_completion(
                prompt=user_prompt,
                system_prompt=system_prompt,
                capability=self._ModelCapability.STRUCTURED,
                max_tokens=1024,
                temperature=0.1,
                json_mode=True,
                preferred_models=preferred_models,
                caller_context=f"parallel_doc_processor.search:{doc_id}",
            )
            raw = (result.get("response") or "").strip()
            if not raw:
                return {"doc_id": doc_id, "answer": None, "error": "Empty LLM response", "reasoning": "Empty response", "source_location": ""}

            parsed = _extract_json_object(raw)
            if isinstance(parsed, dict):
                return {
                    "doc_id": doc_id,
                    "answer": parsed.get("answer"),
                    "reasoning": parsed.get("reasoning", ""),
                    "source_location": parsed.get("source_location", ""),
                }
            return {"doc_id": doc_id, "answer": None, "error": "Failed to parse JSON from LLM response", "reasoning": "Failed to parse response", "source_location": ""}
        except Exception as e:
            logger.exception(f"[PARALLEL_DOC] Search failed for {doc_id}: {e}")
            return {"doc_id": doc_id, "answer": None, "error": str(e), "reasoning": str(e), "source_location": ""}
