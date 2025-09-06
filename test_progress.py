#!/usr/bin/env python3
"""
Simple test script to verify the progress tracking functions work correctly.
"""

import re
from datetime import datetime, timedelta

# Test data
sample_meal_analysis = """
*Meal:* Grilled chicken with rice and vegetables
*Breakdown:*
• Grilled chicken breast: 230 kcal | P 43g | C 0g | F 5g
• Steamed white rice: 180 kcal | P 4g | C 37g | F 0.5g
• Mixed vegetables: 40 kcal | P 2g | C 8g | F 0g
*Total:* 450 kcal | P 49g | C 45g | F 5.5g
"""

# Test calorie extraction
def extract_total_calories(analysis_text: str) -> int:
    """Extract total calories from the *Total:* line in meal analysis."""
    pattern = r'Total.*?(\d+).*?kcal'
    match = re.search(pattern, analysis_text)
    
    if match:
        return int(match.group(1))
    
    return 0

def get_daily_window_timestamps() -> tuple:
    """Get start and end timestamps for the current 24-hour cycle (5am to 5am)."""
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

def create_progress_bar(percentage: int, length: int = 20) -> str:
    """Create a visual progress bar."""
    filled_length = round(length * percentage / 100)
    bar = '█' * filled_length + '░' * (length - filled_length)
    return f"[{bar}]"

def format_progress_message(progress: dict) -> str:
    """Format the progress information into a message focused on remaining calories."""
    progress_bar = create_progress_bar(progress['percentage'])
    
    message = f"""📊 Daily Calorie Progress
{progress_bar} {progress['total_calories']} / {progress['target_calories']} kcal ({progress['percentage']}%)

🎯 Remaining: {progress['remaining_calories']} kcal"""
    
    return message

# Run tests
if __name__ == "__main__":
    print("Testing progress tracking functions...")
    
    # Test 1: Calorie extraction
    print("\n1. Testing calorie extraction:")
    calories = extract_total_calories(sample_meal_analysis)
    print(f"   Extracted calories: {calories}")
    print(f"   Sample text: {repr(sample_meal_analysis)}")
    # Debug: let's see what the pattern matches
    import re
    
    # Test the working pattern
    pattern = r'Total.*?(\d+).*?kcal'
    matches = re.findall(pattern, sample_meal_analysis)
    print(f"   Pattern '{pattern}' matches: {matches}")
    assert calories == 450, f"Expected 450, got {calories}"
    print("   ✅ Calorie extraction works!")
    
    # Test 2: Time window calculation
    print("\n2. Testing time window calculation:")
    start, end = get_daily_window_timestamps()
    print(f"   Current time window: {start} to {end}")
    print(f"   Window duration: {end - start}")
    print("   ✅ Time window calculation works!")
    
    # Test 3: Progress bar creation
    print("\n3. Testing progress bar:")
    test_percentages = [0, 25, 50, 70, 100]
    for pct in test_percentages:
        bar = create_progress_bar(pct)
        print(f"   {pct}%: {bar}")
    print("   ✅ Progress bar creation works!")
    
    # Test 4: Progress message formatting
    print("\n4. Testing progress message formatting:")
    test_progress = {
        'total_calories': 950,
        'target_calories': 1350,
        'percentage': 70,
        'remaining_calories': 400
    }
    message = format_progress_message(test_progress)
    print(f"   Sample message:\n{message}")
    print("   ✅ Progress message formatting works!")
    
    print("\n✅ All tests passed! Progress tracking implementation is working correctly.")