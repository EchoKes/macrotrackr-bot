import os
import logging
import traceback
from flask import Flask, request, jsonify
import requests
import openai
from typing import Dict, Any, Optional
import base64
import re
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from urllib.parse import urlparse
    POSTGRES_AVAILABLE = True
except ImportError as e:
    logger.error(f"PostgreSQL dependencies not available: {e}")
    POSTGRES_AVAILABLE = False

# Initialize Flask app
app = Flask(__name__)

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
CHANNEL_ID = os.getenv('CHANNEL_ID')
DATABASE_URL = os.getenv('DATABASE_URL')

# Initialize OpenAI client
openai.api_key = OPENAI_API_KEY

# Telegram API base URL
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Daily calorie target (constant)
DAILY_CALORIE_TARGET = 1350

def validate_environment() -> None:
    """Validate that all required environment variables are set."""
    required_vars = ['TELEGRAM_BOT_TOKEN', 'OPENAI_API_KEY', 'CHANNEL_ID', 'DATABASE_URL']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

def get_db_connection():
    """Get a connection to the PostgreSQL database."""
    if not POSTGRES_AVAILABLE:
        logger.error("PostgreSQL not available")
        return None
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return None

def init_database():
    """Initialize the database table for meal calories."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        
        with conn.cursor() as cur:
            # Create table if it doesn't exist
            cur.execute("""
                CREATE TABLE IF NOT EXISTS meal_calories (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    user_name VARCHAR(255),
                    calories INTEGER NOT NULL,
                    meal_analysis TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            
            # Create index on user_id and created_at for faster queries
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_meal_calories_user_date 
                ON meal_calories(user_id, created_at);
            """)
            
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False

def store_meal_calories(user_id: int, user_name: str, calories: int, meal_analysis: str) -> bool:
    """Store meal calories in the database."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO meal_calories (user_id, user_name, calories, meal_analysis)
                VALUES (%s, %s, %s, %s)
            """, (user_id, user_name, calories, meal_analysis))
        
        conn.commit()
        conn.close()
        logger.info(f"Stored {calories} calories for user {user_name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to store meal calories: {e}")
        return False

def get_daily_calories(user_id: int) -> int:
    """Get total calories for the user within the current 5am-to-5am window."""
    try:
        start_time, _ = get_daily_window_timestamps()
        
        conn = get_db_connection()
        if not conn:
            return 0
        
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(SUM(calories), 0) as total_calories
                FROM meal_calories
                WHERE user_id = %s AND created_at >= %s
            """, (user_id, start_time))
            
            result = cur.fetchone()
            total_calories = result[0] if result else 0
        
        conn.close()
        logger.info(f"Retrieved {total_calories} total calories for user {user_id}")
        return total_calories
        
    except Exception as e:
        logger.error(f"Failed to get daily calories: {e}")
        return 0

def reset_daily_calories(user_id: int) -> bool:
    """Reset (delete) all meal calories for the user within the current 5am-to-5am window."""
    try:
        start_time, _ = get_daily_window_timestamps()
        
        conn = get_db_connection()
        if not conn:
            return False
        
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM meal_calories
                WHERE user_id = %s AND created_at >= %s
            """, (user_id, start_time))
            
            deleted_count = cur.rowcount
        
        conn.commit()
        conn.close()
        logger.info(f"Reset {deleted_count} meal entries for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to reset daily calories: {e}")
        return False

def get_daily_window_timestamps() -> tuple:
    """
    Get start and end timestamps for the current 24-hour cycle (5am to 5am).
    Returns tuple of (start_timestamp, end_timestamp).
    """
    now = datetime.now()
    
    # Get today's 5am
    today_5am = now.replace(hour=5, minute=0, second=0, microsecond=0)
    
    # If current time is before 5am, use yesterday's 5am as start
    if now.hour < 5:
        start_time = today_5am - timedelta(days=1)
        end_time = today_5am
    else:
        # If current time is after 5am, use today's 5am as start
        start_time = today_5am
        end_time = today_5am + timedelta(days=1)
    
    return start_time, end_time

def extract_total_calories(analysis_text: str) -> int:
    """
    Extract total calories from meal analysis text.
    Tries multiple patterns to handle different formats.
    Returns 0 if no calories found.
    """
    # Multiple patterns to handle different possible formats
    patterns = [
        r'\*Total\*:?\s*(\d+)\s*kcal',  # *Total:* 450 kcal
        r'Total:?\s*(\d+)\s*kcal',      # Total: 450 kcal
        r'Total.*?(\d+)\s*kcal',        # Total anything 450 kcal
        r'(\d+)\s*kcal.*?total',        # 450 kcal ... total (case insensitive)
        r'total.*?(\d+)\s*kcal',        # total ... 450 kcal (case insensitive)
        r'(\d+)\s*kcal.*?P\s*\d+g.*?C\s*\d+g.*?F\s*\d+g',  # Pattern with macros
    ]
    
    for pattern in patterns:
        match = re.search(pattern, analysis_text, re.IGNORECASE)
        if match:
            try:
                calories = int(match.group(1))
                # Sanity check: calories should be reasonable (between 0 and 3000)
                if 0 <= calories <= 3000:
                    logger.info(f"Extracted {calories} calories using pattern: {pattern}")
                    return calories
            except (ValueError, IndexError):
                continue
    
    logger.warning(f"Could not extract calories from text: {analysis_text[:200]}...")
    return 0

def calculate_daily_progress(user_id: int) -> dict:
    """
    Calculate current daily calorie progress from database.
    Returns dict with progress information.
    """
    total_calories = get_daily_calories(user_id)
    
    percentage = min(100, round((total_calories / DAILY_CALORIE_TARGET) * 100)) if DAILY_CALORIE_TARGET > 0 else 0
    remaining_calories = max(0, DAILY_CALORIE_TARGET - total_calories)
    
    return {
        'total_calories': total_calories,
        'target_calories': DAILY_CALORIE_TARGET,
        'percentage': percentage,
        'remaining_calories': remaining_calories
    }

def create_progress_bar(percentage: int, length: int = 20) -> str:
    """
    Create a visual progress bar.
    """
    filled_length = round(length * percentage / 100)
    bar = '█' * filled_length + '░' * (length - filled_length)
    return f"[{bar}]"

def format_progress_message(progress: dict) -> str:
    """
    Format the progress information into a message focused on remaining calories.
    """
    progress_bar = create_progress_bar(progress['percentage'])
    
    message = f"""📊 *Daily Calorie Progress*
{progress_bar} {progress['total_calories']} / {progress['target_calories']} kcal ({progress['percentage']}%)

