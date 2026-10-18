"""Test doubles and paths shared by the test modules."""

from pathlib import Path

from autosar_hld_assistant.app.core.llm import LLMError, LLMNotConfigured

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
EBC_PDF = SAMPLES / "ebc_brake_ecu_hld.pdf"
EBC_V13_PDF = SAMPLES / "ebc_brake_ecu_hld_v1_3.pdf"
VBCS_PDF = SAMPLES / "vbcs_brake_system_hld.pdf"


class FakeLLM:
    """Stands in for LLMClient. Records calls; replies with a fixed text or JSON."""

    def __init__(self, reply="", json_reply=None, configured=True, error=None):
        self.reply = reply
        self.json_reply = json_reply
        self.configured = configured
        self.error = error
        self.calls = []

    def is_configured(self):
        return self.configured

    def chat(self, system_prompt, user_prompt, history=None, **_kwargs):
        self.calls.append({"system": system_prompt, "user": user_prompt, "history": history})
        if not self.configured:
            raise LLMNotConfigured("not configured")
        if self.error:
            raise LLMError(self.error)
        return self.reply

    def chat_json(self, system_prompt, user_prompt, **_kwargs):
        self.calls.append({"system": system_prompt, "user": user_prompt})
        return self.json_reply


class FakeRetriever:
    """Returns canned hits; records the queries it was asked."""

    def __init__(self, hits_by_call):
        self.hits_by_call = list(hits_by_call)
        self.queries = []

    def retrieve(self, query, top_k=5):
        self.queries.append(query)
        return self.hits_by_call.pop(0) if self.hits_by_call else []

    @staticmethod
    def format_context(hits):
        return "\n".join(meta["text"] for meta, _ in hits)


def hit(text="BrakeControlSWC provides PP_BrakeCommand.", distance=0.5, page=8):
    return ({"document_name": "doc.pdf", "page_number": page, "section_header": "3.2 BrakeControlSWC",
             "chunk_id": f"doc.pdf_p{page}_c1", "text": text}, distance)
