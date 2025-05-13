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
        self.post_tracking_start = {}  # Track when we started monitoring each post
        self.tracking_duration = 24 * 60 * 60  # Track posts for 24 hours
        self.debug = debug
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO if debug else logging.WARNING,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('reddit_scraper.log', encoding='utf-8'),
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
        """Clean and normalize text content while preserving URLs"""
        if not text:
            return ""
        
        # Extract URLs before cleaning
        urls = re.findall(r'http\S+', text)
        
        # Clean text but preserve URLs
        # Remove special characters but keep basic punctuation and URLs
        text = re.sub(r'[^\w\s.,!?\-:/]', '', text)
        # Normalize whitespace
        text = ' '.join(text.split())
        
        return text.strip()

    def add_subreddit(self, subreddit_name: str):
        self.subreddits.append(subreddit_name)

    def _get_subreddit_rules(self, subreddit: praw.models.Subreddit) -> List[Dict[str, Any]]:
        """Get detailed rules of the subreddit"""
        rules_data = []
        try:
            for rule in subreddit.rules:
                rules_data.append({
                    'short_name': rule.short_name,
                    'description': rule.description,
                    'kind': rule.kind,  # e.g., 'all', 'link', 'comment'
                    'priority': rule.priority,
                    'violation_reason': rule.violation_reason  # Text used in report forms
                })
            return rules_data
        except Exception as e:
            self.logger.error(f"Error fetching rules for subreddit {subreddit.display_name}: {e}")
            return []

    def _get_media_info(self, post: praw.models.Submission) -> Dict[str, Any]:
        """Get comprehensive media information from a post"""
        media_type = "text"
        image_urls = []
        video_url = None

        try:
            # Check for gallery posts
            if hasattr(post, 'gallery_data') and post.gallery_data:
                media_type = "gallery"
                for item in post.gallery_data['items']:
                    media_id = item['media_id']
                    if hasattr(post, 'media_metadata') and media_id in post.media_metadata:
                        item_meta = post.media_metadata[media_id]
                        if item_meta.get('e') == 'Image':
                            if item_meta.get('s', {}).get('u'):
                                image_urls.append(item_meta['s']['u'].replace('&amp;', '&'))
                            elif item_meta.get('p'):
                                image_urls.append(item_meta['p'][-1]['u'].replace('&amp;', '&'))
            # Check for regular media posts
            elif not post.is_self and post.url:
                if post.url.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    media_type = "image"
                    image_urls.append(post.url)
                elif 'imgur.com' in post.url or 'redd.it' in post.url and not getattr(post, 'is_video', False):
                    media_type = "image"
                    image_urls.append(post.url)
                elif 'youtube.com' in post.url or 'youtu.be' in post.url or getattr(post, 'is_video', False):
                    media_type = "video"
                    video_url = post.url
                else:
                    media_type = "link"

            return {
                'media_type': media_type,
                'image_urls': image_urls,
                'video_url': video_url,
                'original_url': post.url if not post.is_self else None
            }
        except Exception as e:
            self.logger.warning(f"Error processing media for post {post.id}: {e}")
            return {
                'media_type': "text",
                'image_urls': [],
                'video_url': None,
                'original_url': post.url if not post.is_self else None
            }

    def collect_post_data(self, post: praw.models.Submission) -> Dict[str, Any]:
        """Collect comprehensive data about a post with enhanced metadata"""
        try:
            self._rate_limit()
            
            # Get post content
            content = post.selftext if post.selftext else ""
            title = post.title if post.title else ""
            
            # Extract URLs from content
            content_urls = re.findall(r'http\S+', content)
            title_urls = re.findall(r'http\S+', title)
            
            # Get comments (limited to top-level)
            comments = []
            try:
                post.comments.replace_more(limit=0)  # Only get top-level comments
                for comment in post.comments.list():
                    if not comment.stickied:
                        comment_body = comment.body if comment.body else ""
                        comment_urls = re.findall(r'http\S+', comment_body)
                        comments.append({
                            'id': comment.id,
                            'author': str(comment.author),
                            'body': self._clean_text(comment_body),
                            'urls': comment_urls,
                            'score': comment.score,
                            'created_utc': comment.created_utc,
                            'is_removed': comment_body in ["[removed]", "[deleted]"],
                            'removal_reason': getattr(comment, 'removal_reason', None)
                        })
            except Exception as e:
                self.logger.warning(f"Error fetching comments for post {post.id}: {e}")

            # Get media information
            media_info = self._get_media_info(post)

            # Get removal information
            removal_info = {
                'is_removed': post.removed_by_category is not None,
                'removal_reason': getattr(post, 'removal_reason', None),
                'removed_by': getattr(post, 'removed_by', None),
                'raw_removed_by_category': getattr(post, 'removed_by_category', None),
                'raw_banned_by': getattr(post, 'banned_by', None),
                'raw_author_is_none': post.author is None,
                'raw_selftext_value': post.selftext if post.selftext in ["[removed]", "[deleted]"] else None,
                'approved_by': str(getattr(post, 'approved_by', None)),
                'approved_at_utc': getattr(post, 'approved_at_utc', None)
            }

            post_data = {
                'id': post.id,
                'title': self._clean_text(title),
                'text': self._clean_text(content),
                'urls': {
                    'content': content_urls,
                    'title': title_urls,
                    'total': len(content_urls) + len(title_urls)
                },
                'permalink': f"https://reddit.com{post.permalink}",
                'author': str(post.author),
                'created_utc': post.created_utc,
                'subreddit': post.subreddit.display_name,
                'score': post.score,
                'num_comments': post.num_comments,
                'timestamp_collected': datetime.now().isoformat(),
                'comments': comments,
                'post_length': len(content),
                'title_length': len(title),
                'is_self': post.is_self,
                'is_video': getattr(post, 'is_video', False),
                'over_18': getattr(post, 'over_18', False),
                'spoiler': getattr(post, 'spoiler', False),
                'locked': getattr(post, 'locked', False),
                'contest_mode': getattr(post, 'contest_mode', False),
                'num_reports': getattr(post, 'num_reports', 0),
                'upvote_ratio': getattr(post, 'upvote_ratio', 0),
                'total_awards_received': getattr(post, 'total_awards_received', 0),
                'subreddit_rules': self._get_subreddit_rules(post.subreddit),
                **media_info,
                **removal_info
            }
            
            # Store the post data and track when we started monitoring it
            self.post_id_to_content[post.id] = post_data
            self.post_tracking_start[post.id] = time.time()
            
            return post_data
        except Exception as e:
            self.logger.error(f"Error collecting data for post {post.id}: {e}")
            return None

    def stream_posts(self):
        """Stream posts in real-time with improved error handling"""
        self.logger.info("Starting real-time post stream...")
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
        self.logger.info("Checking for removed posts...")
        current_time = time.time()

        for post_id, cached_data in list(self.post_id_to_content.items()):
            try:
                # Check if we should stop tracking this post
                tracking_start = self.post_tracking_start[post_id]
                if current_time - tracking_start > self.tracking_duration:
                    if self.debug:
                        self.logger.info(f"[TRACKING] Stopping tracking for post {post_id} after {self.tracking_duration/3600:.1f} hours")
                    updated_data.append(cached_data)
                    del self.post_id_to_content[post_id]
                    del self.post_tracking_start[post_id]
                    continue

                self._rate_limit()
                post = self.reddit.submission(id=post_id)
                
                # Update removal information
                cached_data.update({
                    'is_removed': post.removed_by_category is not None,
                    'removal_reason': getattr(post, 'removal_reason', None),
                    'removed_by': getattr(post, 'removed_by', None),
                    'raw_removed_by_category': getattr(post, 'removed_by_category', None),
                    'raw_banned_by': getattr(post, 'banned_by', None),
                    'raw_author_is_none': post.author is None,
                    'raw_selftext_value': post.selftext if post.selftext in ["[removed]", "[deleted]"] else None,
                    'approved_by': str(getattr(post, 'approved_by', None)),
                    'approved_at_utc': getattr(post, 'approved_at_utc', None),
                    'timestamp_checked': datetime.now().isoformat(),
                    'hours_tracked': (current_time - tracking_start) / 3600
                })

                # If the post is removed, stop tracking it
                if cached_data['is_removed']:
                    if self.debug:
                        self.logger.info(f"[REMOVED] Post {post_id} was removed after {cached_data['hours_tracked']:.1f} hours")
                    updated_data.append(cached_data)
                    del self.post_id_to_content[post_id]
                    del self.post_tracking_start[post_id]
                else:
                    # Update the cached data with new information
                    self.post_id_to_content[post_id] = cached_data

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
            'removal_rate': sum(1 for p in self.posts_data if p['is_removed']) / len(self.posts_data) * 100,
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
            },
            'removal_stats': {
                'by_reason': defaultdict(int),
                'by_subreddit': defaultdict(int),
                'by_media_type': defaultdict(int),
                'by_url_count': defaultdict(int)  # Track removals by number of URLs
            },
            'url_stats': {
                'posts_with_urls': 0,
                'total_urls': 0,
                'urls_in_removed_posts': 0,
                'url_domains': defaultdict(int)  # Track common URL domains
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
            
            # URL statistics
            url_count = post['urls']['total']
            if url_count > 0:
                stats['url_stats']['posts_with_urls'] += 1
                stats['url_stats']['total_urls'] += url_count
                
                # Track URL domains
                for url in post['urls']['content'] + post['urls']['title']:
                    try:
                        from urllib.parse import urlparse
                        domain = urlparse(url).netloc
                        stats['url_stats']['url_domains'][domain] += 1
                    except:
                        continue

            # Removal statistics
            if post['is_removed']:
                if post['removal_reason']:
                    stats['removal_stats']['by_reason'][post['removal_reason']] += 1
                stats['removal_stats']['by_subreddit'][post['subreddit']] += 1
                stats['removal_stats']['by_media_type'][post['media_type']] += 1
                stats['removal_stats']['by_url_count'][url_count] += 1
                if url_count > 0:
                    stats['url_stats']['urls_in_removed_posts'] += url_count

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
        stats['removal_stats']['by_reason'] = dict(stats['removal_stats']['by_reason'])
        stats['removal_stats']['by_subreddit'] = dict(stats['removal_stats']['by_subreddit'])
        stats['removal_stats']['by_media_type'] = dict(stats['removal_stats']['by_media_type'])
        stats['removal_stats']['by_url_count'] = dict(stats['removal_stats']['by_url_count'])
        stats['url_stats']['url_domains'] = dict(stats['url_stats']['url_domains'])

        # Log removal rate
        self.logger.info(f"Removal rate: {stats['removal_rate']:.2f}% ({stats['removed_posts']} removed out of {stats['total_posts']} total posts)")
        if stats['url_stats']['posts_with_urls'] > 0:
            url_removal_rate = (stats['url_stats']['urls_in_removed_posts'] / stats['url_stats']['total_urls']) * 100
            self.logger.info(f"URL removal rate: {url_removal_rate:.2f}% ({stats['url_stats']['urls_in_removed_posts']} URLs in removed posts out of {stats['url_stats']['total_urls']} total URLs)")

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
        user_agent="Python:RemovedPostScraper:v1.0 (by /u/RemovedPostScraper)",
        debug=True
    )

    # Add subreddits with higher likelihood of removals
    scraper.add_subreddit('AskReddit')
    scraper.add_subreddit('politics')
    scraper.add_subreddit('news')
    scraper.add_subreddit('worldnews')
    scraper.add_subreddit('Advice')
    scraper.add_subreddit('legaladvice')
    scraper.add_subreddit('relationship_advice')
    scraper.add_subreddit('science')
    scraper.add_subreddit('AskHistorians')
    scraper.add_subreddit('Crypto')
    scraper.add_subreddit('personalfinance')
    scraper.add_subreddit('programming')
    scraper.add_subreddit('technology')
    scraper.add_subreddit('Pyongyang')
    scraper.add_subreddit('askscience')

    # Start real-time capture in a thread
    Thread(target=scraper.stream_posts, daemon=True).start()

    # Periodic check loop
    while True:
        scraper.check_for_removals()
        time.sleep(300)  # Check every 5 minutes

if __name__ == "__main__":
    main()
