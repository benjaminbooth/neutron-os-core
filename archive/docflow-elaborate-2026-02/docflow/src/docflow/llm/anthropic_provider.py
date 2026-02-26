"""Anthropic Claude LLM provider."""

import json
from typing import Optional

from ..providers.base import LLMProvider
from ..core import LLMConfig


class AnthropicProvider(LLMProvider):
    """Claude LLM provider using Anthropic's API."""
    
    def __init__(self, config: LLMConfig):
        """Initialize with Anthropic configuration."""
        self.config = config
        
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        except ImportError:
            raise ImportError("anthropic package required: pip install anthropic")
    
    def complete(self, prompt: str, **kwargs) -> str:
        """Generate a text completion using Claude."""
        temperature = kwargs.get("temperature", self.config.temperature)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
        
        message = self.client.messages.create(
            model=self.config.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        return message.content[0].text
    
    def complete_structured(self, prompt: str, schema: dict, **kwargs) -> dict:
        """Generate structured output matching JSON schema.
        
        Uses Claude's native tool_choice for structured outputs.
        """
        temperature = kwargs.get("temperature", self.config.temperature)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
        
        # Create a tool that returns the structured data
        tools = [
            {
                "name": "output",
                "description": "Structured output",
                "input_schema": schema
            }
        ]
        
        message = self.client.messages.create(
            model=self.config.model,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
            tool_choice={"type": "tool", "name": "output"},
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Extract the tool use block
        for block in message.content:
            if hasattr(block, "type") and block.type == "tool_use":
                return block.input
        
        # Fallback if no tool use found
        return {}
