"""Shared utilities."""

import json
import re


def parse_json_from_llm(content: str):
    """Parse JSON from LLM response, stripping markdown code blocks if present.
    Some models don't support response_format=json_object and return ```json ... ```.
    """
    if not content or not content.strip():
        raise ValueError("Empty content")
    text = content.strip()
    # Remove ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1).strip()
    # Try to find first { or [ in case of leading text
    for start_char, end_char in (("{", "}"), ("[", "]")):
        start = text.find(start_char)
        if start != -1:
            depth = 0
            for i in range(start, len(text)):
                if text[i] == start_char:
                    depth += 1
                elif text[i] == end_char:
                    depth -= 1
                    if depth == 0:
                        text = text[start : i + 1]
                        break
            break
    return json.loads(text)
