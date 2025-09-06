# MacroTrackr Bot

Telegram bot that analyzes meal photos and provides calorie/macro breakdowns using OpenAI GPT-4 Vision.

## Features

- 📸 Photo analysis with calorie breakdown
- 🔍 AI-powered food recognition (GPT-4o-mini)
- 📊 Detailed macros (calories, protein, carbs, fat)
- 📤 Auto-posts to Telegram channel
- 🚀 Production ready for Render

## Setup

### 1. Prerequisites
- Telegram Bot Token (from @BotFather)
- OpenAI API Key
- Telegram Channel (bot as admin)

### 2. Local Development
```bash
git clone <repo>
cd macrotrackr-bot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your values
python app.py
```

### 3. Deploy on Render
1. Push to GitHub
2. Create new Web Service on render.com
3. Set environment variables:
   - `TELEGRAM_BOT_TOKEN`
   - `OPENAI_API_KEY` 
   - `CHANNEL_ID`
4. Set webhook:
```bash
curl -X POST https://api.telegram.org/bot<TOKEN>/setWebhook \
  -d '{"url": "https://your-app.onrender.com/webhook"}'
```

## Usage

Send photo with meal description as caption to bot. Get instant analysis posted to your channel.

**Example Output:**
```
Meal: Grilled chicken with rice
Breakdown:
- Chicken breast: 185 kcal | P 35g | C 0g | F 4g
- Rice: 103 kcal | P 2g | C 22g | F 0g
Total: 288 kcal | P 37g | C 22g | F 4g
```