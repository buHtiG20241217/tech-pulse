import pytest

from autosar_hld_assistant.app.core.config import LLMSettings
from autosar_hld_assistant.app.core.llm import LLMClient, LLMNotConfigured, parse_json_reply


def test_mistral_client_is_configured_with_a_key():
    client = LLMClient(LLMSettings(provider="mistral", mistral_api_key="test-key", mistral_model="ministral-8b-latest"))
    assert client.is_configured()
    assert client.model == "ministral-8b-latest"
    assert client.describe() == "Mistral · ministral-8b-latest"


def test_azure_needs_endpoint_and_key():
    assert not LLMClient(LLMSettings(provider="azure", azure_api_key="k")).is_configured()
    assert LLMClient(LLMSettings(provider="azure", azure_api_key="k",
                                 azure_endpoint="https://x.openai.azure.com/")).is_configured()


def test_unconfigured_client_raises_instead_of_answering():
    client = LLMClient(LLMSettings(provider="mistral", mistral_api_key=""))
    assert not client.is_configured()
    with pytest.raises(LLMNotConfigured):
        client.chat("system", "question")


def test_default_settings_come_from_environment_and_tests_have_no_key():
    assert not LLMClient().is_configured()


@pytest.mark.parametrize("raw", ['{"a": 1}', '```json\n{"a": 1}\n```', '```\n{"a": 1}```'])
def test_parse_json_reply_accepts_fenced_json(raw):
    assert parse_json_reply(raw) == {"a": 1}


@pytest.mark.parametrize("raw", ["not json", "[1, 2]", ""])
def test_parse_json_reply_rejects_non_objects(raw):
    assert parse_json_reply(raw) is None


def test_cut_off_reply_keeps_complete_items():
    raw = ('```json\n{"swcs": [{"name": "A_SWC", "type": "x"}, {"name": "B_SWC"}],\n'
           ' "dependencies": [{"source_swc": "A_SWC", "target_swc": "B_SWC"}, {"source_swc": "B_S')
    assert parse_json_reply(raw) == {
        "swcs": [{"name": "A_SWC", "type": "x"}, {"name": "B_SWC"}],
        "dependencies": [{"source_swc": "A_SWC", "target_swc": "B_SWC"}],
    }


def test_cut_off_inside_a_string_with_braces_is_handled():
    raw = '{"swcs": [{"name": "A_SWC", "description": "uses {x}"}, {"name": "B_SWC", "description": "half'
    assert parse_json_reply(raw) == {"swcs": [{"name": "A_SWC", "description": "uses {x}"}]}
