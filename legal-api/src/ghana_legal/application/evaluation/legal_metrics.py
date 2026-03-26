"""Legal-specific evaluation metrics for the Ghana Legal AI system."""

from typing import List, Dict, Any, Optional
from deepeval.test_case import LLMTestCase
from deepeval.metrics import BaseMetric
from deepeval.utils import get_ellipsis_string
from deepeval.telemetry import capture_metric_type
import re
from loguru import logger


class LegalAccuracyMetric(BaseMetric):
    """Metric to evaluate the accuracy of legal responses."""
    
    def __init__(
        self,
        threshold: float = 0.7,
        include_citations: bool = True,
    ):
        self.threshold = threshold
        self.include_citations = include_citations

    def measure(self, test_case: LLMTestCase) -> float:
        """Measure the legal accuracy of the response."""
        try:
            # Extract legal concepts and citations from the expected output
            expected_citations = self._extract_legal_citations(test_case.expected_output)
            actual_citations = self._extract_legal_citations(test_case.actual_output)
            
            # Calculate citation accuracy
            citation_accuracy = self._calculate_citation_accuracy(expected_citations, actual_citations)
            
            # Extract legal concepts (articles, sections, etc.)
            expected_concepts = self._extract_legal_concepts(test_case.expected_output)
            actual_concepts = self._extract_legal_concepts(test_case.actual_output)
            
            # Calculate concept accuracy
            concept_accuracy = self._calculate_concept_accuracy(expected_concepts, actual_concepts)
            
            # Combine metrics
            if self.include_citations:
                score = 0.6 * concept_accuracy + 0.4 * citation_accuracy
            else:
                score = concept_accuracy
            
            self.success = score >= self.threshold
            self.score = score
            
            return score
        except Exception as e:
            logger.error(f"Error calculating LegalAccuracyMetric: {e}")
            self.success = False
            self.score = 0.0
            return 0.0

    def _extract_legal_citations(self, text: str) -> List[str]:
        """Extract legal citations from text."""
        patterns = [
            r"(?i)(?:article|art\.?)\s+\d+",  # Article 12, Art. 5, etc.
            r"(?i)(?:section|sec\.?)\s+\d+(?:\([a-z0-9]+\))?",  # Section 5, Sec. 5(a), etc.
            r"(?i)(?:act|law)\s+\d+\s+of\s+\d{4}",  # Act 20 of 2020, etc.
            r"[A-Z][A-Z0-9]+/\d+/\d{4}",  # Case numbers like C.A.123/2020
        ]
        
        citations = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            citations.extend([m.lower().strip() for m in matches])
        
        return list(set(citations))  # Remove duplicates

    def _extract_legal_concepts(self, text: str) -> List[str]:
        """Extract legal concepts and principles."""
        # Extract key legal phrases and concepts
        concepts = re.findall(r'\b(?:right to|freedom of|protection of|due process|equal protection|fundamental right)\b', text, re.IGNORECASE)
        return [c.lower().strip() for c in concepts]

    def _calculate_citation_accuracy(self, expected: List[str], actual: List[str]) -> float:
        """Calculate accuracy of legal citations."""
        if not expected:
            return 1.0 if not actual else 0.0
        
        matches = sum(1 for cit in expected if cit in actual)
        return matches / len(expected) if expected else 0.0

    def _calculate_concept_accuracy(self, expected: List[str], actual: List[str]) -> float:
        """Calculate accuracy of legal concepts."""
        if not expected:
            return 1.0 if not actual else 0.0
        
        matches = sum(1 for conc in expected if conc in actual)
        return matches / len(expected) if expected else 0.0

    @property
    def __name__(self):
        return "LegalAccuracy"


