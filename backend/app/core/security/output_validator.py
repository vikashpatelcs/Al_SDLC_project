"""
Structured output validation and automated repair helper.
Ensures LLM output strictly conforms to Pydantic v2 schemas with up to 2 repair retries.
"""
import json
import re
from typing import Type, TypeVar, Optional, Callable, Any
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class StructuredOutputHelper:
    """Extracts, validates, and automatically repairs JSON outputs against Pydantic models."""

    @staticmethod
    def extract_json_candidate(text: str) -> Optional[str]:
        """Extract JSON substring from raw model output or markdown code fences."""
        if not text:
            return None

        # 1. Match ```json ... ``` code fence
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if fence_match:
            candidate = fence_match.group(1).strip()
            if candidate.startswith(("{", "[")):
                return candidate

        # 2. Match outermost { ... }
        curly_start = text.find("{")
        curly_end = text.rfind("}")
        if curly_start != -1 and curly_end != -1 and curly_end > curly_start:
            return text[curly_start : curly_end + 1]

        # 3. Match outermost [ ... ]
        bracket_start = text.find("[")
        bracket_end = text.rfind("]")
        if bracket_start != -1 and bracket_end != -1 and bracket_end > bracket_start:
            return text[bracket_start : bracket_end + 1]

        return None

    def parse_and_validate(self, text: str, schema_cls: Type[T]) -> T:
        """Parse text directly into target Pydantic model without repair."""
        json_str = self.extract_json_candidate(text)
        if not json_str:
            raise ValueError(f"No JSON object or array found in text: {text[:200]}")

        data = json.loads(json_str)
        return schema_cls.model_validate(data)

    def validate_with_repair(
        self,
        raw_output: str,
        schema_cls: Type[T],
        repair_caller: Optional[Callable[[str], str]] = None,
        max_retries: int = 2,
    ) -> T:
        """
        Validate against schema_cls; if validation fails and repair_caller is provided,
        prompt for automated JSON correction up to max_retries.
        """
        current_text = raw_output
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                return self.parse_and_validate(current_text, schema_cls)
            except (ValueError, json.JSONDecodeError, ValidationError) as e:
                last_error = e
                if attempt < max_retries and repair_caller is not None:
                    repair_prompt = (
                        f"The previous output failed validation against the schema {schema_cls.__name__}.\n"
                        f"Validation Error: {str(e)}\n\n"
                        f"Invalid Output:\n{current_text}\n\n"
                        f"Please output ONLY the valid JSON object adhering to the schema. "
                        f"No markdown explanation, only raw JSON."
                    )
                    current_text = repair_caller(repair_prompt)
                else:
                    break

        raise ValueError(
            f"Failed to obtain valid {schema_cls.__name__} after {max_retries} retries. "
            f"Last error: {last_error}"
        )


output_validator = StructuredOutputHelper()
