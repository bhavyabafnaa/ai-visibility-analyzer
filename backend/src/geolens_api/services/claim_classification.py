import json
from json import JSONDecodeError
from typing import Any

from geolens_api.analysis.claims import (
    ClaimAssessment,
    ClaimClassification,
    ClaimSegment,
    EvidenceMatch,
)
from geolens_api.providers.contract import Provider, ProviderResponseStatus

_SYSTEM_INSTRUCTION = """\
Classify the factual claim against only the supplied evidence. Return one JSON object with:
- classification: supported, partially_supported, unsupported, contradicted, or unverifiable
- confidence: number from 0 to 1
- explanation: a concise evidence-grounded explanation

Use supported only when the evidence directly establishes the whole claim. Use
partially_supported when it establishes only part. Use unsupported when relevant evidence is
present but does not support the claim. Use contradicted only when evidence states an
incompatible fact. Use unverifiable when evidence is absent or insufficient. Do not add facts.
"""


class ProviderClaimClassifier:
    """Adapts a configured model provider to the isolated claim-classifier protocol."""

    def __init__(self, provider: Provider) -> None:
        self._provider = provider

    async def classify(
        self,
        claim: ClaimSegment,
        evidence: list[EvidenceMatch],
    ) -> ClaimAssessment:
        if not evidence:
            return self._fallback(
                "No relevant stored evidence was retrieved, so the claim is unverifiable."
            )
        payload = {
            "claim": claim.text,
            "evidence": [
                {
                    "reference": match.candidate.reference,
                    "text": match.candidate.text[:2000],
                }
                for match in evidence
            ],
        }
        result = await self._provider.execute(
            f"{_SYSTEM_INSTRUCTION}\nInput:\n{json.dumps(payload, ensure_ascii=False)}"
        )
        if result.status is not ProviderResponseStatus.SUCCEEDED:
            return self._fallback("The classifier provider did not return a successful response.")
        try:
            parsed = _first_json_object(result.response_text)
            classification = ClaimClassification(str(parsed["classification"]))
            confidence = float(parsed["confidence"])
            explanation = str(parsed["explanation"]).strip()
            if not 0 <= confidence <= 1 or not explanation:
                raise ValueError("invalid confidence or explanation")
        except (JSONDecodeError, KeyError, TypeError, ValueError):
            return self._fallback(
                "The classifier response was invalid, so the claim is unverifiable."
            )
        return ClaimAssessment(
            classification=classification,
            confidence=confidence,
            explanation=explanation,
            classifier=self._provider.name,
            model_identifier=self._provider.model_identifier,
        )

    def _fallback(self, explanation: str) -> ClaimAssessment:
        return ClaimAssessment(
            classification=ClaimClassification.UNVERIFIABLE,
            confidence=0,
            explanation=explanation,
            classifier=self._provider.name,
            model_identifier=self._provider.model_identifier,
        )


class UnconfiguredClaimClassifier:
    """Explicit result used when no model-assisted classifier was requested."""

    async def classify(
        self,
        claim: ClaimSegment,
        evidence: list[EvidenceMatch],
    ) -> ClaimAssessment:
        del claim, evidence
        return ClaimAssessment(
            classification=ClaimClassification.UNVERIFIABLE,
            confidence=0,
            explanation=(
                "No claim classifier provider was requested; the claim was not model-classified."
            ),
            classifier="not_configured",
            model_identifier=None,
        )


def _first_json_object(value: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    start = value.find("{")
    if start < 0:
        raise JSONDecodeError("No JSON object", value, 0)
    parsed, _ = decoder.raw_decode(value[start:])
    if not isinstance(parsed, dict):
        raise JSONDecodeError("Expected JSON object", value, start)
    return parsed
