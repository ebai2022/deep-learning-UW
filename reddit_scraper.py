import praw
import time
from datetime import datetime
import json
import os
import random
from typing import List, Dict, Any

class RedditScraper:
    def __init__(self, client_id: str, client_secret: str, user_agent: str, debug: bool = False):
        """
        Initialize the Reddit scraper with API credentials
        """
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        self.subreddits = []
        self.posts_data = []
        self.debug = debug
        self.collected_posts = set()  # Track post IDs to avoid duplicates
        
    def add_subreddit(self, subreddit_name: str):
        """
        Add a subreddit to monitor
        """
        self.subreddits.append(subreddit_name)
        
    def collect_post_data(self, post: praw.models.Submission) -> Dict[str, Any]:
        """
        Collect comprehensive data about a post
        """
        return {
            'id': post.id,
            'title': post.title,
            'text': post.selftext if post.selftext else "",
            'url': post.url,
            'permalink': f"https://reddit.com{post.permalink}",
            'author': str(post.author),
            'created_utc': post.created_utc,
            'subreddit': post.subreddit.display_name,
            'score': post.score,
            'num_comments': post.num_comments,
            'is_removed': post.removed_by_category is not None,
            'removal_reason': post.removal_reason if hasattr(post, 'removal_reason') else None,
            'removed_by': post.removed_by if hasattr(post, 'removed_by') else None,
            'timestamp': datetime.now().isoformat(),
            'media_type': self._get_media_type(post),
            'media_url': self._get_media_url(post),
            'subreddit_rules': self._get_subreddit_rules(post.subreddit)
        }
    
    def _get_media_type(self, post: praw.models.Submission) -> str:
        """Determine the type of media in the post"""
        if post.is_self:
            return "text"
        elif post.url.endswith(('.jpg', '.jpeg', '.png', '.gif')):
            return "image"
        elif 'imgur.com' in post.url or 'redd.it' in post.url:
            return "image"
        elif 'youtube.com' in post.url or 'youtu.be' in post.url:
            return "video"
        else:
            return "link"
    
    def _get_media_url(self, post: praw.models.Submission) -> str:
        """Get the URL of the media content"""
        if post.is_self:
            return ""
        return post.url
    
    def _get_subreddit_rules(self, subreddit: praw.models.Subreddit) -> List[str]:
        """Get the rules of the subreddit"""
        try:
            return [rule.short_name for rule in subreddit.rules]
        except:
            return []
    
    def monitor_posts(self, limit: int = 100, interval: int = 300, sample_size: int = 50):
        """
        Monitor posts in specified subreddits
        Args:
            limit: Number of posts to check per subreddit
            interval: Time interval between checks in seconds
            sample_size: Number of posts to collect per subreddit per run
        """
        while True:
            for subreddit_name in self.subreddits:
                try:
                    subreddit = self.reddit.subreddit(subreddit_name)
                    print(f"\nChecking r/{subreddit_name}...")
                    
                    # Get new posts
                    new_posts = list(subreddit.new(limit=limit))
                    
                    # Randomly sample posts to ensure diversity
                    sampled_posts = random.sample(new_posts, min(sample_size, len(new_posts)))
                    
                    posts_checked = 0
                    posts_collected = 0
                    
                    for post in sampled_posts:
                        posts_checked += 1
                        
                        # Skip if we've already collected this post
                        if post.id in self.collected_posts:
                            continue
                            
                        if self.debug:
                            print(f"\nProcessing post: {post.title}")
                            print(f"Removed: {post.removed_by_category is not None}")
                        
                        # Collect post data
                        post_data = self.collect_post_data(post)
                        self.posts_data.append(post_data)
                        self.collected_posts.add(post.id)
                        posts_collected += 1
                        
                    print(f"\nSummary for r/{subreddit_name}:")
                    print(f"Posts checked: {posts_checked}")
                    print(f"Posts collected: {posts_collected}")
                    print(f"Total posts in dataset: {len(self.posts_data)}")
                    
                except Exception as e:
                    print(f"Error processing subreddit {subreddit_name}: {str(e)}")
                    
            # Save data to file
            self.save_data()
            
            # Wait for specified interval
            print(f"\nWaiting {interval} seconds before next check...")
            time.sleep(interval)
            
    def save_data(self):
        """
        Save collected post data to a JSON file
        """
        if not self.posts_data:
            print("No posts collected in this run.")
            return
            
        # Create data directory if it doesn't exist
        os.makedirs('data', exist_ok=True)
        
        # Save full dataset
        full_filename = f"data/reddit_posts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(full_filename, 'w', encoding='utf-8') as f:
            json.dump(self.posts_data, f, ensure_ascii=False, indent=2)
        print(f"Full dataset saved to {full_filename}")
        
        # Save statistics
        stats = {
            'total_posts': len(self.posts_data),
            'removed_posts': sum(1 for post in self.posts_data if post['is_removed']),
            'subreddit_distribution': {},
            'media_type_distribution': {}
        }
        
        for post in self.posts_data:
            stats['subreddit_distribution'][post['subreddit']] = stats['subreddit_distribution'].get(post['subreddit'], 0) + 1
            stats['media_type_distribution'][post['media_type']] = stats['media_type_distribution'].get(post['media_type'], 0) + 1
            
        stats_filename = f"data/dataset_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(stats_filename, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        print(f"Dataset statistics saved to {stats_filename}")

def main():
    # Initialize scraper with your Reddit API credentials
    scraper = RedditScraper(
        client_id='YOUR_CLIENT_ID',
        client_secret='YOUR_CLIENT_SECRET',
        user_agent='ContentModerationBot/1.0',
        debug=True
    )
    
    # Add subreddits to monitor - choose a diverse set of subreddits
    scraper.add_subreddit('all')  # Monitor all subreddits
    # Add specific subreddits with different moderation styles
    scraper.add_subreddit('AskReddit')
    scraper.add_subreddit('politics')
    scraper.add_subreddit('memes')
    scraper.add_subreddit('science')
    scraper.add_subreddit('news')
    scraper.add_subreddit('worldnews')
    scraper.add_subreddit('pics')
    scraper.add_subreddit('gaming')
    
    # Start monitoring
    print("Starting Reddit content monitoring...")
    scraper.monitor_posts(
        limit=100,  # Check 100 posts per subreddit
        interval=300,  # Check every 5 minutes
        sample_size=50  # Collect 50 posts per subreddit per run
    )

if __name__ == "__main__":
    main() 