🎯 Remaining: {progress['remaining_calories']} kcal"""
    
    return message

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
'parse_mode': 'Markdown'
            }
        else:
            # Send text message
            url = f"{TELEGRAM_API_URL}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': text,
'parse_mode': 'Markdown'
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
        
        # Extract calories from the analysis
        calories = extract_total_calories(analysis)
        user_id = message['from']['id']
        
        # Format final message
        formatted_message = f"📊 *Meal Analysis for {user_name}*\n\n{analysis}"
        
        # Send result back to user
        send_telegram_message(chat_id, f"✅ Analysis complete!\n\n{formatted_message}")
        
        # Post to channel
        channel_success = send_telegram_message(CHANNEL_ID, formatted_message, file_id)
        
        if channel_success:
            send_telegram_message(chat_id, "📤 Posted to tracking channel!")
            
            # Store calories in database
            if calories > 0:
                store_success = store_meal_calories(user_id, user_name, calories, analysis)
                if store_success:
                    # Show daily progress after successful meal submission and storage
                    progress = calculate_daily_progress(user_id)
                    progress_message = format_progress_message(progress)
                    send_telegram_message(chat_id, progress_message)
                else:
                    logger.warning(f"Failed to store calories for user {user_name}")
            else:
                logger.warning(f"No calories extracted from analysis for user {user_name}")
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
        
        # Check database connection
        conn = get_db_connection()
        if conn:
            conn.close()
            db_status = 'connected'
        else:
            db_status = 'disconnected'
        
        return jsonify({
            'status': 'healthy',
            'service': 'macrotrackr-bot',
            'environment': 'production',
            'database': db_status
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

@app.route('/init-db', methods=['GET'])
def init_db_endpoint():
    """Manual database initialization endpoint."""
    try:
        success = init_database()
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Database initialized successfully'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to initialize database - check logs'
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Database initialization error: {str(e)}'
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
                # Handle text messages
                chat_id = str(message['chat']['id'])
                text = message.get('text', '').strip()
                
                # Check for /progress command
                if text.lower() == '/progress':
                    user_id = message['from']['id']
                    progress = calculate_daily_progress(user_id)
                    progress_message = format_progress_message(progress)
                    send_telegram_message(chat_id, progress_message)
                
                # Check for /resetprogress command
                elif text.lower() == '/resetprogress':
                    user_id = message['from']['id']
                    user_name = message['from'].get('first_name', 'Unknown')
                    
                    # Reset daily calories
                    reset_success = reset_daily_calories(user_id)
                    
                    if reset_success:
                        # Show updated progress (should be 0)
                        progress = calculate_daily_progress(user_id)
                        progress_message = format_progress_message(progress)
                        
                        reset_message = f"✅ *Daily progress reset for {user_name}*\n\n{progress_message}"
                        send_telegram_message(chat_id, reset_message)
                    else:
                        send_telegram_message(chat_id, "❌ Failed to reset daily progress. Please try again.")
                
                else:
                    # Send help message for other text messages
                    help_text = (
                        "🍽️ *Macro Tracker Bot*\n\n"
                        "Send me a photo of your meal with a brief description as the caption, "
                        "and I'll analyze the calories and macros for you!\n\n"
                        "Commands:\n"
                        "• /progress - View your daily calorie progress\n"
                        "• /resetprogress - Reset your daily calorie progress\n\n"
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
        
        # Initialize database
        if not init_database():
            logger.error("Failed to initialize database, but continuing...")
        
        app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        exit(1)