"""Provider selection, the strict-mode schema walk, and what the Groq adapter sends.

No network. The Groq client is faked; every assertion here is about the request
this app BUILDS, which is the part a real API call cannot check cheaply — a live
call tells you the model answered, not that `strict` was set.
"""

from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from backend.adapters import groq_provider as gp
from backend.adapters.groq_provider import GroqProvider, harden
from backend.adapters.llm_factory import create_llm_provider
from backend.adapters.prompts import (
    ClaimsResponse,
    EnhancedReasoning,
    PatternsResponse,
    ReflectionQuestion,
)
from backend.domain.filing import FilingSummary
from backend.domain.research import ResearchSummary
from backend.domain.verification import VerdictData

# Every schema the adapter can send. Strict mode rejects a schema that breaks any
# of its rules, so this list is what "the adapter cannot make an illegal request"
# is checked against.
ALL_SCHEMAS = [
    ClaimsResponse,
    VerdictData,
    ReflectionQuestion,
    EnhancedReasoning,
    ResearchSummary,
    FilingSummary,
    PatternsResponse,
]


# --- the factory --------------------------------------------------------------------


@pytest.fixture
def no_sdk_clients(monkeypatch):
    """Stop both adapters building real SDK clients — selection is what is under test."""
    from backend.adapters.gemini_provider import GeminiProvider

    monkeypatch.setattr(GeminiProvider, "__init__", lambda self: None)
    monkeypatch.setattr(GroqProvider, "__init__", lambda self: None)
    return GeminiProvider


def test_defaults_to_gemini_when_unset(monkeypatch, no_sdk_clients):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert isinstance(create_llm_provider(), no_sdk_clients)


def test_env_selects_groq(monkeypatch, no_sdk_clients):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    assert isinstance(create_llm_provider(), GroqProvider)


def test_env_selects_gemini_explicitly(monkeypatch, no_sdk_clients):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    assert isinstance(create_llm_provider(), no_sdk_clients)


@pytest.mark.parametrize("raw", ["  GROQ ", "Groq", "gROQ"])
def test_case_and_whitespace_tolerated(monkeypatch, no_sdk_clients, raw):
    """An env var pasted with a stray space must not change which provider runs."""
    monkeypatch.setenv("LLM_PROVIDER", raw)
    assert isinstance(create_llm_provider(), GroqProvider)


def test_empty_string_falls_back_to_default(monkeypatch, no_sdk_clients):
    """An exported-but-blank variable is 'unset', not an error."""
    monkeypatch.setenv("LLM_PROVIDER", "")
    assert isinstance(create_llm_provider(), no_sdk_clients)


@pytest.mark.parametrize("raw", ["grok", "openai", "gemeni", "claude"])
def test_unknown_provider_raises_rather_than_defaulting(monkeypatch, no_sdk_clients, raw):
    """⚠️ THE POINT: a typo must not silently run the app on the default provider."""
    monkeypatch.setenv("LLM_PROVIDER", raw)
    with pytest.raises(ValueError, match="not a provider"):
        create_llm_provider()


def test_error_names_the_bad_value_and_the_supported_ones(monkeypatch, no_sdk_clients):
    monkeypatch.setenv("LLM_PROVIDER", "grok")
    with pytest.raises(ValueError) as exc:
        create_llm_provider()
    assert "grok" in str(exc.value)
    assert "gemini" in str(exc.value) and "groq" in str(exc.value)


# --- the strict-mode schema walk ----------------------------------------------------


