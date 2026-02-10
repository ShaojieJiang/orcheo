from orcheo.nodes import evaluation as root_evaluation
from orcheo.nodes.conversational_search import (
    evaluation as conversational_search_evaluation,
)


def test_conversational_search_evaluation_shim_re_exports_nodes() -> None:
    assert conversational_search_evaluation.DatasetNode is root_evaluation.DatasetNode
    assert (
        conversational_search_evaluation.TokenF1MetricsNode
        is root_evaluation.TokenF1MetricsNode
    )
    assert conversational_search_evaluation.__all__ == root_evaluation.__all__
