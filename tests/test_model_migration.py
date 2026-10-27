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
