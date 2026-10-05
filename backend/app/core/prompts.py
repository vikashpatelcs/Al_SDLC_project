"""
Versioned prompt loader for FinReq AI agents.
Loads templates from prompts/{version}/{name}.md.
"""
import os
from typing import Dict, Any


class PromptLoader:
    def __init__(self, base_dir: str = "prompts"):
        self.base_dir = base_dir

    def get_prompt(self, name: str, version: str = "v1", **kwargs: Any) -> str:
        """
        Load prompt template file and format with provided keyword arguments.
        """
        prompt_path = os.path.join(self.base_dir, version, f"{name}.md")
        if not os.path.exists(prompt_path):
            raise FileNotFoundError(f"Prompt template not found at {prompt_path}")

        with open(prompt_path, "r", encoding="utf-8") as f:
            template = f.read()

        if kwargs:
            try:
                return template.format(**kwargs)
            except KeyError:
                # If template contains unmatched braces (e.g. JSON examples), safely replace provided keys
                res = template
                for k, v in kwargs.items():
                    res = res.replace(f"{{{k}}}", str(v))
                return res

        return template


prompt_loader = PromptLoader()