def walk_objects(node):
    """Yield every JSON-schema object node, including those inside $defs."""
    if isinstance(node, dict):
        if node.get("type") == "object":
            yield node
        for value in node.values():
            yield from walk_objects(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk_objects(item)


@pytest.mark.parametrize("schema", ALL_SCHEMAS, ids=lambda s: s.__name__)
def test_hardened_schema_satisfies_strict_mode(schema):
    """Groq strict mode: additionalProperties false, and every property required."""
    hardened = harden(schema.model_json_schema())

    objects = list(walk_objects(hardened))
    assert objects, f"{schema.__name__} produced no object nodes to check"

    for obj in objects:
        assert obj["additionalProperties"] is False
        if "properties" in obj:
            assert set(obj["required"]) == set(obj["properties"])


@pytest.mark.parametrize("schema", ALL_SCHEMAS, ids=lambda s: s.__name__)
def test_raw_pydantic_schema_would_be_rejected(schema):
    """The walk is not decoration: Pydantic's own output is missing what strict needs.

    Guards against someone "simplifying" harden() away on the grounds that
    Pydantic already emits a JSON schema. It does — just not a legal one here.
    """
    raw = schema.model_json_schema()
    assert any("additionalProperties" not in obj for obj in walk_objects(raw))


def test_nullable_fields_survive_being_forced_required():
    """⚠️ The migration hazard. ResearchSummary's optional fields must stay nullable.

    Strict mode has no notion of an optional field, so `harden` marks them
    required. That is only safe because `str | None` renders as a union WITH
    null — the model must emit the key, and null is still a legal value, which is
    the "the filing did not say" answer the field exists to carry. If the union
    were lost, forcing required would compel the model to invent prose.
    """
    hardened = harden(ResearchSummary.model_json_schema())
    props = hardened["properties"]

    for field in ("what_the_company_does", "how_it_makes_money"):
        types = {option.get("type") for option in props[field]["anyOf"]}
        assert "null" in types, f"{field} lost its null branch"

    assert set(hardened["required"]) == set(props)


def test_nested_defs_are_hardened():
    """FilingSummary nests NotableNumber via $defs — strict mode checks those too."""
    hardened = harden(FilingSummary.model_json_schema())
    notable = hardened["$defs"]["NotableNumber"]
    assert notable["additionalProperties"] is False
    assert set(notable["required"]) == {"figure", "what_it_measures"}


def test_harden_does_not_mutate_its_input():
    """Pydantic caches model_json_schema(); mutating it in place would poison it."""
    original = ClaimsResponse.model_json_schema()
    snapshot = repr(original)
    harden(original)
    assert repr(original) == snapshot


# --- what the adapter actually sends ------------------------------------------------


class FakeCompletions:
    def __init__(self, content: str):
        self._content = content
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self._content))]
        )


def build(content: str) -> tuple[GroqProvider, FakeCompletions]:
    provider = GroqProvider.__new__(GroqProvider)  # no SDK client, no API key
    fake = FakeCompletions(content)
    provider._client = SimpleNamespace(chat=SimpleNamespace(completions=fake))
    return provider, fake


CLAIMS_JSON = (
    '{"claims":[{"statement":"CUDA lock-in holds","proof_condition":"share stays >80%",'
    '"break_condition":"share falls below 60%","is_core":true}]}'
)


def test_extract_claims_decodes_into_domain_models():
    provider, _ = build(CLAIMS_JSON)
    claims = provider.extract_claims("NVDA", "cuda lock-in is real")
    assert len(claims) == 1
    assert claims[0].is_core is True
    assert claims[0].statement == "CUDA lock-in holds"


def test_request_demands_strict_schema_enforcement():
    """⚠️ Without strict:true this is best-effort JSON, which the app cannot rely on."""
    provider, fake = build(CLAIMS_JSON)
    provider.extract_claims("NVDA", "reasoning")

    schema_block = fake.kwargs["response_format"]["json_schema"]
    assert fake.kwargs["response_format"]["type"] == "json_schema"
    assert schema_block["strict"] is True
    assert schema_block["schema"]["additionalProperties"] is False


def test_request_uses_a_strict_capable_model():
    """Only the two gpt-oss models honour strict:true; a Llama model would not."""
    provider, fake = build(CLAIMS_JSON)
    provider.extract_claims("NVDA", "reasoning")
    assert fake.kwargs["model"] in ("openai/gpt-oss-20b", "openai/gpt-oss-120b")
    assert gp.MODEL_NAME in ("openai/gpt-oss-20b", "openai/gpt-oss-120b")


def test_reasoning_tokens_are_not_requested():
    """Billed as completion tokens against an 8K-per-minute ceiling, and unread."""
    provider, fake = build(CLAIMS_JSON)
    provider.extract_claims("NVDA", "reasoning")
    assert fake.kwargs["include_reasoning"] is False


def test_temperature_is_above_zero():
    """Groq coerces 0 to 1e-8; sending 0 would misreport what is actually used."""
    provider, fake = build(CLAIMS_JSON)
    provider.extract_claims("NVDA", "reasoning")
    assert fake.kwargs["temperature"] > 0


def test_truncated_response_raises_rather_than_half_parsing():
    """Hitting the token ceiling mid-object must fail the check, not save a fragment."""
    provider, _ = build('{"claims":[{"statement":"CUDA lock-in ho')
    with pytest.raises(Exception):
        provider.extract_claims("NVDA", "reasoning")


