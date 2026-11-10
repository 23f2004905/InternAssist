import pytest

from services.gemini_retry import GenerationError, generate_with_fallback


class FakeAPIError(Exception):
    def __init__(self, code, status):
        super().__init__("sensitive provider message must not escape")
        self.code = code
        self.status = status


class Script:
    def __init__(self, outcomes):
        self.outcomes = {key: list(value) for key, value in outcomes.items()}
        self.calls = []

    def __call__(self, model):
        self.calls.append(model)
        outcome = self.outcomes[model].pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def run(script, fallback="fallback", sleeps=None):
    sleeps = [] if sleeps is None else sleeps
    result = generate_with_fallback(
        script, "primary", fallback, sleep=sleeps.append, jitter=0
    )
    return result


def test_primary_success_does_not_retry_or_fallback():
    script = Script({"primary": ["answer"]})
    sleeps = []
    assert run(script, sleeps=sleeps) == "answer"
    assert script.calls == ["primary"]
    assert sleeps == []


def test_timeout_retries_primary_once():
    script = Script({"primary": [TimeoutError(), "answer"]})
    sleeps = []
    assert run(script, sleeps=sleeps) == "answer"
    assert script.calls == ["primary", "primary"]
    assert sleeps == [1.0]


def test_503_retries_primary_then_succeeds():
    error = FakeAPIError(503, "UNAVAILABLE")
    script = Script({"primary": [error, "answer"]})
    sleeps = []
    assert run(script, sleeps=sleeps) == "answer"
    assert script.calls == ["primary", "primary"]
    assert sleeps == [1.0]


def test_fallback_success_after_primary_exhausted():
    error = FakeAPIError(503, "UNAVAILABLE")
    script = Script({"primary": [error, error], "fallback": ["fallback answer"]})
    assert run(script) == "fallback answer"
    assert script.calls == ["primary", "primary", "fallback"]


def test_total_failure_is_generic_and_bounded():
    error = FakeAPIError(504, "DEADLINE_EXCEEDED")
    script = Script({"primary": [error, error], "fallback": [error, error]})
    sleeps = []
    with pytest.raises(GenerationError) as captured:
        run(script, sleeps=sleeps)
    assert len(script.calls) == 4
    assert sleeps == pytest.approx([1.0, 1.0])
    assert "sensitive" not in str(captured.value)
    assert captured.value.__cause__ is None


@pytest.mark.parametrize("code,status", [
    (400, "INVALID_ARGUMENT"),
    (401, "UNAUTHENTICATED"),
    (403, "PERMISSION_DENIED"),
    (404, "NOT_FOUND"),
])
def test_permanent_errors_do_not_retry_or_fallback(code, status):
    script = Script({"primary": [FakeAPIError(code, status)], "fallback": ["unused"]})
    with pytest.raises(GenerationError):
        run(script)
    assert script.calls == ["primary"]


def test_same_fallback_model_is_not_called_twice():
    error = FakeAPIError(503, "UNAVAILABLE")
    script = Script({"primary": [error, error]})
    with pytest.raises(GenerationError):
        run(script, fallback="primary")
    assert script.calls == ["primary", "primary"]
