"""
MacroTrackr Bot - Main Flask application.
Refactored for better code organization and maintainability.
"""
import logging
import traceback
import threading
from flask import Flask, request, jsonify
from typing import Dict, Any

from config import config
from database.connection import init_database, check_db_connection
from database.models import MealCalorie
from services.openai_service import OpenAIService
from services.telegram_service import TelegramService
from services.progress_service import ProgressService
from utils.helpers import extract_total_calories

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)


def process_meal_photo(message: Dict[str, Any]) -> None:
    """
    Process incoming meal photo message.
    
    Args:
        message: Telegram message object
    """
    try:
        chat_id = str(message['chat']['id'])
        user_name = message['from'].get('first_name', 'Unknown')
        user_id = message['from']['id']
        
        # Check for photo
        if 'photo' not in message:
            TelegramService.send_message(
                chat_id,
                "❌ Please send a photo of your meal along with a description."
            )
            return
        
        # Get caption
        caption = message.get('caption', '').strip()
        if not caption:
            TelegramService.send_message(
                chat_id,
                "❌ Please include a brief description of your meal as a caption."
            )
            return
        
        # Get the highest resolution photo
        photo = max(message['photo'], key=lambda p: p.get('file_size', 0))
        file_id = photo['file_id']
        
        # Send processing message
        TelegramService.send_message(chat_id, "🔄 Analyzing your meal...")
        
        # Download and process photo
        image_base64 = TelegramService.get_photo_from_telegram(file_id)
        if not image_base64:
            TelegramService.send_message(
                chat_id,
                "❌ Failed to download photo. Please try again."
            )
            return
        
        # Analyze with OpenAI
        analysis = OpenAIService.analyze_meal(image_base64, caption)
        if not analysis:
            TelegramService.send_message(
                chat_id,
                "❌ Failed to analyze meal. Please try again later."
            )
            return
        
        # Extract calories from the analysis
        calories = extract_total_calories(analysis)
        
        # Format final message
        formatted_message = f"📊 *Meal Analysis for {user_name}*\n\n{analysis}"
        
        # Send result back to user
        TelegramService.send_message(chat_id, f"✅ Analysis complete!\n\n{formatted_message}")
        
        # Post to channel
        channel_success = TelegramService.send_message(config.CHANNEL_ID, formatted_message, file_id)
        
        if channel_success:
            TelegramService.send_message(chat_id, "📤 Posted to tracking channel!")
            
            # Store calories in database
            if calories > 0:
                store_success = MealCalorie.store(user_id, user_name, calories, analysis)
                if store_success:
                    # Show daily progress after successful meal submission and storage
                    progress = ProgressService.calculate_daily_progress(user_id)
                    progress_message = ProgressService.format_progress_message(progress)
                    
                    # Send progress to user
                    TelegramService.send_message(chat_id, progress_message)
                    
                    # Also post progress to channel
                    TelegramService.send_message(config.CHANNEL_ID, progress_message)
                else:
                    logger.warning(f"Failed to store calories for user {user_name}")
            else:
                logger.warning(f"No calories extracted from analysis for user {user_name}")
        else:
            TelegramService.send_message(chat_id, "⚠️ Analysis complete but failed to post to channel.")
            
    except Exception as e:
        logger.error(f"Error processing meal photo: {e}\n{traceback.format_exc()}")
        if 'chat' in message:
            TelegramService.send_message(
                str(message['chat']['id']),
                "❌ An error occurred while processing your meal. Please try again."
            )


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Render."""
    try:
        config.validate_required_env_vars()
        db_status = check_db_connection()
        
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

@app.route('/test-channel', methods=['GET'])
def test_channel_endpoint():
    """Test channel access endpoint for debugging."""
    try:
        result = TelegramService.test_channel_access()
        if result['success']:
            return jsonify({
                'status': 'success',
                'message': 'Channel access working',
                'channel_info': result['chat_info'],
                'channel_id': result['channel_id']
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Channel access failed',
                'error': result['error'],
                'channel_id': result['channel_id']
            }), 400
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Channel test error: {str(e)}'
        }), 500


def process_webhook_update(update: Dict[str, Any]) -> None:
    """Process webhook update in background thread."""
    try:
        logger.info(f"Processing webhook update: {update.get('update_id', 'unknown')}")
        
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
                user_id = message['from']['id']
                user_name = message['from'].get('first_name', 'Unknown')
                
                # Check for /progress command
                if text.lower() == '/progress':
                    progress = ProgressService.calculate_daily_progress(user_id)
                    progress_message = ProgressService.format_progress_message(progress)
                    
                    # Send progress to user
                    TelegramService.send_message(chat_id, progress_message)
                    
                    # Also post progress to channel
                    TelegramService.send_message(config.CHANNEL_ID, progress_message)
                
                # Check for /resetprogress command
                elif text.lower() == '/resetprogress':
                    reset_success = ProgressService.reset_progress(user_id)
                    
                    if reset_success:
                        # Show updated progress (should be 0)
                        progress = ProgressService.calculate_daily_progress(user_id)
                        progress_message = ProgressService.format_progress_message(progress)
                        
                        reset_message = f"✅ *Daily progress reset for {user_name}*\n\n{progress_message}"
                        TelegramService.send_message(chat_id, reset_message)
                    else:
                        TelegramService.send_message(chat_id, "❌ Failed to reset daily progress. Please try again.")
                
                # Check for /deletelast command
                elif text.lower() == '/deletelast':
                    delete_success, deleted_meal = MealCalorie.delete_last_meal(user_id)
                    
                    if delete_success and deleted_meal:
                        # Show updated progress after deletion
                        progress = ProgressService.calculate_daily_progress(user_id)
                        progress_message = ProgressService.format_progress_message(progress)
                        
                        delete_message = (
                            f"🗑️ *Last meal deleted for {user_name}*\n"
                            f"Removed: {deleted_meal['calories']} calories\n\n"
                            f"{progress_message}"
                        )
                        TelegramService.send_message(chat_id, delete_message)
                    else:
                        TelegramService.send_message(chat_id, "❌ No recent meal found to delete.")
                
                else:
                    # Send help message for other text messages
                    help_text = TelegramService.get_help_text()
                    TelegramService.send_message(chat_id, help_text)
        
    except Exception as e:
        logger.error(f"Background webhook processing error: {e}\n{traceback.format_exc()}")


@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming Telegram webhook updates with fast ACK."""
    try:
        update = request.get_json()
        
        if not update:
            logger.warning("Received empty webhook update")
            return jsonify({'status': 'error', 'message': 'No data received'}), 400
        
        # Immediately acknowledge the webhook with 200 status
        response = jsonify({'status': 'ok'})
        
        # Process the update in a background thread to prevent Telegram retries
        thread = threading.Thread(target=process_webhook_update, args=(update,))
        thread.daemon = True
        thread.start()
        
        return response, 200
        
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
        config.validate_required_env_vars()
        logger.info("Starting MacroTrackr Bot...")
        
        # Initialize database
        if not init_database():
            logger.error("Failed to initialize database, but continuing...")
        
        app.run(host='0.0.0.0', port=config.PORT, debug=False)
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        exit(1)