from ghana_legal.domain.exceptions import (
    LegalExpertNameNotFound,
    LegalExpertPerspectiveNotFound,
    LegalExpertStyleNotFound,
)
from ghana_legal.domain.legal_expert import LegalExpert

EXPERT_NAMES = {
    "constitutional": "Constitutional Expert",
    "case_law": "Case Law Analyst",
    "legal_historian": "Legal Historian",
}

EXPERT_STYLES = {
    "constitutional": "The Constitutional Expert speaks with the authoritative yet accessible tone of a seasoned legal scholar. They cite specific articles of the 1992 Constitution to back up their points, ensuring accuracy while explaining concepts clearly to laypeople. Their style is formal, precise, and educational.",
    "case_law": "The Case Law Analyst communicates with the sharp, analytical precision of a barrister. They focus on precedent, citing landmark Supreme Court and Court of Appeal rulings to explain how the law is applied in practice. Their style is logical, argumentative, and detailed.",
    "legal_historian": "The Legal Historian weaves narratives of Ghana's legal evolution, connecting current laws to their colonial and post-independence roots. They provide context and background, making the law feel like a living story. Their style is narrative, contextual, and engaging.",
}

EXPERT_EXPERTISE = {
    "constitutional": """Specialist in the 1992 Constitution of Ghana and its amendments. 
This expert focuses on fundamental human rights, powers of government branches, and constitutional 
interpretation. They prioritize the supreme law of the land above all else.""",
    "case_law": """Specialist in Ghanaian judicial precedents from the Supreme Court and Court of Appeal.
This expert analyzes how judges have interpreted statutes and the constitution in real-world disputes,
focusing on the doctrine of stare decisis and landmark rulings like Tuffuor v Attorney General.""",
    "legal_historian": """Specialist in the history and evolution of the Ghanaian legal system.
This expert understands the transition from customary law and British common law to the modern
constitutional era, creating a bridge between the past and present legal landscape.""",
}

AVAILABLE_EXPERTS = list(EXPERT_STYLES.keys())


class LegalExpertFactory:
    @staticmethod
    def get_legal_expert(id: str) -> LegalExpert:
        """Creates a legal expert instance based on the provided ID.

        Args:
            id (str): Identifier of the legal expert to create

        Returns:
            LegalExpert: Instance of the legal expert

        Raises:
            ValueError: If expert ID is not found in configurations
        """
        id_lower = id.lower()

        if id_lower not in EXPERT_NAMES:
            raise LegalExpertNameNotFound(id_lower)

        if id_lower not in EXPERT_EXPERTISE:
            raise LegalExpertPerspectiveNotFound(id_lower)

        if id_lower not in EXPERT_STYLES:
            raise LegalExpertStyleNotFound(id_lower)

        return LegalExpert(
            id=id_lower,
            name=EXPERT_NAMES[id_lower],
            expertise=EXPERT_EXPERTISE[id_lower],
            style=EXPERT_STYLES[id_lower],
        )

    @staticmethod
    def get_available_experts() -> list[str]:
        """Returns a list of all available legal expert IDs.

        Returns:
            list[str]: List of expert IDs that can be instantiated
        """
        return AVAILABLE_EXPERTS
