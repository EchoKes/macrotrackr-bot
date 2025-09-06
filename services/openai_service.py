"""
OpenAI service for meal analysis.
"""
import openai
import logging
from typing import Optional

from config import config

logger = logging.getLogger(__name__)

# Initialize OpenAI client
openai.api_key = config.OPENAI_API_KEY


class OpenAIService:
    """Service for interacting with OpenAI API."""
    
    @staticmethod
    def analyze_meal(image_base64: str, caption: str) -> Optional[str]:
        """
        Analyze meal photo and caption using OpenAI GPT-4 Vision.
        
        Args:
            image_base64: Base64 encoded image
            caption: User's meal description
        
        Returns:
            Formatted calorie and macro breakdown or None if failed
        """
        try:
            prompt = f"""
            Analyze this meal photo and description: "{caption}"
            
            Provide a detailed calorie and macro breakdown in this exact format:
            
            *Meal:* [brief summary of the meal]
            *Breakdown:*
            • [food item 1]: [calories] kcal | P [protein]g | C [carbs]g | F [fat]g
            • [food item 2]: [calories] kcal | P [protein]g | C [carbs]g | F [fat]g
            [continue for all visible items]
            *Total:* [total calories] kcal | P [total protein]g | C [total carbs]g | F [total fat]g
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                            }
                        ]
                    }
                ]
            )
            
            # Log token usage
            if hasattr(response, 'usage'):
                usage = response.usage
                logger.info(f"Token usage - Input: {usage.prompt_tokens}, Output: {usage.completion_tokens}, Total: {usage.total_tokens}")
            else:
                logger.warning("No token usage information available in response")
            
            result = response.choices[0].message.content.strip()
            logger.info("Successfully analyzed meal with OpenAI")
            return result
            
        except Exception as e:
            logger.error(f"OpenAI analysis failed: {e}")
            return None