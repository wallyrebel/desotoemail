"""
OpenAI API client for DeSoto Email RSS Digest.
Handles API calls with retry logic for rate limits and server errors.
"""

import logging
import random
import time
from typing import Optional, List, Dict, Any

from openai import OpenAI, APIError, RateLimitError, APIConnectionError

from app.config import OPENAI_MAX_RETRIES

logger = logging.getLogger(__name__)


class OpenAIClient:
    """
    OpenAI API client with automatic retry and fallback model support.
    """
    
    def __init__(
        self,
        api_key: str,
        primary_model: str,
        fallback_model: str,
        max_retries: int = OPENAI_MAX_RETRIES
    ):
        self.client = OpenAI(api_key=api_key)
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.max_retries = max_retries
    
    def _call_with_retry(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Optional[str]:
        """
        Make an API call with exponential backoff retry.
        Returns the response content or None on failure.
        """
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                
                return response.choices[0].message.content
                
            except RateLimitError as e:
                wait_time = min(60 * (2 ** attempt), 120)  # Max 2 minutes
                jitter = random.uniform(0, wait_time * 0.1)
                total_wait = wait_time + jitter
                
                logger.warning(
                    f"Rate limited (attempt {attempt + 1}/{self.max_retries}), "
                    f"waiting {total_wait:.1f}s: {e}"
                )
                time.sleep(total_wait)
                
            except APIConnectionError as e:
                wait_time = 5 * (2 ** attempt)  # 5s, 10s, 20s...
                logger.warning(
                    f"Connection error (attempt {attempt + 1}/{self.max_retries}), "
                    f"waiting {wait_time}s: {e}"
                )
                time.sleep(wait_time)
                
            except APIError as e:
                # 5xx errors
                if hasattr(e, 'status_code') and e.status_code and e.status_code >= 500:
                    wait_time = 10 * (2 ** attempt)
                    logger.warning(
                        f"Server error {e.status_code} (attempt {attempt + 1}/{self.max_retries}), "
                        f"waiting {wait_time}s"
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"API error (non-retryable): {e}")
                    return None
                    
            except Exception as e:
                logger.error(f"Unexpected error calling OpenAI: {e}")
                return None
        
        logger.error(f"Failed after {self.max_retries} attempts with model {model}")
        return None
    
    def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Optional[str]:
        """
        Make a completion request, trying primary model first then fallback.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            
        Returns:
            Response content string or None on failure
        """
        # Try primary model first
        logger.debug(f"Attempting completion with {self.primary_model}")
        result = self._call_with_retry(messages, self.primary_model, temperature, max_tokens)
        
        if result:
            return result
        
        # Try fallback model
        logger.warning(f"Primary model failed, trying fallback: {self.fallback_model}")
        result = self._call_with_retry(messages, self.fallback_model, temperature, max_tokens)
        
        if result:
            logger.info(f"Fallback model {self.fallback_model} succeeded")
            return result
        
        logger.error("Both primary and fallback models failed")
        return None


def create_openai_client(config: dict) -> OpenAIClient:
    """
    Create an OpenAI client from config dict.
    """
    return OpenAIClient(
        api_key=config["openai_api_key"],
        primary_model=config["openai_primary_model"],
        fallback_model=config["openai_fallback_model"],
    )
