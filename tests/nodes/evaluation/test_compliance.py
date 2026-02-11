"""Tests for PolicyComplianceNode, MemoryPrivacyNode, and TurnAnnotationNode."""

import pytest
from orcheo.graph.state import State
from orcheo.nodes.evaluation.compliance import (
    MemoryPrivacyNode,
    PolicyComplianceNode,
    TurnAnnotationNode,
)


@pytest.mark.asyncio
async def test_policy_and_memory_privacy_nodes_apply_redactions() -> None:
    policy = PolicyComplianceNode(name="policy")
    policy_result = await policy.run(
        State(
            inputs={"content": "User email test@example.com contains ssn 123-45-6789"}
        ),
        {},
    )
    assert policy_result["violations"]
    assert "[REDACTED_EMAIL]" in policy_result["sanitized"]

    privacy = MemoryPrivacyNode(name="privacy", retention_count=1)
    history = [
        {"role": "user", "content": "My ssn is 123-45-6789", "metadata": {}},
        {"role": "assistant", "content": "Reply", "metadata": {}},
    ]
    privacy_result = await privacy.run(
        State(inputs={"conversation_history": history}), {}
    )
    assert privacy_result["redaction_count"] >= 1
    assert len(privacy_result["sanitized_history"]) == 1


@pytest.mark.asyncio
async def test_annotations_enrich_examples() -> None:
    annotator = TurnAnnotationNode(name="annotate")
    annotations = await annotator.run(
        State(
            inputs={"conversation_history": [{"role": "user", "content": "Thanks?"}]}
        ),
        {},
    )
    assert annotations["annotations"][0]["is_question"] is True
    assert annotations["annotations"][0]["sentiment"] == "positive"


@pytest.mark.asyncio
async def test_policy_compliance_handles_invalid_input_and_detects_violations() -> None:
    node = PolicyComplianceNode(name="policy")
    with pytest.raises(ValueError, match="expects content string"):
        await node.run(State(inputs={"content": 123}), {})

    result = await node.run(
        State(inputs={"content": "password 123-45-6789 contact test@example.com"}), {}
    )
    assert "blocked_term:password" in result["violations"]
    assert "pii:ssn_pattern" in result["violations"]
    assert "pii:email" in result["violations"]
    assert "[REDACTED_TERM]" in result["sanitized"]
    assert "[REDACTED_SSN]" in result["sanitized"]
    assert "[REDACTED_EMAIL]" in result["sanitized"]


def test_policy_compliance_detects_nothing_for_clean_content() -> None:
    node = PolicyComplianceNode(name="policy")
    assert node._detect_violations("Just chatting about cats", node.blocked_terms) == []


@pytest.mark.asyncio
async def test_policy_compliance_handles_string_blocked_terms_valid_json_list() -> None:
    node = PolicyComplianceNode(
        name="policy", blocked_terms='["secret", "confidential"]'
    )
    result = await node.run(
        State(inputs={"content": "This contains a secret message"}), {}
    )
    assert "blocked_term:secret" in result["violations"]
    assert "[REDACTED_TERM]" in result["sanitized"]


@pytest.mark.asyncio
async def test_policy_compliance_handles_string_blocked_terms_valid_json_non_list() -> (
    None
):
    node = PolicyComplianceNode(name="policy", blocked_terms='"forbidden"')
    result = await node.run(
        State(inputs={"content": "This contains forbidden content"}), {}
    )
    assert "blocked_term:forbidden" in result["violations"]
    assert "[REDACTED_TERM]" in result["sanitized"]


@pytest.mark.asyncio
async def test_policy_compliance_handles_string_blocked_terms_invalid_json() -> None:
    node = PolicyComplianceNode(name="policy", blocked_terms="invalid{json")
    result = await node.run(State(inputs={"content": "This contains invalid{json"}), {})
    assert "blocked_term:invalid{json" in result["violations"]
    assert "[REDACTED_TERM]" in result["sanitized"]


@pytest.mark.asyncio
async def test_memory_privacy_requires_list_and_handles_full_history() -> None:
    node = MemoryPrivacyNode(name="privacy")
    with pytest.raises(ValueError, match="expects a list for conversation_history"):
        await node.run(State(inputs={"conversation_history": "bad"}), {})

    history = [{"role": "user", "content": "Reach me at 1234567890", "metadata": {}}]
    result = await node.run(State(inputs={"conversation_history": history}), {})
    assert result["truncated"] is False
    assert result["redaction_count"] >= 1


@pytest.mark.asyncio
async def test_turn_annotation_requires_list_and_sentiment_variants() -> None:
    node = TurnAnnotationNode(name="annotate")
    with pytest.raises(ValueError, match="conversation_history list"):
        await node.run(State(inputs={"conversation_history": "bad"}), {})

    assert node._sentiment("This is terrible") == "negative"
    assert node._sentiment("Neutral text here") == "neutral"


@pytest.mark.asyncio
async def test_policy_compliance_handles_non_string_non_list_blocked_terms() -> None:
    """Test that blocked_terms defaults to empty list for invalid types like dict."""
    node = PolicyComplianceNode(name="policy")
    # Bypass Pydantic validation by directly setting blocked_terms to an invalid type
    node.blocked_terms = {"invalid": "type"}  # type: ignore[assignment]
    result = await node.run(
        State(inputs={"content": "This is clean content with password"}), {}
    )
    # Since blocked_terms becomes [], "password" is not in the blocked list
    assert "blocked_term:password" not in result["violations"]
    # Only PII patterns should be detected
    assert result["compliant"] is True
