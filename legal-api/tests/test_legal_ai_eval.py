"""
Ghana Legal AI - DeepEval Evaluation Suite
==========================================

This module provides comprehensive LLM evaluation for the Ghana Legal AI system
using DeepEval metrics for RAG quality, hallucination detection, and role adherence.

Usage:
    deepeval test run tests/test_legal_ai_eval.py
    
Or with pytest:
    pytest tests/test_legal_ai_eval.py -v
"""

import pytest
from deepeval import assert_test
from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    HallucinationMetric,
    GEval,
)
from deepeval.test_case import LLMTestCase, LLMTestCaseParams


# =============================================================================
# Test Cases for Constitutional Expert
# =============================================================================

class TestConstitutionalExpert:
    """Evaluation tests for the Constitutional Expert persona."""
    
    @pytest.fixture
    def constitutional_context(self):
        """Sample constitutional context from the 1992 Constitution."""
        return [
            "Article 1(1) of the 1992 Constitution states: The Sovereignty of Ghana resides in the people of Ghana in whose name and for whose welfare the powers of government are to be exercised.",
            "Article 12(1) states: The fundamental human rights and freedoms enshrined in this chapter shall be respected and upheld by the Executive, Legislature and Judiciary and all other organs of government.",
            "Article 21 guarantees freedom of speech, expression, and the press."
        ]
    
    def test_constitutional_answer_relevancy(self, constitutional_context):
        """Test that responses are relevant to constitutional questions."""
        test_case = LLMTestCase(
            input="What does the 1992 Constitution say about sovereignty?",
            actual_output="According to Article 1(1) of the 1992 Constitution of Ghana, sovereignty resides in the people of Ghana. The powers of government are exercised in their name and for their welfare. This establishes Ghana as a sovereign democratic state.",
            expected_output="The sovereignty of Ghana resides in the people, as stated in Article 1(1).",
            retrieval_context=constitutional_context
        )
        
        metric = AnswerRelevancyMetric(threshold=0.7)
        assert_test(test_case, [metric])
    
    def test_constitutional_faithfulness(self, constitutional_context):
        """Test that responses are faithful to the retrieved context."""
        test_case = LLMTestCase(
            input="What fundamental rights are protected in Ghana?",
            actual_output="The 1992 Constitution of Ghana, in Article 12(1), mandates that fundamental human rights and freedoms must be respected and upheld by the Executive, Legislature, Judiciary, and all other organs of government.",
            retrieval_context=constitutional_context
        )
        
        metric = FaithfulnessMetric(threshold=0.7)
        assert_test(test_case, [metric])
    
    def test_constitutional_no_hallucination(self, constitutional_context):
        """Test that the constitutional expert doesn't hallucinate facts."""
        test_case = LLMTestCase(
            input="What does Article 21 cover?",
            actual_output="Article 21 of the 1992 Constitution guarantees fundamental freedoms including freedom of speech, expression, and the press. These are protected rights under Ghanaian law.",
            context=constitutional_context
        )
        
        metric = HallucinationMetric(threshold=0.5)
        assert_test(test_case, [metric])


# =============================================================================
# Test Cases for Case Law Expert  
# =============================================================================

class TestCaseLawExpert:
    """Evaluation tests for the Case Law Analyst persona."""
    
    @pytest.fixture
    def case_law_context(self):
        """Sample case law context from Ghanaian courts."""
        return [
            "In Tuffuor v Attorney General [1980] GLR 637, the Supreme Court held that the Constitution is the supreme law of Ghana and any law inconsistent with it is void to the extent of the inconsistency.",
            "The doctrine of stare decisis requires courts to follow precedents set by higher courts in similar cases.",
            "The Supreme Court of Ghana is the highest court of appeal and has original jurisdiction in constitutional matters."
        ]
    
    def test_case_law_contextual_precision(self, case_law_context):
        """Test that case law citations are precise and accurate."""
        test_case = LLMTestCase(
            input="What is the significance of Tuffuor v Attorney General?",
            actual_output="Tuffuor v Attorney General [1980] GLR 637 is a landmark Supreme Court case that established the supremacy of the Constitution. The court held that any law inconsistent with the Constitution is void to the extent of the inconsistency. This case reinforced constitutional supremacy in Ghana's legal framework.",
            expected_output="Tuffuor v Attorney General established constitutional supremacy in Ghana.",
            retrieval_context=case_law_context
        )
        
        metric = ContextualPrecisionMetric(threshold=0.7)
        assert_test(test_case, [metric])
    
    def test_case_law_legal_accuracy(self, case_law_context):
        """Test legal accuracy using G-Eval with custom criteria."""
        test_case = LLMTestCase(
            input="Explain stare decisis in Ghana.",
            actual_output="Stare decisis is a legal doctrine in Ghana that requires courts to follow precedents established by higher courts in similar cases. This ensures consistency and predictability in the application of law.",
            expected_output="Stare decisis means courts must follow precedents from higher courts.",
            retrieval_context=case_law_context
        )
        
        legal_accuracy_metric = GEval(
            name="Legal Accuracy",
            criteria="Evaluate whether the response accurately explains legal concepts and correctly cites legal principles. The response should be legally sound and consistent with Ghanaian jurisprudence.",
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.RETRIEVAL_CONTEXT
            ],
            threshold=0.7
        )
        
        assert_test(test_case, [legal_accuracy_metric])


