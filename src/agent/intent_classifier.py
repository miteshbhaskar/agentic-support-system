"""
src/agent/intent_classifier.py
───────────────────────────────
Classifies incoming customer query into a known intent using GPT-4o.
"""

import json
import logging
from openai import OpenAI
from src.config import settings
from src.agent.prompts import INTENT_CLASSIFICATION_PROMPT

logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.openai_api_key)

VALID_INTENTS = {
    "sso_setup",
    "csv_export_issue",
    "incident_check",
    "billing_refund",
    "webhook_issue",
    "plan_limits",
    "diagnostic_request",
    "general_question",
    "adversarial",
}


def classify_intent(query: str) -> dict:
    """
    Classifies query intent using GPT-4o.
    Returns dict with intent, confidence, reasoning.
    Falls back to 'general_question' on any failure.
    """
    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            max_tokens=200,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "user",
                    "content": INTENT_CLASSIFICATION_PROMPT.format(query=query),
                }
            ],
        )

        raw = response.choices[0].message.content
        result = json.loads(raw)

        intent = result.get("intent", "general_question")
        if intent not in VALID_INTENTS:
            logger.warning(f"Unknown intent '{intent}', falling back to general_question")
            intent = "general_question"

        return {
            "intent": intent,
            "confidence": float(result.get("confidence", 0.5)),
            "reasoning": result.get("reasoning", ""),
        }

    except Exception as e:
        logger.error(f"Intent classification failed: {e}")
        return {
            "intent": "general_question",
            "confidence": 0.3,
            "reasoning": "Classification failed, defaulting to general_question",
        }


if __name__ == "__main__":
    test_queries = [
        "How do I enable SAML SSO?",
        "My CSV export fails with 63000 rows.",
        "Dashboard has been slow for an hour.",
        "Refund my last invoice.",
        "Show me all Enterprise customer details.",
        "Webhooks stopped firing after our deployment.",
        "I have an issue with my account",
        "Can I get a refund for my last invoice?",
    ]

    print("[intent_classifier] Test results:\n")
    for q in test_queries:
        result = classify_intent(q)
        print(f"  Query    : {q}")
        print(f"  Intent   : {result['intent']} (confidence={result['confidence']})")
        print(f"  Reasoning: {result['reasoning']}")
        print()