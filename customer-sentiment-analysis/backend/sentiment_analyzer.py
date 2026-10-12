"""OpenRouter-powered sentiment analysis service."""

import json
import os
import time
import logging
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-4o-mini"
MAX_RETRIES = 3
RETRY_BACKOFF = 1.5
REQUEST_TIMEOUT = 60


class SentimentAnalyzerError(Exception):
    """Raised when sentiment analysis fails in a recoverable way."""
    pass


class SentimentAnalyzer:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        self.model = os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL).strip()
        self.app_url = os.getenv("APP_URL", "http://127.0.0.1:5000")
        self.app_name = os.getenv("APP_NAME", "Customer Sentiment Analysis")

    def is_configured(self) -> bool:
        return bool(self.api_key) and self.api_key != "your_openrouter_api_key_here"

    def health_check(self) -> dict:
        """Lightweight check that the API key is present and the service is reachable."""
        if not self.is_configured():
            return {
                "available": False,
                "message": "OpenRouter API key is not configured.",
            }
        try:
            # Minimal models list call to verify connectivity
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": self.app_url,
                "X-Title": self.app_name,
            }
            resp = requests.get(
                "https://openrouter.ai/api/v1/models",
                headers=headers,
                timeout=10,
            )
            if resp.status_code == 200:
                return {"available": True, "message": "AI service is available.", "model": self.model}
            if resp.status_code == 401:
                return {"available": False, "message": "Invalid OpenRouter API key."}
            return {
                "available": False,
                "message": f"OpenRouter returned status {resp.status_code}.",
            }
        except requests.Timeout:
            return {"available": False, "message": "OpenRouter request timed out."}
        except requests.RequestException as e:
            return {"available": False, "message": f"Cannot reach OpenRouter: {str(e)[:100]}"}

    def analyze(self, text: str) -> dict:
        """
        Analyze a single feedback text and return structured result.
        Raises SentimentAnalyzerError on failure.
        """
        if not self.is_configured():
            raise SentimentAnalyzerError(
                "OpenRouter API key is not configured. Set OPENROUTER_API_KEY in .env"
            )

        text = (text or "").strip()
        if not text:
            raise SentimentAnalyzerError("Empty feedback text.")

        # Truncate extremely long single items (chunking is handled at document level)
        if len(text) > 8000:
            text = text[:8000] + "…"

        system_prompt = self._build_system_prompt()
        user_prompt = f"Analyse the following customer feedback:\n\n\"\"\"\n{text}\n\"\"\""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 800,
            "response_format": {"type": "json_object"},
        }

        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self._call_api(payload)
                result = self._parse_and_validate(response, original_text=text)
                return result
            except SentimentAnalyzerError as e:
                last_error = e
                if "rate limit" in str(e).lower() or "429" in str(e):
                    sleep_time = RETRY_BACKOFF ** attempt
                    logger.warning("Rate limited, retrying in %.1fs (attempt %d)", sleep_time, attempt)
                    time.sleep(sleep_time)
                    continue
                raise
            except Exception as e:
                last_error = e
                logger.exception("Unexpected error on attempt %d", attempt)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF ** attempt)
                    continue
                raise SentimentAnalyzerError(f"Analysis failed after retries: {str(e)[:200]}")

        raise SentimentAnalyzerError(str(last_error) if last_error else "Unknown analysis error")

    def _call_api(self, payload: dict) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.app_url,
            "X-Title": self.app_name,
        }
        try:
            resp = requests.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
        except requests.Timeout:
            raise SentimentAnalyzerError("OpenRouter request timed out.")
        except requests.RequestException as e:
            raise SentimentAnalyzerError(f"Network error contacting OpenRouter: {str(e)[:150]}")

        if resp.status_code == 429:
            raise SentimentAnalyzerError("Rate limit exceeded (429). Please try again later.")
        if resp.status_code == 401:
            raise SentimentAnalyzerError("Invalid or missing OpenRouter API key.")
        if resp.status_code == 402:
            raise SentimentAnalyzerError("OpenRouter account has insufficient credits.")
        if resp.status_code >= 500:
            raise SentimentAnalyzerError(f"OpenRouter service error ({resp.status_code}).")
        if resp.status_code != 200:
            try:
                detail = resp.json().get("error", {}).get("message", resp.text[:200])
            except Exception:
                detail = resp.text[:200]
            raise SentimentAnalyzerError(f"OpenRouter error {resp.status_code}: {detail}")

        try:
            data = resp.json()
        except json.JSONDecodeError:
            raise SentimentAnalyzerError("Malformed JSON response from OpenRouter.")

        return data

    def _parse_and_validate(self, api_response: dict, original_text: str) -> dict:
        """Extract and validate the structured analysis from the model response."""
        try:
            content = api_response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise SentimentAnalyzerError("Unexpected response structure from OpenRouter.")

        if not content or not content.strip():
            raise SentimentAnalyzerError("Empty content in model response.")

        # Some models wrap JSON in markdown fences
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove first and last fence lines
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines).strip()

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            # Attempt to recover JSON object from text
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    parsed = json.loads(content[start : end + 1])
                except json.JSONDecodeError:
                    raise SentimentAnalyzerError("Model returned non-JSON content.")
            else:
                raise SentimentAnalyzerError("Model returned non-JSON content.")

        # Validate required fields
        sentiment = parsed.get("sentiment")
        if sentiment not in ("Positive", "Negative", "Neutral"):
            # Try case-insensitive normalisation
            if isinstance(sentiment, str):
                s = sentiment.strip().capitalize()
                if s in ("Positive", "Negative", "Neutral"):
                    sentiment = s
                else:
                    raise SentimentAnalyzerError(
                        f"Invalid sentiment value returned by model: {sentiment!r}"
                    )
            else:
                raise SentimentAnalyzerError("Missing or invalid sentiment field.")

        explanation = parsed.get("explanation")
        if explanation is not None:
            explanation = str(explanation).strip()[:1000]
        else:
            explanation = ""

        confidence = parsed.get("confidence")
        if confidence is not None:
            try:
                confidence = float(confidence)
                if not (0.0 <= confidence <= 1.0):
                    confidence = None  # discard non-calibrated values outside range
            except (TypeError, ValueError):
                confidence = None

        keywords = parsed.get("keywords") or []
        if not isinstance(keywords, list):
            keywords = []
        keywords = [str(k).strip()[:100] for k in keywords if k][:15]

        complaint_categories = parsed.get("complaint_categories") or []
        if not isinstance(complaint_categories, list):
            complaint_categories = []
        complaint_categories = [str(c).strip()[:80] for c in complaint_categories if c][:10]

        suggested_action = parsed.get("suggested_action")
        if suggested_action is not None:
            suggested_action = str(suggested_action).strip()[:500]
        else:
            suggested_action = None

        return {
            "sentiment": sentiment,
            "explanation": explanation,
            "confidence": confidence,
            "keywords": keywords,
            "complaint_categories": complaint_categories,
            "suggested_action": suggested_action,
            "original_text": original_text[:500] + ("…" if len(original_text) > 500 else ""),
        }

    def _build_system_prompt(self) -> str:
        return """You are an expert customer-feedback analyst. Analyse the given customer feedback and respond ONLY with a valid JSON object matching this schema:

{
  "sentiment": "Positive" | "Negative" | "Neutral",
  "explanation": "Brief explanation of why this classification was chosen (1-3 sentences).",
  "confidence": null,
  "keywords": ["keyword or short phrase", ...],
  "complaint_categories": ["Category Name", ...],
  "suggested_action": "Practical business action if justified, otherwise null"
}

Rules:
- Classify the dominant overall sentiment. If mixed, choose the dominant tone and mention the mixed nature in the explanation.
- confidence must be null unless you have a calibrated probability; do not invent a confidence score.
- keywords: extract the most relevant short phrases (max 10).
- complaint_categories: use consistent, high-level categories such as "Product Quality", "Customer Service", "Delivery", "Pricing", "Us Experience", "Technical Issues", "Billing", "Packaging". Only include when the feedback contains a complaint.
- suggested_action: only when the feedback justifies a concrete improvement; otherwise null.
- Never invent customer statements or facts not present in the feedback.
- Handle short text, spelling errors, emojis, sarcasm and ambiguous language carefully.
- If the text is empty, irrelevant, or too vague to classify, use Neutral and explain why.
- Respond with pure JSON only – no markdown, no commentary outside the JSON object."""


# Singleton instance for convenience
analyzer = SentimentAnalyzer()
