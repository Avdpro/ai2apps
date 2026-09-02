from pathlib import Path

from benchmarks.knowledge.evaluate_retrieval import evaluate


def test_model_free_knowledge_golden_eval_meets_p1_floor():
    fixture = Path(__file__).parents[1] / "benchmarks/knowledge/eval_cases.json"
    metrics = evaluate(fixture, limit=5)

    assert metrics["cases"] == 7
    assert metrics["recall_at_k"] == 1.0
    assert metrics["mrr"] == 1.0
    assert metrics["citation_precision_at_k"] == 1.0
    assert metrics["no_answer_accuracy"] == 1.0
    assert metrics["answer_citation_precision"] == 1.0
    assert metrics["answer_citation_coverage"] == 1.0
    assert metrics["answer_claim_support"] == 1.0
    assert metrics["citation_authorization_accuracy"] == 1.0
