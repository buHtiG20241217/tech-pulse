import pytest

from autosar_hld_assistant.app.rag.qa_engine import NO_EVIDENCE_REPLY, AnswerStatus, GroundedQAEngine, is_follow_up
from tests.helpers import FakeLLM, FakeRetriever, hit


def _engine(*hits_by_call, threshold=1.2):
    return GroundedQAEngine(retriever=FakeRetriever(hits_by_call), threshold=threshold)


def test_weak_evidence_never_reaches_the_llm():
    llm = FakeLLM(reply="made up")
    answer = _engine([hit(distance=1.6)]).answer_question("Battery warranty?", llm=llm)
    assert answer.status == AnswerStatus.NO_EVIDENCE
    assert answer.text == NO_EVIDENCE_REPLY and not answer.grounded
    assert llm.calls == []


def test_empty_index_is_refused():
    assert _engine([]).answer_question("anything", llm=FakeLLM()).status == AnswerStatus.NO_EVIDENCE


def test_answer_with_citations_when_evidence_is_close():
    llm = FakeLLM(reply="BrakeControlSWC provides PP_BrakeCommand [Doc: doc.pdf, Page: 8, Section: 3.2].")
    answer = _engine([hit(distance=0.5), hit(distance=0.9, page=9)]).answer_question("Ports?", llm=llm)
    assert answer.status == AnswerStatus.ANSWERED and answer.grounded
    assert [c.page_number for c in answer.citations] == [8, 9]
    assert "CONTEXT:" in llm.calls[0]["user"]
    assert NO_EVIDENCE_REPLY in llm.calls[0]["system"]


def test_confidence_follows_best_distance():
    llm = FakeLLM(reply="ok")
    assert _engine([hit(distance=0.5)]).answer_question("q", llm=llm).confidence == "High"
    assert _engine([hit(distance=0.85)]).answer_question("q", llm=llm).confidence == "Medium"
    assert _engine([hit(distance=1.19)]).answer_question("q", llm=llm).confidence == "Low"
    assert _engine([hit(distance=1.9)]).answer_question("q", llm=llm).confidence == "None"


def test_model_refusal_is_detected():
    answer = _engine([hit()]).answer_question("q", llm=FakeLLM(reply=NO_EVIDENCE_REPLY))
    assert answer.status == AnswerStatus.MODEL_DECLINED and not answer.grounded
    assert answer.citations  # the passages it looked at are still shown


def test_without_llm_the_passages_are_still_returned():
    answer = _engine([hit()]).answer_question("q", llm=FakeLLM(configured=False))
    assert answer.status == AnswerStatus.NO_LLM and len(answer.citations) == 1


def test_llm_failure_is_reported_not_raised():
    answer = _engine([hit()]).answer_question("q", llm=FakeLLM(error="timeout"))
    assert answer.status == AnswerStatus.LLM_ERROR and "timeout" in answer.text


def test_unrelated_question_does_not_borrow_previous_evidence():
    retriever = FakeRetriever([[hit(distance=1.6)], [hit(distance=0.6)]])
    engine = GroundedQAEngine(retriever=retriever, threshold=1.2)
    history = [{"role": "user", "content": "Which ports does BrakeControlSWC provide?"},
               {"role": "assistant", "content": "PP_BrakeCommand ..."}]
    llm = FakeLLM(reply="made up")
    answer = engine.answer_question("What is the vehicle battery warranty procedure?", history=history, llm=llm)
    assert answer.status == AnswerStatus.NO_EVIDENCE
    assert len(retriever.queries) == 1 and llm.calls == []


@pytest.mark.parametrize("question, expected", [
    ("And which interface does it use?", True),
    ("What are their data types?", True),
    ("Which ports does BrakeControlSWC provide?", False),
    ("Which signals use that interface, WheelSpeed_If?", False),
    ("What is the battery warranty procedure?", False),
])
def test_follow_up_detection(question, expected):
    assert is_follow_up(question) is expected


def test_follow_up_is_retried_with_previous_question():
    retriever = FakeRetriever([[hit(distance=1.8)], [hit(distance=0.6)]])
    engine = GroundedQAEngine(retriever=retriever, threshold=1.2)
    history = [{"role": "user", "content": "Which ports does BrakeControlSWC provide?"},
               {"role": "assistant", "content": "PP_BrakeCommand ..."}]
    llm = FakeLLM(reply="It uses BrakeCommandIf.")
    answer = engine.answer_question("And which interface does it use?", history=history, llm=llm)
    assert answer.status == AnswerStatus.ANSWERED
    assert retriever.queries[1].startswith("Which ports does BrakeControlSWC provide?")
    assert llm.calls[0]["history"] == history