def test_verify_claim_decodes_a_verdict():
    provider, fake = build(
        '{"verdict":"contradicts","confidence":0.98,'
        '"evidence_quote":"margins fell to 61%","reasoning":"below the threshold"}'
    )
    verdict = provider.verify_claim("s", "p", "b", "doc text")
    assert verdict.verdict == "contradicts"
    assert verdict.confidence == 0.98
    assert "doc text" in fake.kwargs["messages"][0]["content"]


def test_generate_patterns_accepts_an_empty_list():
    """An empty list is the expected answer for most small sets, not a failure."""
    provider, _ = build('{"patterns":[]}')
    assert provider.generate_patterns([]) == []


def test_reflection_question_is_unwrapped_to_a_bare_string():
    provider, _ = build('{"question":"What made you confident margins would hold?"}')
    result = provider.generate_reflection_question("r", "s", "p", "b", ["a quote"])
    assert result == "What made you confident margins would hold?"
    assert isinstance(result, str)


def test_enhance_reasoning_is_unwrapped_to_a_bare_string():
    provider, _ = build('{"reasoning":"I think AWS keeps growing."}')
    assert provider.enhance_reasoning("AMZN", "amazon good") == "I think AWS keeps growing."


def test_summarise_company_accepts_nulls_for_uncovered_fields():
    """The null path the addendum exists to protect."""
    provider, _ = build(
        '{"what_the_company_does":"Designs chips.","how_it_makes_money":null,'
        '"key_risks":[]}'
    )
    summary = provider.summarise_company("NVDA", None, [], [])
    assert summary.how_it_makes_money is None
    assert summary.key_risks == []


def test_summarise_filing_decodes_nested_numbers():
    provider, _ = build(
        '{"filing_type_explained":"A quarterly report.","key_points":["Revenue rose."],'
        '"notable_numbers":[{"figure":"$26.0 billion","what_it_measures":"revenue"}],'
        '"relevant_claim_ids":[]}'
    )
    summary = provider.summarise_filing("NVDA", "10-Q", "Q2", [], [], [])
    assert summary.notable_numbers[0].figure == "$26.0 billion"
    assert summary.relevant_claim_ids == []


def test_absence_addendum_only_on_the_two_prompts_that_need_it():
    """It explains how to SPELL absence; prompts with no optional field must not get it."""
    provider, fake = build(CLAIMS_JSON)
    provider.extract_claims("NVDA", "reasoning")
    assert gp.ABSENCE_ADDENDUM not in fake.kwargs["messages"][0]["content"]

    provider, fake = build('{"what_the_company_does":null,"how_it_makes_money":null,"key_risks":[]}')
    provider.summarise_company("NVDA", None, [], [])
    assert gp.ABSENCE_ADDENDUM in fake.kwargs["messages"][0]["content"]


# --- the two adapters must stay on one set of prompts --------------------------------


def test_both_adapters_share_the_same_prompt_objects():
    """⚠️ Not equal strings — the SAME objects.

    The prompts carry the rules that stop the model inventing numbers and giving
    advice. Two copies would drift, and the copy that drifted would be whichever
    provider was not being tested that week.
    """
    from backend.adapters import gemini_provider as gem

    for name in (
        "EXTRACTION_PROMPT",
        "VERIFICATION_PROMPT",
        "REFLECTION_PROMPT",
        "PATTERNS_PROMPT",
        "ENHANCE_PROMPT",
        "RESEARCH_PROMPT",
        "FILING_PROMPT",
    ):
        assert getattr(gem, name) is getattr(gp, name), f"{name} has been forked"


def test_both_adapters_implement_the_whole_port():
    """A missing method would only surface when that one feature was used."""
    from backend.adapters.gemini_provider import GeminiProvider
    from backend.ports.llm_provider import LLMProvider

    required = {
        name
        for name, value in vars(LLMProvider).items()
        if getattr(value, "__isabstractmethod__", False)
    }
    assert required, "the port declared no abstract methods — has it changed shape?"

    for adapter in (GeminiProvider, GroqProvider):
        assert not required - set(dir(adapter))
        assert not getattr(adapter, "__abstractmethods__", set())


class _Unrelated(BaseModel):
    x: int


def test_harden_leaves_non_object_nodes_alone():
    hardened = harden(_Unrelated.model_json_schema())
    assert hardened["properties"]["x"]["type"] == "integer"
    assert "additionalProperties" not in hardened["properties"]["x"]
