import praw
import time
from datetime import datetime
import json
import os
from threading import Thread
from typing import List, Dict, Any
import logging
from prawcore.exceptions import PrawcoreException
import re
from collections import defaultdict

class RedditScraper:
    def __init__(self, client_id: str, client_secret: str, user_agent: str, debug: bool = False):
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        self.subreddits = []
        self.posts_data = []
        self.collected_posts = set()
        self.post_id_to_content = {}
        self.debug = debug
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO if debug else logging.WARNING,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('reddit_scraper.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 2  # seconds between requests

    def _rate_limit(self):
        """Implement rate limiting to avoid API restrictions"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last_request)
        self.last_request_time = time.time()

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ""
        # Remove URLs
        text = re.sub(r'http\S+', '', text)
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s.,!?-]', '', text)
        # Normalize whitespace
        text = ' '.join(text.split())
        return text.strip()

    def add_subreddit(self, subreddit_name: str):
        self.subreddits.append(subreddit_name)

    def collect_post_data(self, post: praw.models.Submission) -> Dict[str, Any]:
        """Collect comprehensive data about a post with enhanced metadata"""
        try:
            self._rate_limit()
            
            # Get post content
            content = post.selftext if post.selftext else ""
            title = post.title if post.title else ""
            
            # Get comments (limited to top-level)
            comments = []
            try:
                post.comments.replace_more(limit=0)  # Only get top-level comments
                for comment in post.comments.list():
                    if not comment.stickied:
                        comments.append({
                            'id': comment.id,
                            'author': str(comment.author),
                            'body': self._clean_text(comment.body),
                            'score': comment.score,
                            'created_utc': comment.created_utc
                        })
            except Exception as e:
                self.logger.warning(f"Error fetching comments for post {post.id}: {e}")

            return {
                'id': post.id,
                'title': self._clean_text(title),
                'text': self._clean_text(content),
                'url': post.url,
                'permalink': f"https://reddit.com{post.permalink}",
                'author': str(post.author),
                'created_utc': post.created_utc,
                'subreddit': post.subreddit.display_name,
                'score': post.score,
                'num_comments': post.num_comments,
                'is_removed': post.removed_by_category is not None,
                'removal_reason': getattr(post, 'removal_reason', None),
                'removed_by': getattr(post, 'removed_by', None),
                'timestamp_collected': datetime.now().isoformat(),
                'media_type': self._get_media_type(post),
                'media_url': self._get_media_url(post),
                'subreddit_rules': self._get_subreddit_rules(post.subreddit),
                'comments': comments,
                'post_length': len(content),
                'title_length': len(title),
                'has_media': bool(post.url and not post.is_self),
                'is_original_content': getattr(post, 'is_original_content', False),
                'is_self': post.is_self,
                'is_video': getattr(post, 'is_video', False),
                'over_18': getattr(post, 'over_18', False),
                'spoiler': getattr(post, 'spoiler', False),
                'locked': getattr(post, 'locked', False),
                'contest_mode': getattr(post, 'contest_mode', False),
                'num_reports': getattr(post, 'num_reports', 0),
                'upvote_ratio': getattr(post, 'upvote_ratio', 0),
                'total_awards_received': getattr(post, 'total_awards_received', 0)
            }
        except Exception as e:
            self.logger.error(f"Error collecting data for post {post.id}: {e}")
            return None

    def _get_media_type(self, post: praw.models.Submission) -> str:
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
        return "" if post.is_self else post.url

    def _get_subreddit_rules(self, subreddit: praw.models.Subreddit) -> List[str]:
        try:
            return [rule.short_name for rule in subreddit.rules]
        except:
            return []

    def stream_posts(self):
        """Stream posts in real-time with improved error handling"""
        self.logger.info("🔄 Starting real-time post stream...")
        subreddits = '+'.join(self.subreddits)
        
        while True:
            try:
                for post in self.reddit.subreddit(subreddits).stream.submissions(skip_existing=True):
                    if post.id not in self.collected_posts:
                        try:
                            post_data = self.collect_post_data(post)
                            if post_data:
                                self.post_id_to_content[post.id] = post_data
                                self.collected_posts.add(post.id)
                                if self.debug:
                                    self.logger.info(f"[STREAM] Captured post: {post.title}")
                        except Exception as e:
                            self.logger.error(f"[ERROR] Stream error for post {post.id}: {e}")
            except PrawcoreException as e:
                self.logger.error(f"PRAW API error: {e}")
                time.sleep(60)  # Wait a minute before retrying
            except Exception as e:
                self.logger.error(f"Unexpected error in stream: {e}")
                time.sleep(60)

    def check_for_removals(self):
        """Check for removed posts with improved error handling and logging"""
        updated_data = []
        self.logger.info("🕵️ Checking for removed posts...")

        for post_id, cached_data in list(self.post_id_to_content.items()):
            try:
                self._rate_limit()
                post = self.reddit.submission(id=post_id)
                is_removed = post.removed_by_category is not None

                cached_data['is_removed'] = is_removed
                cached_data['removal_reason'] = getattr(post, 'removal_reason', None)
                cached_data['removed_by'] = getattr(post, 'removed_by', None)
                cached_data['timestamp_checked'] = datetime.now().isoformat()

                updated_data.append(cached_data)

                if self.debug:
                    self.logger.info(f"[CHECK] {post_id}: Removed={is_removed}")

                del self.post_id_to_content[post_id]

            except Exception as e:
                self.logger.error(f"[ERROR] Checking {post_id}: {e}")

        if updated_data:
            self.posts_data.extend(updated_data)
            self.save_data()

    def save_data(self):
        """Save data with improved organization and validation"""
        if not self.posts_data:
            self.logger.info("[INFO] No new posts to save.")
            return

        os.makedirs('data', exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Save dataset
        filename = f"data/reddit_posts_{timestamp}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.posts_data, f, ensure_ascii=False, indent=2)
        self.logger.info(f"[SAVE] Dataset saved to {filename}")

        # Enhanced statistics
        stats = {
            'total_posts': len(self.posts_data),
            'removed_posts': sum(1 for p in self.posts_data if p['is_removed']),
            'subreddit_distribution': defaultdict(int),
            'media_type_distribution': defaultdict(int),
            'removal_reasons': defaultdict(int),
            'content_length_stats': {
                'title': {'min': float('inf'), 'max': 0, 'avg': 0},
                'text': {'min': float('inf'), 'max': 0, 'avg': 0}
            },
            'engagement_stats': {
                'score': {'min': float('inf'), 'max': 0, 'avg': 0},
                'comments': {'min': float('inf'), 'max': 0, 'avg': 0}
            }
        }

        total_title_length = 0
        total_text_length = 0
        total_score = 0
        total_comments = 0

        for post in self.posts_data:
            # Basic distributions
            stats['subreddit_distribution'][post['subreddit']] += 1
            stats['media_type_distribution'][post['media_type']] += 1
            if post['removal_reason']:
                stats['removal_reasons'][post['removal_reason']] += 1

            # Content length stats
            title_len = len(post['title'])
            text_len = len(post['text'])
            stats['content_length_stats']['title']['min'] = min(stats['content_length_stats']['title']['min'], title_len)
            stats['content_length_stats']['title']['max'] = max(stats['content_length_stats']['title']['max'], title_len)
            stats['content_length_stats']['text']['min'] = min(stats['content_length_stats']['text']['min'], text_len)
            stats['content_length_stats']['text']['max'] = max(stats['content_length_stats']['text']['max'], text_len)
            total_title_length += title_len
            total_text_length += text_len

            # Engagement stats
            stats['engagement_stats']['score']['min'] = min(stats['engagement_stats']['score']['min'], post['score'])
            stats['engagement_stats']['score']['max'] = max(stats['engagement_stats']['score']['max'], post['score'])
            stats['engagement_stats']['comments']['min'] = min(stats['engagement_stats']['comments']['min'], post['num_comments'])
            stats['engagement_stats']['comments']['max'] = max(stats['engagement_stats']['comments']['max'], post['num_comments'])
            total_score += post['score']
            total_comments += post['num_comments']

        # Calculate averages
        num_posts = len(self.posts_data)
        stats['content_length_stats']['title']['avg'] = total_title_length / num_posts
        stats['content_length_stats']['text']['avg'] = total_text_length / num_posts
        stats['engagement_stats']['score']['avg'] = total_score / num_posts
        stats['engagement_stats']['comments']['avg'] = total_comments / num_posts

        # Convert defaultdict to regular dict for JSON serialization
        stats['subreddit_distribution'] = dict(stats['subreddit_distribution'])
        stats['media_type_distribution'] = dict(stats['media_type_distribution'])
        stats['removal_reasons'] = dict(stats['removal_reasons'])

        stats_file = f"data/dataset_stats_{timestamp}.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        self.logger.info(f"[SAVE] Stats saved to {stats_file}")

        # Clear memory
        self.posts_data = []

def main():
    # Initialize scraper with environment variables
    scraper = RedditScraper(
        client_id=os.environ.get("CLIENT_ID"),
        client_secret=os.environ.get("CLIENT_SECRET"),
        user_agent="RemovedPostScraper/1.0",
        debug=True
    )

    # Add subreddits
    scraper.add_subreddit('AskReddit')
    scraper.add_subreddit('politics')
    scraper.add_subreddit('memes')
    scraper.add_subreddit('science')
    scraper.add_subreddit('news')
    scraper.add_subreddit('worldnews')
    scraper.add_subreddit('pics')
    scraper.add_subreddit('gaming')

    # Start real-time capture in a thread
    Thread(target=scraper.stream_posts, daemon=True).start()

    # Periodic check loop
    while True:
        scraper.check_for_removals()
        time.sleep(300)  # Check every 5 minutes

if __name__ == "__main__":
    main()
