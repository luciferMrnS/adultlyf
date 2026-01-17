"""
SEO Automation Module for Adultlyf
Handles automated SEO optimization including meta tags, sitemaps, keywords, and content optimization.
"""

import json
import os
import random
import re
import requests
from datetime import datetime, timedelta
from collections import Counter
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import threading
import time

from models import db, SEOMetadata, SEOKeyword, SEOPerformance, SEOContent, SEOLink, SEOAutomation
from visitor_analytics import analytics

class SEOAutomationManager:
    """Main SEO automation manager"""

    def __init__(self, app=None):
        self.app = app
        self.base_url = os.environ.get('BASE_URL', 'http://localhost:5000')
        self.keywords_data = self.load_keywords()

    def load_keywords(self):
        """Load keywords from the keywords.json file"""
        try:
            with open('keywords.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def initialize_seo_data(self):
        """Initialize SEO data for the site"""
        with self.app.app_context():
            # Initialize default SEO metadata for main pages
            pages = [
                {'url': '/', 'title': 'Adultlyf - Meet A Girl, Watch Your Show, Stay Horny'},
                {'url': '/escorts', 'title': 'Escort Services - Adultlyf'},
                {'url': '/game.html', 'title': 'Naughty Memory Game - Adultlyf'},
                {'url': '/chat.html', 'title': 'Chat Room - Adultlyf'},
                {'url': '/group_chat.html', 'title': 'Group Chat - Adultlyf'},
            ]

            for page in pages:
                if not SEOMetadata.query.filter_by(page_url=page['url']).first():
                    metadata = SEOMetadata(
                        page_url=page['url'],
                        title=page['title'],
                        description=self.generate_description(page['url']),
                        keywords=json.dumps(self.select_relevant_keywords(page['url'])),
                        h1_tag=page['title'],
                        canonical_url=urljoin(self.base_url, page['url']),
                        og_title=page['title'],
                        og_description=self.generate_description(page['url']),
                        structured_data=json.dumps(self.generate_structured_data(page['url']))
                    )
                    db.session.add(metadata)

            # Initialize keyword tracking
            for keyword in self.keywords_data[:50]:  # Start with first 50 keywords
                if not SEOKeyword.query.filter_by(keyword=keyword).first():
                    seo_keyword = SEOKeyword(
                        keyword=keyword,
                        search_volume=random.randint(1000, 100000),
                        competition_level=random.choice(['low', 'medium', 'high']),
                        monthly_searches=random.randint(100, 50000)
                    )
                    db.session.add(seo_keyword)

            # Initialize automation settings
            automation_types = [
                'meta_update', 'sitemap_generation', 'keyword_refresh',
                'content_optimization', 'performance_tracking', 'link_checking'
            ]

            for automation_type in automation_types:
                if not SEOAutomation.query.filter_by(automation_type=automation_type).first():
                    automation = SEOAutomation(
                        automation_type=automation_type,
                        schedule_interval='daily',
                        settings=json.dumps(self.get_default_settings(automation_type))
                    )
                    automation.calculate_next_run()
                    db.session.add(automation)

            db.session.commit()

    def get_default_settings(self, automation_type):
        """Get default settings for automation types"""
        settings = {
            'meta_update': {
                'title_variations': 5,
                'description_length': 160,
                'keyword_limit': 10
            },
            'sitemap_generation': {
                'include_images': True,
                'include_videos': True,
                'max_urls': 50000
            },
            'keyword_refresh': {
                'update_frequency_days': 7,
                'new_keywords_limit': 10
            },
            'content_optimization': {
                'min_word_count': 300,
                'target_keyword_density': 2.5,
                'internal_links_min': 3
            },
            'performance_tracking': {
                'track_rankings': True,
                'track_backlinks': True,
                'alert_threshold': 10
            },
            'link_checking': {
                'timeout_seconds': 30,
                'max_redirects': 5,
                'check_external_links': False
            }
        }
        return settings.get(automation_type, {})

    def generate_description(self, page_url):
        """Generate SEO-friendly description for a page"""
        descriptions = {
            '/': "Watch the best free adult videos online. We have a huge collection of HD porn videos, updated daily with new content.",
            '/escorts': "Find premium escort services and meet beautiful companions. Safe, discreet, and professional escort booking.",
            '/game.html': "Play our naughty memory game for fun and entertainment. Test your memory with adult-themed challenges.",
            '/chat.html': "Join our adult chat room and connect with like-minded people. Safe and moderated chat environment.",
            '/group_chat.html': "Participate in group discussions and make new friends in our adult community chat."
        }

        base_desc = descriptions.get(page_url, "Adult entertainment and social platform for adults 18+.")
        keywords = self.select_relevant_keywords(page_url)[:3]

        if keywords:
            keyword_text = ", ".join(keywords)
            return f"{base_desc} Featuring {keyword_text} and more."

        return base_desc

    def select_relevant_keywords(self, page_url):
        """Select relevant keywords for a page based on its content type"""
        keyword_sets = {
            '/': ['adult videos', 'free porn', 'HD porn', 'porn videos', 'adult entertainment'],
            '/escorts': ['escort services', 'escort booking', 'premium escorts', 'companion services', 'adult dating'],
            '/game.html': ['adult games', 'naughty games', 'memory game', 'fun games', 'entertainment'],
            '/chat.html': ['adult chat', 'chat room', 'online chat', 'social chat', 'community'],
            '/group_chat.html': ['group chat', 'adult community', 'social network', 'chat groups', 'online friends']
        }

        relevant_keywords = keyword_sets.get(page_url, [])
        # Add some random popular keywords
        additional_keywords = random.sample(self.keywords_data, min(5, len(self.keywords_data)))
        relevant_keywords.extend(additional_keywords)

        return list(set(relevant_keywords))[:10]

    def generate_structured_data(self, page_url):
        """Generate JSON-LD structured data for a page"""
        if page_url == '/':
            return {
                "@context": "https://schema.org",
                "@type": "WebSite",
                "name": "Adultlyf",
                "description": "Adult entertainment platform with videos, escorts, and social features",
                "url": self.base_url,
                "potentialAction": {
                    "@type": "SearchAction",
                    "target": f"{self.base_url}/search.html?q={{search_term_string}}",
                    "query-input": "required name=search_term_string"
                }
            }
        elif page_url.startswith('/escorts'):
            return {
                "@context": "https://schema.org",
                "@type": "Service",
                "name": "Escort Services",
                "description": "Premium escort booking and companion services",
                "provider": {
                    "@type": "Organization",
                    "name": "Adultlyf"
                }
            }
        else:
            return {
                "@context": "https://schema.org",
                "@type": "WebPage",
                "name": "Adultlyf",
                "description": "Adult entertainment platform",
                "url": urljoin(self.base_url, page_url)
            }

    def update_meta_tags(self):
        """Update meta tags for all pages with fresh keywords and descriptions"""
        with self.app.app_context():
            metadata_entries = SEOMetadata.query.all()

            for metadata in metadata_entries:
                # Rotate keywords
                current_keywords = json.loads(metadata.keywords) if metadata.keywords else []
                new_keywords = self.select_relevant_keywords(metadata.page_url)
                # Mix old and new keywords
                combined_keywords = list(set(current_keywords + new_keywords))
                random.shuffle(combined_keywords)
                metadata.keywords = json.dumps(combined_keywords[:10])

                # Update description occasionally
                if random.random() < 0.3:  # 30% chance to update description
                    metadata.description = self.generate_description(metadata.page_url)
                    metadata.og_description = metadata.description

                # Update title variations occasionally
                if random.random() < 0.2:  # 20% chance to update title
                    base_title = metadata.title.split(' - ')[0] if ' - ' in metadata.title else metadata.title
                    variations = [
                        f"{base_title} - Adultlyf",
                        f"Adultlyf - {base_title}",
                        f"{base_title} | Adult Entertainment",
                        f"Free {base_title} - Adultlyf",
                        f"{base_title} - Premium Adult Content"
                    ]
                    metadata.title = random.choice(variations)
                    metadata.og_title = metadata.title

                metadata.last_updated = datetime.utcnow()

            db.session.commit()

    def generate_sitemap(self):
        """Generate XML sitemap for the website"""
        urls = []

        # Add main pages
        main_pages = [
            {'loc': '/', 'priority': '1.0', 'changefreq': 'daily'},
            {'loc': '/escorts', 'priority': '0.8', 'changefreq': 'weekly'},
            {'loc': '/game.html', 'priority': '0.6', 'changefreq': 'monthly'},
            {'loc': '/chat.html', 'priority': '0.7', 'changefreq': 'daily'},
            {'loc': '/group_chat.html', 'priority': '0.7', 'changefreq': 'daily'},
            {'loc': '/player.html', 'priority': '0.5', 'changefreq': 'monthly'},
            {'loc': '/search.html', 'priority': '0.4', 'changefreq': 'monthly'},
            {'loc': '/analytics.html', 'priority': '0.3', 'changefreq': 'weekly'},
        ]

        for page in main_pages:
            urls.append({
                'loc': urljoin(self.base_url, page['loc']),
                'lastmod': datetime.utcnow().strftime('%Y-%m-%d'),
                'priority': page['priority'],
                'changefreq': page['changefreq']
            })

        # Add video pages (limit to avoid huge sitemap)
        try:
            with open('videos.json', 'r') as f:
                videos = json.load(f)[:1000]  # Limit to 1000 videos

            for video in videos:
                video_url = f"/player.html?embed_url={video.get('embed_url', '')}&title={video.get('title', '')}"
                urls.append({
                    'loc': urljoin(self.base_url, video_url),
                    'lastmod': datetime.utcnow().strftime('%Y-%m-%d'),
                    'priority': '0.5',
                    'changefreq': 'weekly'
                })
        except FileNotFoundError:
            pass

        # Generate XML
        sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

        for url in urls:
            sitemap_xml += '  <url>\n'
            sitemap_xml += f'    <loc>{url["loc"]}</loc>\n'
            sitemap_xml += f'    <lastmod>{url["lastmod"]}</lastmod>\n'
            sitemap_xml += f'    <changefreq>{url["changefreq"]}</changefreq>\n'
            sitemap_xml += f'    <priority>{url["priority"]}</priority>\n'
            sitemap_xml += '  </url>\n'

        sitemap_xml += '</urlset>'

        # Save sitemap
        with open('sitemap.xml', 'w', encoding='utf-8') as f:
            f.write(sitemap_xml)

        return len(urls)

    def generate_robots_txt(self):
        """Generate robots.txt file"""
        robots_content = f"""User-agent: *
Allow: /
Allow: /videos.json
Allow: /adverts.json
Allow: /escorts.json
Allow: /group_chat/messages
Allow: /api/analytics

Disallow: /admin/
Disallow: /uploads/
Disallow: /static/age_verification.css
Disallow: /meet
Disallow: /chat/
Disallow: /apply-model

Sitemap: {urljoin(self.base_url, 'sitemap.xml')}

# Adult content warning
# This site contains adult material. Access restricted to users 18+.
"""

        with open('robots.txt', 'w', encoding='utf-8') as f:
            f.write(robots_content)

    def update_keyword_rankings(self):
        """Update keyword ranking data (simulated)"""
        with self.app.app_context():
            keywords = SEOKeyword.query.filter_by(is_active=True).all()

            for keyword in keywords:
                # Simulate ranking changes
                current_ranking = keyword.current_ranking or random.randint(50, 100)
                change = random.randint(-5, 5)
                new_ranking = max(1, current_ranking + change)
                keyword.current_ranking = new_ranking

                # Update search volume occasionally
                if random.random() < 0.3:
                    keyword.search_volume = random.randint(1000, 100000)
                    keyword.monthly_searches = random.randint(100, 50000)

                keyword.last_updated = datetime.utcnow()

            db.session.commit()

    def track_performance(self):
        """Track SEO performance metrics"""
        with self.app.app_context():
            # Get data from analytics
            today = datetime.utcnow().date()
            performance_data = analytics.get_analytics(days=1)

            # Create performance record
            performance = SEOPerformance(
                date=today,
                organic_traffic=int(performance_data.get('total_visitors', 0) * 0.7),  # Estimate organic traffic
                total_traffic=performance_data.get('total_visitors', 0),
                bounce_rate=performance_data.get('bounce_rate', 45.0),
                avg_session_duration=performance_data.get('avg_session_duration', 180.0),
                pages_per_session=performance_data.get('page_views', 2.5),
                new_users_percentage=random.uniform(20, 40),
                top_landing_pages=json.dumps(['/'] * 5),  # Mock data
                top_keywords=json.dumps(random.sample(self.keywords_data, 10)),
                backlinks_count=random.randint(50, 200),
                domain_authority=random.randint(20, 60)
            )

            db.session.add(performance)
            db.session.commit()

    def optimize_content(self):
        """Optimize content for SEO"""
        with self.app.app_context():
            # Get videos for content optimization
            try:
                with open('videos.json', 'r') as f:
                    videos = json.load(f)[:50]  # Process first 50 videos

                for video in videos:
                    # Create or update content optimization record
                    content_record = SEOContent.query.filter_by(
                        content_type='video',
                        content_id=hash(video.get('title', ''))
                    ).first()

                    if not content_record:
                        content_record = SEOContent(
                            content_type='video',
                            content_id=hash(video.get('title', '')),
                            title=video.get('title', ''),
                            content_text=video.get('title', ''),  # Use title as content
                            word_count=len(video.get('title', '').split()),
                            images_count=1 if video.get('thumbnail') else 0,
                            videos_count=1
                        )

                        # Calculate keyword density
                        title_words = video.get('title', '').lower().split()
                        word_freq = Counter(title_words)
                        total_words = len(title_words)
                        density = {}
                        for word, count in word_freq.most_common(10):
                            if len(word) > 3:  # Ignore short words
                                density[word] = (count / total_words) * 100 if total_words > 0 else 0

                        content_record.keyword_density = json.dumps(density)
                        content_record.seo_score = self.calculate_seo_score(content_record)

                        db.session.add(content_record)

                db.session.commit()

            except FileNotFoundError:
                pass

    def calculate_seo_score(self, content):
        """Calculate SEO score for content"""
        score = 0

        # Word count score (ideal: 300-2000 words)
        if 300 <= content.word_count <= 2000:
            score += 20
        elif content.word_count >= 100:
            score += 10

        # Keyword density score
        if content.keyword_density:
            densities = json.loads(content.keyword_density)
            optimal_densities = [d for d in densities.values() if 1.5 <= d <= 3.0]
            if optimal_densities:
                score += 15

        # Internal links score
        if content.internal_links and len(json.loads(content.internal_links)) >= 3:
            score += 15

        # Images score
        if content.images_count > 0:
            score += 10

        # Videos score
        if content.videos_count > 0:
            score += 10

        # Readability score (mock)
        if content.readability_score >= 60:
            score += 10

        return min(score, 100)  # Max score of 100

    def check_links(self):
        """Check internal and external links for broken links"""
        with self.app.app_context():
            links = SEOLink.query.filter_by(link_status='active').all()

            for link in links:
                try:
                    response = requests.head(link.target_url, timeout=10, allow_redirects=True)
                    if response.status_code >= 400:
                        link.link_status = 'broken'
                    elif response.status_code >= 300:
                        link.link_status = 'redirected'
                    else:
                        link.link_status = 'active'
                except:
                    link.link_status = 'broken'

                link.last_checked = datetime.utcnow()

            db.session.commit()

    def run_automated_tasks(self):
        """Run all enabled automated SEO tasks"""
        with self.app.app_context():
            automations = SEOAutomation.query.filter_by(is_enabled=True).all()

            for automation in automations:
                if datetime.utcnow() >= automation.next_run:
                    try:
                        if automation.automation_type == 'meta_update':
                            self.update_meta_tags()
                        elif automation.automation_type == 'sitemap_generation':
                            self.generate_sitemap()
                            self.generate_robots_txt()
                        elif automation.automation_type == 'keyword_refresh':
                            self.update_keyword_rankings()
                        elif automation.automation_type == 'content_optimization':
                            self.optimize_content()
                        elif automation.automation_type == 'performance_tracking':
                            self.track_performance()
                        elif automation.automation_type == 'link_checking':
                            self.check_links()

                        automation.last_run = datetime.utcnow()
                        automation.calculate_next_run()

                    except Exception as e:
                        print(f"Error running {automation.automation_type}: {e}")

            db.session.commit()

    def get_seo_recommendations(self):
        """Get SEO recommendations based on current data"""
        recommendations = []

        with self.app.app_context():
            # Check meta descriptions length
            metadata = SEOMetadata.query.all()
            for meta in metadata:
                if meta.description and len(meta.description) > 160:
                    recommendations.append({
                        'type': 'warning',
                        'message': f"Meta description for {meta.page_url} is too long ({len(meta.description)} chars). Max 160 chars recommended.",
                        'action': 'Shorten meta description'
                    })

            # Check keyword rankings
            poor_keywords = SEOKeyword.query.filter(SEOKeyword.current_ranking > 50).limit(5).all()
            for keyword in poor_keywords:
                recommendations.append({
                    'type': 'info',
                    'message': f"Keyword '{keyword.keyword}' ranks at position {keyword.current_ranking}. Consider content optimization.",
                    'action': 'Optimize content for this keyword'
                })

            # Check content scores
            low_score_content = SEOContent.query.filter(SEOContent.seo_score < 50).limit(3).all()
            for content in low_score_content:
                recommendations.append({
                    'type': 'warning',
                    'message': f"Content '{content.title}' has low SEO score ({content.seo_score}/100). Needs optimization.",
                    'action': 'Improve content SEO'
                })

        return recommendations

    def start_automation_scheduler(self):
        """Start the automation scheduler in a background thread"""
        def scheduler_loop():
            while True:
                try:
                    self.run_automated_tasks()
                except Exception as e:
                    print(f"SEO automation error: {e}")

                # Sleep for 1 hour
                time.sleep(3600)

        thread = threading.Thread(target=scheduler_loop, daemon=True)
        thread.start()

# Global instance
seo_manager = SEOAutomationManager()
