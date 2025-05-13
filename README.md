# Reddit Content Moderation Scraper

This is a Python-based web scraper that monitors Reddit posts for potentially harmful content using the Reddit API (PRAW). The scraper provides comprehensive content analysis, media detection, and removal tracking capabilities.

## Features

- Real-time post monitoring across multiple subreddits
- Comprehensive content analysis including:
  - Text content cleaning and normalization
  - URL extraction and tracking
  - Media type detection (images, videos, galleries)
  - Comment analysis
  - Subreddit rule compliance checking
- Removal tracking and analysis
- Rate limiting and error handling
- Detailed logging system
- JSON output with rich metadata

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
   - Monitor specified subreddits for posts in real-time
   - Collect comprehensive post data including:
     - Post content and metadata
     - Media information (images, videos, galleries)
     - Comment analysis
     - Removal status and reasons
     - Subreddit rules and compliance
   - Save matching posts to JSON files with timestamps
   - Run continuously with built-in rate limiting

3. Customize the monitoring:
   - Add/remove subreddits by modifying the `add_subreddit()` calls in `main()`
   - Adjust the monitoring parameters in the `RedditScraper` initialization
   - Configure logging levels and output in the `__init__` method

## Output

The scraper saves posts to JSON files with the following information:
- Basic post information (ID, title, URL, author, timestamps)
- Content analysis:
  - Cleaned text content
  - Extracted URLs
  - Post and title lengths
- Media information:
  - Media type (text, image, video, gallery)
  - Image URLs
  - Video URLs
  - Original post URL
- Comment analysis:
  - Comment content and metadata
  - URL extraction
  - Removal status
- Post status:
  - Removal information
  - Moderation actions
  - Report counts
  - Awards and engagement metrics
- Subreddit rules and compliance

## Advanced Features

- **Rate Limiting**: Built-in rate limiting to comply with Reddit's API restrictions
- **Error Handling**: Comprehensive error handling and logging
- **Media Detection**: Support for various media types including:
  - Direct image links
  - Imgur links
  - Reddit galleries
  - YouTube videos
  - Other media content
- **Content Cleaning**: Text normalization and URL preservation
- **Removal Tracking**: Detailed tracking of post and comment removals

## Notes

- The scraper uses Reddit's API rate limits, so be mindful of the number of requests
- Debug mode can be enabled for detailed logging
- The implementation includes comprehensive error handling and recovery mechanisms
- Consider adding more sophisticated content analysis (e.g., sentiment analysis, machine learning models)
- The current implementation includes basic media detection; consider adding image analysis capabilities 