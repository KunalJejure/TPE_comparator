from __future__ import annotations

"""Semantic diff via local Ollama LLM (through langchain_ollama)."""

import logging
from typing import Optional


logger = logging.getLogger(__name__)


def semantic_diff(
    text1: str,
    text2: str,
    *,
    ollama_host: str = "localhost:11434",
    model: str = "llama2",
) -> str:
    """Use a local Ollama model to semantically compare two text extracts.

    The prompt is tailored for QA engineers doing software validation.

    Args:
        text1: Extract from the original PDF.
        text2: Extract from the revised PDF.
        ollama_host: Host:port of the Ollama HTTP server.
        model: Model name registered with Ollama.

    Returns:
        String with LLM response; typically JSON per instructions.
    """
    # Truncate to stay within a safe context size for typical local models.
    max_chars = 3000
    truncated_text1 = text1[:max_chars]
    truncated_text2 = text2[:max_chars]

    prompt = (
        "As QA expert, analyze doc changes for software validation.\n\n"
        "Compare these PDF extracts and identify key changes:\n\n"
        f"Original:\n{truncated_text1}\n\n"
        f"Revised:\n{truncated_text2}\n\n"
        "For each change, specify:\n"
        "- type: insert | delete | move | modify\n"
        "- brief_text: short excerpt illustrating the change\n"
        "- impact_score: 1-5 (1 = low impact, 5 = critical)\n\n"
        "Return JSON ONLY in the following shape:\n"
        "{\n"
        '  "similarity": <number between 0 and 1>,\n'
        '  "changes": [\n'
        '    {"page": 1, "type": "insert", "text": "New bug fix", "impact_score": 3}\n'
        "  ]\n"
        "}\n"
    )

    try:
        from langchain_ollama import OllamaLLM  # type: ignore[import]

        llm = OllamaLLM(model=model, base_url=f"http://{ollama_host}")
        logger.info("Calling Ollama LLM at %s with model %s", ollama_host, model)
        response: str = llm.invoke(prompt)
        logger.info("Received semantic diff response from LLM")
        return response
    except ImportError:
        logger.warning(
            "langchain_ollama not installed; semantic analysis is unavailable."
        )
        return "Semantic analysis unavailable: install `langchain-ollama` and ensure Ollama is running."
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Semantic diff via Ollama failed.")
        return f"Error during semantic analysis: {exc}"