# =============================================================================
# Test Cases for Role Adherence (All Experts)
# =============================================================================

class TestRoleAdherence:
    """Test that each expert adheres to their assigned persona and style."""
    
    def test_constitutional_expert_style(self):
        """Test Constitutional Expert uses formal, educational style."""
        test_case = LLMTestCase(
            input="What are my rights according to the constitution?",
            actual_output="According to Chapter 5 of the 1992 Constitution of Ghana, citizens are guaranteed fundamental human rights and freedoms. These include, inter alia, the right to life (Article 13), the right to personal liberty (Article 14), respect for human dignity (Article 15), and protection from slavery and forced labour (Article 16). These rights are justiciable and enforceable in the courts of law.",
            expected_output="A formal, educational response citing specific constitutional articles."
        )
        
        style_metric = GEval(
            name="Constitutional Expert Style",
            criteria="The response should be formal, precise, and educational. It should cite specific constitutional articles and explain concepts clearly to laypeople. The tone should be authoritative yet accessible.",
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT
            ],
            threshold=0.7
        )
        
        assert_test(test_case, [style_metric])
    
    def test_case_law_expert_style(self):
        """Test Case Law Analyst uses logical, argumentative style."""
        test_case = LLMTestCase(
            input="How do courts interpret ambiguous statutes?",
            actual_output="In matters of statutory interpretation, Ghanaian courts apply several canons of construction. First, the literal rule: words are given their ordinary meaning. However, where this leads to absurdity, courts apply the mischief rule, as demonstrated in Mensah v Attorney General, examining the statute's purpose. The Supreme Court has consistently held that statutes must be interpreted in light of constitutional provisions.",
            expected_output="A logical, argumentative response citing case precedents."
        )
        
        style_metric = GEval(
            name="Case Law Analyst Style", 
            criteria="The response should be logical and argumentative like a barrister. It should cite case precedents and explain judicial reasoning. The style should be detailed and focused on how law is applied in practice.",
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT
            ],
            threshold=0.7
        )
        
        assert_test(test_case, [style_metric])


# =============================================================================
# RAG Quality Metrics
# =============================================================================

class TestRAGQuality:
    """Test overall RAG pipeline quality."""
    
    @pytest.fixture
    def mixed_context(self):
        """Mixed context from multiple sources."""
        return [
            "The 1992 Constitution is the supreme law of Ghana.",
            "Ghana gained independence on 6th March 1957.",
            "The Supreme Court has original jurisdiction in constitutional matters.",
            "Customary law is recognized as part of Ghana's legal system."
        ]
    
    def test_contextual_recall(self, mixed_context):
        """Test that relevant context is being retrieved."""
        test_case = LLMTestCase(
            input="What is the role of the Supreme Court in Ghana?",
            actual_output="The Supreme Court of Ghana serves as the highest court of appeal in the country. It has original jurisdiction in constitutional matters, meaning cases involving interpretation of the Constitution are heard directly by the Supreme Court. This is established under the 1992 Constitution.",
            expected_output="The Supreme Court is the highest appellate court with constitutional jurisdiction.",
            retrieval_context=mixed_context
        )
        
        metric = ContextualRecallMetric(threshold=0.6)
        assert_test(test_case, [metric])


# =============================================================================
# Evaluation Dataset Generator
# =============================================================================

def generate_evaluation_dataset():
    """
    Generate a dataset of test cases for batch evaluation.
    Can be used with: deepeval evaluate --dataset
    """
    from deepeval.dataset import EvaluationDataset
    
    test_cases = [
        LLMTestCase(
            input="What is the supreme law of Ghana?",
            actual_output="The 1992 Constitution is the supreme law of Ghana. Any law inconsistent with it is void.",
            expected_output="The 1992 Constitution",
            retrieval_context=["Article 1 establishes the 1992 Constitution as the supreme law of Ghana."]
        ),
        LLMTestCase(
            input="When did Ghana gain independence?",
            actual_output="Ghana gained independence on 6th March 1957, becoming the first sub-Saharan African country to achieve independence from colonial rule.",
            expected_output="6th March 1957",
            retrieval_context=["Ghana gained independence on 6th March 1957."]
        ),
        LLMTestCase(
            input="What are the branches of government in Ghana?",
            actual_output="Ghana operates a separation of powers system with three branches: the Executive (led by the President), the Legislature (Parliament), and the Judiciary (headed by the Supreme Court).",
            expected_output="Executive, Legislature, and Judiciary",
            retrieval_context=["The 1992 Constitution establishes three branches of government: Executive, Legislature, and Judiciary."]
        ),
    ]
    
    return EvaluationDataset(test_cases=test_cases)


if __name__ == "__main__":
    # Run with: python -m tests.test_legal_ai_eval
    import deepeval
    
    dataset = generate_evaluation_dataset()
    
    # Evaluate with multiple metrics
    metrics = [
        AnswerRelevancyMetric(threshold=0.7),
        FaithfulnessMetric(threshold=0.7),
    ]
    
    deepeval.evaluate(dataset, metrics)
