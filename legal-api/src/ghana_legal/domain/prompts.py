import opik
from loguru import logger


class Prompt:
    def __init__(self, name: str, prompt: str) -> None:
        self.name = name

        try:
            self.__prompt = opik.Prompt(name=name, prompt=prompt)
        except Exception:
            logger.warning(
                "Can't use Opik to version the prompt (probably due to missing or invalid credentials). Falling back to local prompt. The prompt is not versioned, but it's still usable."
            )

            self.__prompt = prompt

    @property
    def prompt(self) -> str:
        if isinstance(self.__prompt, opik.Prompt):
            return self.__prompt.prompt
        else:
            return self.__prompt

    def __str__(self) -> str:
        return self.prompt

    def __repr__(self) -> str:
        return self.__str__()


# ===== PROMPTS =====

# --- Legal Experts ---

__LEGAL_EXPERT_CHARACTER_CARD = """
Let's roleplay. You're {{expert_name}} - a legal expert specializing in Ghana law, engaging with a user 
seeking legal information. Use professional, clear language, citing specific Articles of the 1992 Constitution 
or relevant Case Law where applicable.

Your responses must never exceed 150 words to keep the advice digestible.

Your name, area of expertise and communication style are detailed below.

---

Expert name: {{expert_name}}
Area of Expertise: {{expertise}}
Communication style: {{style}}

---

You must always follow these rules:

- You will never mention that you are an AI or a virtual assistant.
- If it's the first time you're talking to the user, you must introduce yourself and your specialty.
- DISTINGUISH clearly between constitutional provisions, statutory law, and case law precedents.
- Provide plain text responses without any formatting indicators or meta-commentary.
- INCLUDE A DISCLAIMER when necessary that you provide information, not legal advice/representation.
- Always make sure your response is concise.

---

Summary of conversation earlier between {{expert_name}} and the user:

{{summary}}

---

The conversation between {{expert_name}} and the user starts now.
"""

LEGAL_EXPERT_CHARACTER_CARD = Prompt(
    name="legal_expert_character_card",
    prompt=__LEGAL_EXPERT_CHARACTER_CARD,
)

# --- Summary ---

__SUMMARY_PROMPT = """Create a summary of the legal consultation between {{expert_name}} and the user.
The summary must be a short description of the conversation so far, capturing the legal questions asked
and the advice/information provided by {{expert_name}}: """

SUMMARY_PROMPT = Prompt(
    name="summary_prompt",
    prompt=__SUMMARY_PROMPT,
)

__EXTEND_SUMMARY_PROMPT = """This is a summary of the legal consultation to date between {{expert_name}} and the user:

{{summary}}

Extend the summary by taking into account the new messages above: """

EXTEND_SUMMARY_PROMPT = Prompt(
    name="extend_summary_prompt",
    prompt=__EXTEND_SUMMARY_PROMPT,
)

__CONTEXT_SUMMARY_PROMPT = """Your task is to summarise the following legal text into less than 50 words. 
Focus on the key legal principle or statutory provision. Just return the summary, don't include any other text:

{{context}}"""

CONTEXT_SUMMARY_PROMPT = Prompt(
    name="context_summary_prompt",
    prompt=__CONTEXT_SUMMARY_PROMPT,
)

# --- Evaluation Dataset Generation ---

__EVALUATION_DATASET_GENERATION_PROMPT = """
Generate a conversation between a legal expert and a user based on the provided legal document. 
The expert will respond to the user's questions by referencing the document (Constitution, Act, or Ruling).

The conversation should be in the following JSON format:

{
    "messages": [
        {"role": "user", "content": "Hi, I have a question about <legal_topic>. <question_related_to_document> ?"},
        {"role": "assistant", "content": "<expert_response>"},
        {"role": "user", "content": "<follow_up_question> ?"},
        {"role": "assistant", "content": "<expert_response>"},
        {"role": "user", "content": "<follow_up_question> ?"},
        {"role": "assistant", "content": "<expert_response>"}
    ]
}

Generate a maximum of 4 questions and answers and a minimum of 2 questions and answers. 
Ensure that the expert's responses accurately reflect the content of the document.

Legal Expert: {{expert}}
Document: {{document}}

Begin the conversation with a user question, and then generate the expert's response.
"""

EVALUATION_DATASET_GENERATION_PROMPT = Prompt(
    name="evaluation_dataset_generation_prompt",
    prompt=__EVALUATION_DATASET_GENERATION_PROMPT,
)
