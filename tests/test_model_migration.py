from types import SimpleNamespace
from unittest.mock import Mock
from app.openai_client import OpenAIClient


def test_retired_fallback_uses_approved_model_without_changing_disabled_workflow():
    editor = OpenAIClient("offline-test", "gpt-5-mini", "gpt-4.1-nano", max_retries=1)
    editor.client = Mock()
    editor.client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="A factual short update."), finish_reason="stop")])
    assert editor._call_with_retry([], editor.fallback_model, max_tokens=2000)
    options = editor.client.chat.completions.create.call_args.kwargs
    assert options["model"] == "gpt-6-luna"
    assert options["max_completion_tokens"] == 2000
    assert options["reasoning_effort"] == "none"
    assert "temperature" not in options and "max_tokens" not in options
    assert "if: ${{ false }}" in open(".github/workflows/daily_digest.yml").read()


def test_observed_missing_detail_narration_is_not_eligible_for_output():
    from app.model_options import replacement_payload_problem
    assert replacement_payload_problem({"headline":"No Schedule Details Provided for NAHS Athletics", "body":"It does not provide a schedule."})
    assert replacement_payload_problem({"narration_text":"The supplied text asks a question but does not include an answer."})
    assert replacement_payload_problem({"headline":"Road reopened", "body":"Main Street reopened."}) is None


def test_luna_marked_email_article_refusal_returns_none():
    editor=OpenAIClient("offline-test", "gpt-5-mini", "gpt-6-luna", max_retries=1)
    editor.client=Mock()
    editor.client.chat.completions.create.return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="HEADLINE: No Conference Details Provided\n\nBODY: The submitted text does not include his response.\nSOURCE: Public source"),finish_reason="stop")])
    assert editor._call_with_retry([],"gpt-6-luna") is None
