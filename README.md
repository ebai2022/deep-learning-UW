# Reddit Content Moderation Scraper

This is a Python-based web scraper that monitors Reddit posts for potentially harmful content using the Reddit API (PRAW).

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Create a Reddit application to get API credentials:
   - Go to https://www.reddit.com/prefs/apps
   - Click "create another app..."
   - Select "script" as the application type
   - Fill in the name and description
   - Set the redirect URI to http://localhost:8080
   - Note down the client ID (under the app name) and client secret

3. Update the credentials in `reddit_scraper.py`:
   - Replace `YOUR_CLIENT_ID` with your actual client ID
   - Replace `YOUR_CLIENT_SECRET` with your actual client secret

## Usage

1. Run the scraper:
```bash
python reddit_scraper.py
```

2. The scraper will:
   - Monitor specified subreddits for posts containing the defined keywords
   - Save matching posts to JSON files with timestamps
   - Run continuously, checking for new posts every 5 minutes

3. Customize the monitoring:
   - Add/remove subreddits by modifying the `add_subreddit()` calls in `main()`
   - Add/remove keywords by modifying the `add_keyword()` calls in `main()`
   - Adjust the monitoring interval and post limit in the `monitor_posts()` call

## Output

The scraper saves matching posts to JSON files with the following information:
- Post ID
- Title
- URL
- Author
- Creation timestamp
- Subreddit
- Matched keyword
- Detection timestamp

## Notes

- The scraper uses Reddit's API rate limits, so be mindful of the number of requests
- Consider adding more sophisticated content analysis (e.g., sentiment analysis, machine learning models)
- The current implementation focuses on text content; consider adding image analysis capabilities 