class LegalRelevanceMetric(BaseMetric):
    """Metric to evaluate the relevance of legal responses to the query."""
    
    def __init__(
        self,
        threshold: float = 0.6,
    ):
        self.threshold = threshold

    def measure(self, test_case: LLMTestCase) -> float:
        """Measure the relevance of the legal response."""
        try:
            # Check if response addresses the specific legal area mentioned in the input
            input_lower = test_case.input.lower()
            output_lower = test_case.actual_output.lower()
            
            # Look for keywords that indicate legal relevance
            relevance_indicators = [
                "constitution", "article", "section", "court", "case", "law", "act", 
                "legal", "right", "provision", "interpretation", "precedent"
            ]
            
            # Count how many relevance indicators appear in both input and output
            input_indicators = [ind for ind in relevance_indicators if ind in input_lower]
            output_indicators = [ind for ind in relevance_indicators if ind in output_lower]
            
            # Calculate overlap
            if input_indicators:
                relevant_matches = sum(1 for ind in input_indicators if ind in output_indicators)
                relevance_score = relevant_matches / len(input_indicators)
            else:
                # If no legal terms in input, check if response still contains legal content
                relevance_score = len(output_indicators) / len(relevance_indicators) if output_indicators else 0.0
            
            # Check for specific legal concepts
            legal_concept_match = self._calculate_concept_relevance(test_case.input, test_case.actual_output)
            
            # Combine relevance scores
            final_score = 0.7 * relevance_score + 0.3 * legal_concept_match
            
            self.success = final_score >= self.threshold
            self.score = final_score
            
            return final_score
        except Exception as e:
            logger.error(f"Error calculating LegalRelevanceMetric: {e}")
            self.success = False
            self.score = 0.0
            return 0.0

    def _calculate_concept_relevance(self, input_text: str, output_text: str) -> float:
        """Calculate relevance based on legal concepts."""
        input_lower = input_text.lower()
        output_lower = output_text.lower()
        
        # Look for specific legal topic matches
        constitution_terms = ["constitution", "article", "fundamental", "right"]
        case_law_terms = ["court", "case", "precedent", "decision", "judgment"]
        statutory_terms = ["act", "section", "provision", "statute", "law"]
        
        score = 0.0
        max_score = 0.0
        
        # Check constitution terms
        input_has_const = any(term in input_lower for term in constitution_terms)
        output_has_const = any(term in output_lower for term in constitution_terms)
        if input_has_const and output_has_const:
            score += 1.0
        if input_has_const or output_has_const:
            max_score += 1.0
        
        # Check case law terms
        input_has_case = any(term in input_lower for term in case_law_terms)
        output_has_case = any(term in output_lower for term in case_law_terms)
        if input_has_case and output_has_case:
            score += 1.0
        if input_has_case or output_has_case:
            max_score += 1.0
        
        # Check statutory terms
        input_has_stat = any(term in input_lower for term in statutory_terms)
        output_has_stat = any(term in output_lower for term in statutory_terms)
        if input_has_stat and output_has_stat:
            score += 1.0
        if input_has_stat or output_has_stat:
            max_score += 1.0
        
        return score / max_score if max_score > 0 else 0.0

    @property
    def __name__(self):
        return "LegalRelevance"


class LegalAuthorityMetric(BaseMetric):
    """Metric to evaluate if the response cites appropriate legal authority."""
    
    def __init__(
        self,
        threshold: float = 0.5,
    ):
        self.threshold = threshold

    def measure(self, test_case: LLMTestCase) -> float:
        """Measure if the response cites appropriate legal authority."""
        try:
            output_lower = test_case.actual_output.lower()
            
            # Check for authority indicators
            authority_indicators = [
                "supreme court", "court of appeal", "high court",  # Court hierarchy
                "constitution", "1992 constitution", "article", "section",  # Constitutional authority
                "act", "law", "legislation",  # Statutory authority
                "precedent", "case law", "judicial", "court decision",  # Case law authority
            ]
            
            # Count authority indicators
            authority_count = sum(1 for indicator in authority_indicators if indicator in output_lower)
            
            # More indicators = higher authority score
            max_indicators = len(authority_indicators)
            authority_score = authority_count / max_indicators if max_indicators > 0 else 0.0
            
            # Boost score if specific high-authority terms are present
            high_authority_terms = ["supreme court", "1992 constitution", "article"]
            has_high_authority = any(term in output_lower for term in high_authority_terms)
            
            if has_high_authority:
                authority_score = min(1.0, authority_score * 1.5)  # Boost by 50%
            
            self.success = authority_score >= self.threshold
            self.score = authority_score
            
            return authority_score
        except Exception as e:
            logger.error(f"Error calculating LegalAuthorityMetric: {e}")
            self.success = False
            self.score = 0.0
            return 0.0

    @property
    def __name__(self):
        return "LegalAuthority"


def get_legal_metrics() -> List[BaseMetric]:
    """Get a list of legal-specific evaluation metrics.
    
    Returns:
        List of legal-specific DeepEval metrics
    """
    logger.info("Initializing legal-specific evaluation metrics")
    return [
        LegalAccuracyMetric(),
        LegalRelevanceMetric(),
        LegalAuthorityMetric(),
    ]