class LegalExpertNameNotFound(Exception):
    """Exception raised when a legal expert's name is not found."""

    def __init__(self, expert_id: str):
        self.message = f"Legal expert name for {expert_id} not found."
        super().__init__(self.message)


class LegalExpertPerspectiveNotFound(Exception):
    """Exception raised when a legal expert's perspective/expertise is not found."""

    def __init__(self, expert_id: str):
        self.message = f"Legal expert expertise for {expert_id} not found."
        super().__init__(self.message)


class LegalExpertStyleNotFound(Exception):
    """Exception raised when a legal expert's style is not found."""

    def __init__(self, expert_id: str):
        self.message = f"Legal expert style for {expert_id} not found."
        super().__init__(self.message)


class LegalExpertContextNotFound(Exception):
    """Exception raised when a legal expert's context is not found."""

    def __init__(self, expert_id: str):
        self.message = f"Legal expert context for {expert_id} not found."
        super().__init__(self.message)
