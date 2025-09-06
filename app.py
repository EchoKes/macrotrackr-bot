import os
import logging
import traceback
from flask import Flask, request, jsonify
import requests
import openai
from typing import Dict, Any, Optional
import base64

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
CHANNEL_ID = os.getenv('CHANNEL_ID')

# Initialize OpenAI client
openai.api_key = OPENAI_API_KEY

# Telegram API base URL
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

def validate_environment() -> None:
    """Validate that all required environment variables are set."""
    required_vars = ['TELEGRAM_BOT_TOKEN', 'OPENAI_API_KEY', 'CHANNEL_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

def send_telegram_message(chat_id: str, text: str, photo_file_id: Optional[str] = None) -> bool:
    """
    Send a message or photo with caption to a Telegram chat.
    
    Args:
        chat_id: Telegram chat ID
        text: Message text or photo caption
        photo_file_id: Optional Telegram file ID for photo
    
    Returns:
        True if message sent successfully, False otherwise
    """
    try:
        if photo_file_id:
            # Send photo with caption
            url = f"{TELEGRAM_API_URL}/sendPhoto"
            data = {
                'chat_id': chat_id,
                'photo': photo_file_id,
                'caption': text,
                'parse_mode': 'HTML'
            }
        else:
            # Send text message
            url = f"{TELEGRAM_API_URL}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'HTML'
            }
        
        response = requests.post(url, json=data, timeout=10)
        response.raise_for_status()
        
        logger.info(f"Message sent successfully to chat {chat_id}")
        return True
        
    except requests.RequestException as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False

def get_photo_from_telegram(file_id: str) -> Optional[str]:
    """
    Download photo from Telegram and return as base64 string.
    
    Args:
        file_id: Telegram file ID
    
    Returns:
        Base64 encoded image string or None if failed
    """
    try:
        # Get file info
        file_info_url = f"{TELEGRAM_API_URL}/getFile"
        response = requests.get(file_info_url, params={'file_id': file_id}, timeout=10)
        response.raise_for_status()
        
        file_path = response.json()['result']['file_path']
        
        # Download file
        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
        file_response = requests.get(file_url, timeout=30)
        file_response.raise_for_status()
        
        # Convert to base64
        return base64.b64encode(file_response.content).decode('utf-8')
        
    except requests.RequestException as e:
        logger.error(f"Failed to download photo from Telegram: {e}")
        return None

def analyze_meal_with_openai(image_base64: str, caption: str) -> Optional[str]:
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
            ],
            max_tokens=500,
            temperature=0.3
        )
        
        result = response.choices[0].message.content.strip()
        logger.info("Successfully analyzed meal with OpenAI")
        return result
        
    except Exception as e:
        logger.error(f"OpenAI analysis failed: {e}")
        return None

def process_meal_photo(message: Dict[str, Any]) -> None:
    """
    Process incoming meal photo message.
    
    Args:
        message: Telegram message object
    """
    try:
        chat_id = str(message['chat']['id'])
        user_name = message['from'].get('first_name', 'Unknown')
        
        # Check for photo
        if 'photo' not in message:
            send_telegram_message(
                chat_id,
                "❌ Please send a photo of your meal along with a description."
            )
            return
        
        # Get caption
        caption = message.get('caption', '').strip()
        if not caption:
            send_telegram_message(
                chat_id,
                "❌ Please include a brief description of your meal as a caption."
            )
            return
        
        # Get the highest resolution photo
        photo = max(message['photo'], key=lambda p: p.get('file_size', 0))
        file_id = photo['file_id']
        
        # Send processing message
        send_telegram_message(chat_id, "🔄 Analyzing your meal...")
        
        # Download and process photo
        image_base64 = get_photo_from_telegram(file_id)
        if not image_base64:
            send_telegram_message(
                chat_id,
                "❌ Failed to download photo. Please try again."
            )
            return
        
        # Analyze with OpenAI
        analysis = analyze_meal_with_openai(image_base64, caption)
        if not analysis:
            send_telegram_message(
                chat_id,
                "❌ Failed to analyze meal. Please try again later."
            )
            return
        
        # Format final message
        formatted_message = f"📊 <b>Meal Analysis for {user_name}</b>\n\n{analysis}"
        
        # Send result back to user
        send_telegram_message(chat_id, f"✅ Analysis complete!\n\n{formatted_message}")
        
        # Post to channel
        channel_success = send_telegram_message(CHANNEL_ID, formatted_message, file_id)
        
        if channel_success:
            send_telegram_message(chat_id, "📤 Posted to tracking channel!")
        else:
            send_telegram_message(chat_id, "⚠️ Analysis complete but failed to post to channel.")
            
    except Exception as e:
        logger.error(f"Error processing meal photo: {e}\n{traceback.format_exc()}")
        if 'chat' in message:
            send_telegram_message(
                str(message['chat']['id']),
                "❌ An error occurred while processing your meal. Please try again."
            )

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Render."""
    try:
        validate_environment()
        return jsonify({
            'status': 'healthy',
            'service': 'macrotrackr-bot',
            'environment': 'production'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming Telegram webhook updates."""
    try:
        update = request.get_json()
        
        if not update:
            logger.warning("Received empty webhook update")
            return jsonify({'status': 'error', 'message': 'No data received'}), 400
        
        logger.info(f"Received webhook update: {update.get('update_id', 'unknown')}")
        
        # Handle message
        if 'message' in update:
            message = update['message']
            
            # Check if message has photo
            if 'photo' in message:
                process_meal_photo(message)
            else:
                # Send help message for text-only messages
                chat_id = str(message['chat']['id'])
                help_text = (
                    "🍽️ <b>Macro Tracker Bot</b>\n\n"
                    "Send me a photo of your meal with a brief description as the caption, "
                    "and I'll analyze the calories and macros for you!\n\n"
                    "Example: Send a photo with caption 'Grilled chicken breast with rice and vegetables'"
                )
                send_telegram_message(chat_id, help_text)
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        logger.error(f"Webhook error: {e}\n{traceback.format_exc()}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'status': 'error', 'message': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

if __name__ == '__main__':
    try:
        validate_environment()
        logger.info("Starting MacroTrackr Bot...")
        app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        exit(1)