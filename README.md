# MacroTrackr Bot

Telegram bot that analyzes meal photos and tracks daily calorie progress using OpenAI GPT-4 Vision.

## Features

- 📸 Photo analysis with calorie/macro breakdown
- 📊 Daily calorie progress tracking (5am-5am cycle) 
- 📤 Auto-posts to Telegram channel
- 🎯 Commands: `/progress`, `/resetprogress`
- 🗄️ PostgreSQL storage

## Setup

### 1. Prerequisites
- Telegram Bot Token (from @BotFather)
- OpenAI API Key
- Telegram Channel (bot as admin)
- PostgreSQL Database (Render free tier)

### 2. Local Development
```bash
git clone https://github.com/EchoKes/macrotrackr-bot.git
cd macrotrackr-bot
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your values
python app.py
```

### 3. Deploy on Render
1. **Create PostgreSQL Database**
   - Go to Render Dashboard → New → PostgreSQL
   - Database Name: `macrotrackr_db`
   - Username: `macrotrackr_user`
   - Copy the Internal Database URL

2. **Create Web Service**
   - Connect your GitHub repository
   - Set environment variables:
     - `TELEGRAM_BOT_TOKEN`
     - `OPENAI_API_KEY` 
     - `CHANNEL_ID`
     - `DATABASE_URL` (from PostgreSQL service)

3. **Initialize Database**
   - Visit: `https://your-app.onrender.com/init-db`
   - Should return: `{"status": "success", "message": "Database initialized successfully"}`

4. **Set Telegram Webhook**
```bash
curl -X POST https://api.telegram.org/bot<TOKEN>/setWebhook \
  -d '{"url": "https://your-app.onrender.com/webhook"}'
```

## Usage

### Basic Commands
- Send **photo with meal description** → Get analysis + progress update
- `/progress` → View current daily progress
- `/resetprogress` → Reset daily calorie progress

### Example Interaction
1. **User sends meal photo** with caption: "Grilled chicken with rice and vegetables"
2. **Bot responds** with analysis + posts to channel
3. **Progress automatically shown**:

```
📊 Meal Analysis for John

*Meal:* Grilled chicken with rice and vegetables
*Breakdown:*
• Grilled chicken breast: 185 kcal | P 35g | C 0g | F 4g  
• Steamed rice: 150 kcal | P 3g | C 30g | F 0g
• Mixed vegetables: 40 kcal | P 2g | C 8g | F 0g
*Total:* 375 kcal | P 40g | C 38g | F 4g

📊 *Daily Calorie Progress*
[██████░░░░░░░░░░░░░░] 825 / 1350 kcal (61%)

🎯 Remaining: 525 kcal
```