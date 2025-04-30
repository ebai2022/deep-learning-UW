import praw
import time
from datetime import datetime
import json
import os

class RedditScraper:
    def __init__(self, client_id, client_secret, user_agent):
        """
        Initialize the Reddit scraper with API credentials
        """
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        self.subreddits = []
        self.keywords = []
        self.posts_data = []
        
    def add_subreddit(self, subreddit_name):
        """
        Add a subreddit to monitor
        """
        self.subreddits.append(subreddit_name)
        
    def add_keyword(self, keyword):
        """
        Add a keyword to monitor
        """
        self.keywords.append(keyword.lower())
        
    def monitor_posts(self, limit=100, interval=300):
        """
        Monitor posts in specified subreddits for keywords
        Args:
            limit: Number of posts to check per subreddit
            interval: Time interval between checks in seconds
        """
        while True:
            for subreddit_name in self.subreddits:
                subreddit = self.reddit.subreddit(subreddit_name)
                print(f"\nChecking r/{subreddit_name}...")
                
                for post in subreddit.new(limit=limit):
                    # Check if post contains any keywords
                    title = post.title.lower()
                    content = post.selftext.lower() if post.selftext else ""
                    
                    for keyword in self.keywords:
                        if keyword in title or keyword in content:
                            post_data = {
                                'id': post.id,
                                'title': post.title,
                                'url': post.url,
                                'author': str(post.author),
                                'created_utc': post.created_utc,
                                'subreddit': subreddit_name,
                                'keyword_found': keyword,
                                'timestamp': datetime.now().isoformat()
                            }
                            
                            self.posts_data.append(post_data)
                            print(f"Found post matching keyword '{keyword}': {post.title}")
                            
            # Save data to file
            self.save_data()
            
            # Wait for specified interval
            print(f"\nWaiting {interval} seconds before next check...")
            time.sleep(interval)
            
    def save_data(self):
        """
        Save collected post data to a JSON file
        """
        filename = f"reddit_posts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.posts_data, f, ensure_ascii=False, indent=2)
        print(f"Data saved to {filename}")

def main():
    # Initialize scraper with your Reddit API credentials
    scraper = RedditScraper(
        client_id=os.environ.get('CLIENT_ID'),
        client_secret=os.environ.get('CLIENT_SECRET'),
        user_agent='ContentModerationBot/1.0'
    )
    
    # Add subreddits to monitor
    scraper.add_subreddit('all')  # Monitor all subreddits
    # scraper.add_subreddit('subreddit_name')  # Add specific subreddits
    
    # Add keywords to monitor
    scraper.add_keyword('hate speech')
    scraper.add_keyword('harassment')
    scraper.add_keyword('bullying')
    # Add more keywords as needed
    
    # Start monitoring
    print("Starting Reddit content monitoring...")
    scraper.monitor_posts(limit=100, interval=300)  # Check 100 posts every 5 minutes

if __name__ == "__main__":
    main() 