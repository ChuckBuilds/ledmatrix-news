"""
News Ticker Plugin for LEDMatrix

Displays scrolling news headlines from RSS feeds including sports news from ESPN,
NCAA updates, and custom RSS sources. Shows breaking news and updates in a
continuous scrolling ticker format.

Features:
- Multiple RSS feed sources (ESPN, NCAA, custom feeds)
- Scrolling headline display
- Headline rotation and cycling
- Custom feed support
- Configurable scroll speed and colors
- Background data fetching

API Version: 1.0.0
"""

import logging
import time
import requests
import xml.etree.ElementTree as ET
import html
import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from src.plugin_system.base_plugin import BasePlugin
from src.common.scroll_helper import ScrollHelper
from src.common.logo_helper import LogoHelper

logger = logging.getLogger(__name__)


class NewsTickerPlugin(BasePlugin):
    """
    News ticker plugin for displaying scrolling headlines from RSS feeds.

    Supports multiple predefined feeds (ESPN sports, NCAA) and custom RSS URLs
    with configurable display options and scrolling ticker format.

    Configuration options:
        feeds: Enable/disable predefined and custom RSS feeds
        display_options: Scroll speed, duration, colors, rotation
        background_service: Data fetching configuration
    """

    # Default RSS feeds
    DEFAULT_FEEDS = {
        'MLB': 'http://espn.com/espn/rss/mlb/news',
        'NFL': 'http://espn.go.com/espn/rss/nfl/news',
        'NCAA FB': 'https://www.espn.com/espn/rss/ncf/news',
        'NHL': 'https://www.espn.com/espn/rss/nhl/news',
        'NBA': 'https://www.espn.com/espn/rss/nba/news',
        'TOP SPORTS': 'https://www.espn.com/espn/rss/news',
        'BIG10': 'https://www.espn.com/blog/feed?blog=bigten',
        'NCAA': 'https://www.espn.com/espn/rss/ncaa/news',
        'Other': 'https://www.coveringthecorner.com/rss/current.xml'
    }

    # Feed name to logo file mapping
    FEED_LOGO_MAP = {
        'MLB': 'mlbn.png',  # MLB Network logo
        'NFL': 'nfln.png',  # NFL Network logo
        'NCAA FB': 'espn.png',  # ESPN logo
        'NHL': 'espn.png',  # ESPN logo
        'NBA': 'espn.png',  # ESPN logo
        'TOP SPORTS': 'espn.png',  # ESPN logo
        'BIG10': 'espn.png',  # ESPN logo
        'NCAA': 'espn.png',  # ESPN logo
        'Other': 'espn.png'  # Default to ESPN
    }

    def __init__(self, plugin_id: str, config: Dict[str, Any],
                 display_manager, cache_manager, plugin_manager):
        """Initialize the news ticker plugin."""
        super().__init__(plugin_id, config, display_manager, cache_manager, plugin_manager)

        # Get display dimensions
        self.display_width = display_manager.width
        self.display_height = display_manager.height

        # Configuration
        self.feeds_config = config.get('feeds', {})
        self.global_config = config.get('global', {})

        # Display settings
        self.display_duration = self.global_config.get('display_duration', 30)
        
        # Scroll configuration - prefer display object (frame-based), fallback to legacy
        display_config = self.global_config.get('display', {})
        if display_config and ('scroll_speed' in display_config or 'scroll_delay' in display_config):
            # New format: use frame-based scrolling
            self.scroll_speed = display_config.get('scroll_speed', 1.0)
            self.scroll_delay = display_config.get('scroll_delay', 0.01)
            self.scroll_pixels_per_second = None
            self.logger.info(f"Using global.display.scroll_speed={self.scroll_speed} px/frame, global.display.scroll_delay={self.scroll_delay}s (frame-based mode)")
        else:
            # Legacy format: use global scroll_speed/scroll_delay
            self.scroll_speed = self.global_config.get('scroll_speed', 1.0)
            self.scroll_delay = self.global_config.get('scroll_delay', 0.01)
            self.scroll_pixels_per_second = self.global_config.get('scroll_pixels_per_second')
            if self.scroll_pixels_per_second is not None:
                self.logger.info(f"Using scroll_pixels_per_second={self.scroll_pixels_per_second} px/s (time-based mode)")
            else:
                self.logger.info(f"Using legacy scroll_speed={self.scroll_speed}, scroll_delay={self.scroll_delay}")

        # Dynamic duration settings
        dynamic_duration_config = self.global_config.get('dynamic_duration', {})
        if isinstance(dynamic_duration_config, bool):
            # Legacy: just a boolean
            self.dynamic_duration_enabled = dynamic_duration_config
            self.min_duration = self.global_config.get('min_duration', 30)
            self.max_duration = self.global_config.get('max_duration', 300)
            self.duration_buffer = self.global_config.get('duration_buffer', 0.1)
        else:
            # New format: object with settings
            self.dynamic_duration_enabled = dynamic_duration_config.get('enabled', True)
            self.min_duration = dynamic_duration_config.get('min_duration_seconds', 30)
            self.max_duration = dynamic_duration_config.get('max_duration_seconds', 300)
            self.duration_buffer = dynamic_duration_config.get('buffer_ratio', 0.1)

        self.rotation_enabled = self.global_config.get('rotation_enabled', True)
        self.rotation_threshold = self.global_config.get('rotation_threshold', 3)
        self.headlines_per_feed = self.global_config.get('headlines_per_feed', 2)
        self.font_size = self.global_config.get('font_size', 12)
        self.target_fps = self.global_config.get('target_fps') or self.global_config.get('scroll_target_fps', 100)

        # Colors
        self.text_color = tuple(self.feeds_config.get('text_color', [255, 255, 255]))
        self.separator_color = tuple(self.feeds_config.get('separator_color', [255, 0, 0]))

        # Logo settings
        self.show_logos = self.feeds_config.get('show_logos', True)
        # Logo size defaults to display height minus 4 pixels for margin, but can be overridden
        default_logo_size = self.display_height - 4 if self.display_height > 4 else self.display_height
        self.logo_size = self.feeds_config.get('logo_size', default_logo_size)
        
        # Feed logo mapping - allows users to specify custom logo file names per feed
        # Format: {"Feed Name": "logo_filename.png"}
        self.feed_logo_map = self.feeds_config.get('feed_logo_map', {})

        # Background service configuration
        self.background_config = self.global_config.get('background_service', {
            'enabled': True,
            'request_timeout': 30,
            'max_retries': 3,
            'priority': 2
        })

        # State
        self.current_headlines = []
        self.last_update = 0
        self.rotation_count = 0
        self._cycle_complete = False
        self.initialized = True

        # Load fonts
        self.fonts = self._load_fonts()

        # Initialize LogoHelper for news source logos
        self.logo_helper = LogoHelper(
            display_width=self.display_width,
            display_height=self.display_height,
            logger=self.logger
        )

        # Initialize ScrollHelper
        self.scroll_helper = ScrollHelper(self.display_width, self.display_height, logger=self.logger)
        
        # Enable scrolling for high FPS mode
        self.enable_scrolling = True

        # Configure ScrollHelper with plugin settings
        use_frame_based = (self.scroll_pixels_per_second is None and 
                          display_config and 
                          ('scroll_speed' in display_config or 'scroll_delay' in display_config))

        if use_frame_based:
            # Frame-based scrolling
            if hasattr(self.scroll_helper, 'set_frame_based_scrolling'):
                self.scroll_helper.set_frame_based_scrolling(True)
            self.scroll_helper.set_scroll_speed(self.scroll_speed)
            self.scroll_helper.set_scroll_delay(self.scroll_delay)
            pixels_per_second = self.scroll_speed / self.scroll_delay if self.scroll_delay > 0 else self.scroll_speed * 100
            self.logger.info(f"Effective scroll speed: {pixels_per_second:.1f} px/s ({self.scroll_speed} px/frame at {1.0/self.scroll_delay:.0f} FPS)")
        else:
            # Time-based scrolling (backward compatibility)
            if self.scroll_pixels_per_second is not None:
                pixels_per_second = self.scroll_pixels_per_second
            else:
                pixels_per_second = self.scroll_speed / self.scroll_delay if self.scroll_delay > 0 else self.scroll_speed * 100
            self.scroll_helper.set_scroll_speed(pixels_per_second)
            self.scroll_helper.set_scroll_delay(self.scroll_delay)

        # Set target FPS
        if hasattr(self.scroll_helper, 'set_target_fps'):
            self.scroll_helper.set_target_fps(self.target_fps)
        else:
            self.scroll_helper.target_fps = max(30.0, min(200.0, self.target_fps))
            self.scroll_helper.frame_time_target = 1.0 / self.scroll_helper.target_fps

        # Configure dynamic duration
        self.scroll_helper.set_dynamic_duration_settings(
            enabled=self.dynamic_duration_enabled,
            min_duration=self.min_duration,
            max_duration=self.max_duration,
            buffer=self.duration_buffer
        )

        # Log enabled feeds
        enabled_feeds = self.feeds_config.get('enabled_feeds', [])
        custom_feeds = list(self.feeds_config.get('custom_feeds', {}).keys())

        self.logger.info("News ticker plugin initialized")
        self.logger.info(f"Enabled predefined feeds: {enabled_feeds}")
        self.logger.info(f"Custom feeds: {custom_feeds}")
        self.logger.info(f"Display dimensions: {self.display_width}x{self.display_height}")
        if hasattr(self.scroll_helper, 'frame_based_scrolling') and self.scroll_helper.frame_based_scrolling:
            pixels_per_second = self.scroll_speed / self.scroll_delay if self.scroll_delay > 0 else self.scroll_speed * 100
            self.logger.info(f"Scroll speed: {self.scroll_speed} px/frame, {self.scroll_delay}s delay ({pixels_per_second:.1f} px/s effective)")
        else:
            if hasattr(self, 'scroll_pixels_per_second') and self.scroll_pixels_per_second is not None:
                self.logger.info(f"Scroll speed: {self.scroll_pixels_per_second} px/s")
            else:
                pixels_per_second = self.scroll_speed / self.scroll_delay if self.scroll_delay > 0 else self.scroll_speed * 100
                self.logger.info(f"Scroll speed: {pixels_per_second:.1f} px/s")
        self.logger.info(
            "Dynamic duration settings: enabled=%s, min=%ss, max=%ss, buffer=%.2f",
            self.dynamic_duration_enabled,
            self.min_duration,
            self.max_duration,
            self.duration_buffer,
        )

    def _load_fonts(self) -> Dict[str, ImageFont.FreeTypeFont]:
        """Load fonts for the news ticker display."""
        fonts = {}
        try:
            # Try to load Press Start 2P font
            font_path = self.global_config.get('font_path', 'assets/fonts/PressStart2P-Regular.ttf')
            fonts['headline'] = ImageFont.truetype(font_path, self.font_size)
            fonts['separator'] = ImageFont.truetype(font_path, self.font_size)
            fonts['info'] = ImageFont.truetype(font_path, 6)
            self.logger.info("Successfully loaded Press Start 2P font")
        except IOError:
            self.logger.warning("Press Start 2P font not found, trying 4x6 font")
            try:
                fonts['headline'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", self.font_size)
                fonts['separator'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", self.font_size)
                fonts['info'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 6)
                self.logger.info("Successfully loaded 4x6 font")
            except IOError:
                self.logger.warning("4x6 font not found, using default PIL font")
                default_font = ImageFont.load_default()
                fonts = {
                    'headline': default_font,
                    'separator': default_font,
                    'info': default_font
                }
        except Exception as e:
            self.logger.error(f"Error loading fonts: {e}")
            default_font = ImageFont.load_default()
            fonts = {
                'headline': default_font,
                'separator': default_font,
                'info': default_font
            }
        return fonts

    def validate_config(self) -> bool:
        """Validate plugin configuration."""
        # Call parent validation first
        if not super().validate_config():
            return False
        
        # Validate feeds configuration
        if not isinstance(self.feeds_config, dict):
            self.logger.error("feeds configuration must be a dictionary")
            return False
        
        # Validate enabled_feeds is a list if present
        enabled_feeds = self.feeds_config.get('enabled_feeds', [])
        if not isinstance(enabled_feeds, list):
            self.logger.error("enabled_feeds must be a list")
            return False
        
        # Validate custom_feeds is a dict if present
        custom_feeds = self.feeds_config.get('custom_feeds', {})
        if not isinstance(custom_feeds, dict):
            self.logger.error("custom_feeds must be a dictionary")
            return False
        
        # Validate global configuration
        if not isinstance(self.global_config, dict):
            self.logger.error("global configuration must be a dictionary")
            return False
        
        return True

    def update(self) -> None:
        """Update news headlines from all enabled feeds."""
        if not self.initialized:
            return

        try:
            self.current_headlines = []

            # Fetch from enabled predefined feeds
            enabled_feeds = self.feeds_config.get('enabled_feeds', [])
            for feed_name in enabled_feeds:
                if feed_name in self.DEFAULT_FEEDS:
                    headlines = self._fetch_feed_headlines(feed_name, self.DEFAULT_FEEDS[feed_name])
                    if headlines:
                        self.current_headlines.extend(headlines)

            # Fetch from custom feeds
            custom_feeds = self.feeds_config.get('custom_feeds', {})
            for feed_name, feed_url in custom_feeds.items():
                headlines = self._fetch_feed_headlines(feed_name, feed_url)
                if headlines:
                    self.current_headlines.extend(headlines)

            # Limit total headlines and reset rotation tracking
            max_headlines = len(enabled_feeds) * self.headlines_per_feed + len(custom_feeds) * self.headlines_per_feed
            if len(self.current_headlines) > max_headlines:
                self.current_headlines = self.current_headlines[:max_headlines]

            # Reset rotation tracking for new content
            if self.current_headlines:
                self.rotation_count = 0
                # Clear scroll cache to force recreation of scrolling image
                if hasattr(self, 'scroll_helper'):
                    self.scroll_helper.clear_cache()

            self.last_update = time.time()
            self.logger.debug(f"Updated news headlines: {len(self.current_headlines)} total")

        except Exception as e:
            self.logger.error(f"Error updating news headlines: {e}")

    def _fetch_feed_headlines(self, feed_name: str, feed_url: str) -> List[Dict]:
        """Fetch headlines from a specific RSS feed."""
        cache_key = f"news_{feed_name}_{datetime.now().strftime('%Y%m%d%H')}"
        update_interval = self.global_config.get('update_interval_seconds', 300)

        # Check cache first
        cached_data = self.cache_manager.get(cache_key)
        if cached_data and (time.time() - self.last_update) < update_interval:
            self.logger.debug(f"Using cached headlines for {feed_name}")
            return cached_data

        try:
            self.logger.info(f"Fetching headlines from {feed_name}...")
            response = requests.get(feed_url, timeout=self.background_config.get('request_timeout', 30))
            response.raise_for_status()

            # Parse RSS XML
            root = ET.fromstring(response.content)
            headlines = []

            # Extract headlines from RSS items
            for item in root.findall('.//item')[:self.headlines_per_feed]:
                title = item.find('title')
                description = item.find('description')
                pub_date = item.find('pubDate')
                link = item.find('link')

                if title is not None and title.text:
                    headline = {
                        'feed_name': feed_name,
                        'title': html.unescape(title.text).strip(),
                        'description': html.unescape(description.text).strip() if description is not None else '',
                        'published': pub_date.text if pub_date is not None else '',
                        'link': link.text if link is not None else '',
                        'timestamp': datetime.now().isoformat()
                    }

                    # Clean up the title (remove extra whitespace, fix common issues)
                    headline['title'] = self._clean_headline(headline['title'])
                    headlines.append(headline)

            # Cache the results
            self.cache_manager.set(cache_key, headlines, ttl=update_interval * 2)

            return headlines

        except requests.RequestException as e:
            self.logger.error(f"Error fetching RSS feed {feed_name}: {e}")
            return []
        except ET.ParseError as e:
            self.logger.error(f"Error parsing RSS feed {feed_name}: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Error processing RSS feed {feed_name}: {e}")
            return []

    def _clean_headline(self, headline: str) -> str:
        """Clean and format headline text."""
        if not headline:
            return ""

        # Remove extra whitespace
        headline = re.sub(r'\s+', ' ', headline.strip())

        # Remove common artifacts
        headline = re.sub(r'^\s*-\s*', '', headline)  # Remove leading dashes
        headline = re.sub(r'\s+', ' ', headline)  # Normalize whitespace

        # Limit length for display
        if len(headline) > 100:
            headline = headline[:97] + "..."

        return headline

    def display(self, display_mode: str = None, force_clear: bool = False) -> None:
        """
        Display scrolling news headlines.

        Args:
            display_mode: Should be 'news_ticker'
            force_clear: If True, clear display before rendering
        """
        if not self.initialized:
            self._display_error("News ticker plugin not initialized")
            return

        if not self.current_headlines:
            self._display_no_headlines()
            return

        # Create scrolling image if needed
        if not self.scroll_helper.cached_image or force_clear:
            self.logger.info("Creating news ticker image...")
            self._create_scrolling_image()
            if not self.scroll_helper.cached_image:
                self.logger.error("Failed to create news ticker image, showing fallback")
                self._display_no_headlines()
                return
            self.logger.info("News ticker image created successfully")
            self._cycle_complete = False

        if force_clear:
            self.scroll_helper.reset_scroll()
            self._cycle_complete = False

        # Signal scrolling state
        self.display_manager.set_scrolling_state(True)
        self.display_manager.process_deferred_updates()

        # Update scroll position using the scroll helper
        self.scroll_helper.update_scroll_position()
        if self.dynamic_duration_enabled and self.scroll_helper.is_scroll_complete():
            if not self._cycle_complete:
                scroll_info = self.scroll_helper.get_scroll_info()
                elapsed_time = scroll_info.get('elapsed_time')
                self.logger.info(
                    "News ticker scroll cycle completed (elapsed=%.2fs, target=%.2fs)",
                    elapsed_time if elapsed_time is not None else -1.0,
                    scroll_info.get('dynamic_duration'),
                )
            self._cycle_complete = True

        # Get visible portion
        visible_portion = self.scroll_helper.get_visible_portion()
        if visible_portion:
            # Update display
            self.display_manager.image.paste(visible_portion, (0, 0))
            self.display_manager.update_display()

        # Log frame rate (less frequently to avoid spam)
        self.scroll_helper.log_frame_rate()

    def _create_scrolling_image(self) -> None:
        """Create the scrolling news ticker image."""
        try:
            # Create PIL Images for each headline
            headline_images = []
            for headline in self.current_headlines:
                headline_img = self._render_headline(headline)
                if headline_img:
                    headline_images.append(headline_img)

            if not headline_images:
                self.logger.warning("No headline images created")
                self.scroll_helper.clear_cache()
                return

            # Use ScrollHelper to create the scrolling image
            self.scroll_helper.create_scrolling_image(
                headline_images,
                item_gap=32,  # Gap between headlines
                element_gap=16  # Gap within headline elements
            )
            # Dynamic duration is automatically calculated by create_scrolling_image()
            self._cycle_complete = False

            self.logger.info(f"Created news ticker image with {len(headline_images)} headlines")
            self.logger.info(f"Dynamic duration: {self.scroll_helper.get_dynamic_duration()}s")

        except Exception as e:
            self.logger.error(f"Error creating news ticker image: {e}")
            self.scroll_helper.clear_cache()

    def _get_feed_logo_path(self, feed_name: str) -> Optional[Path]:
        """
        Get the path to a feed's logo file.
        
        Priority order:
        1. User-configured feed_logo_map (custom logo file names)
        2. Predefined FEED_LOGO_MAP
        3. Infer from feed name
        4. Default fallback
        
        Checks directories in order:
        1. assets/news_logos/ (primary location for news logos)
        2. assets/broadcast_logos/ (fallback for broadcast network logos)
        3. Plugin assets/logos/ (plugin-specific logos)
        """
        # First check user-configured logo map
        logo_filename = self.feed_logo_map.get(feed_name)
        
        # If not in user config, check predefined mapping
        if not logo_filename:
            logo_filename = self.FEED_LOGO_MAP.get(feed_name)
        
        # If still not found, try to infer from feed name
        if not logo_filename:
            feed_lower = feed_name.lower()
            if 'espn' in feed_lower:
                logo_filename = 'espn.png'
            elif 'nfl' in feed_lower:
                logo_filename = 'nfln.png'
            elif 'mlb' in feed_lower:
                logo_filename = 'mlbn.png'
            elif 'nba' in feed_lower or 'nhl' in feed_lower or 'ncaa' in feed_lower:
                logo_filename = 'espn.png'
            else:
                # Try using feed name as filename (normalized)
                # Remove spaces and special chars, convert to lowercase
                normalized = re.sub(r'[^a-zA-Z0-9]', '_', feed_name.lower())
                logo_filename = f"{normalized}.png"
        
        # Check directories in priority order
        project_root = Path(__file__).parent.parent.parent
        plugin_assets = Path(__file__).parent / 'assets' / 'logos'
        
        search_dirs = [
            project_root / 'assets' / 'news_logos',  # Primary location
            project_root / 'assets' / 'broadcast_logos',  # Fallback
            plugin_assets  # Plugin-specific
        ]
        
        for assets_dir in search_dirs:
            logo_path = assets_dir / logo_filename
            if logo_path.exists():
                self.logger.debug(f"Found logo for {feed_name} at {logo_path}")
                return logo_path
        
        self.logger.debug(f"No logo found for {feed_name} (searched for {logo_filename})")
        return None

    def _render_headline(self, headline: Dict[str, Any]) -> Optional[Image.Image]:
        """
        Render a single headline as a PIL Image.
        
        When a logo is present:
        - Logo replaces the "[Feed Name]: " prefix
        - Logo replaces the " • " separator
        - Format: [Logo] Title
        
        When a logo is missing:
        - Shows "[Feed Name]: " prefix
        - Shows " • " separator after title
        - Format: [Feed Name]: Title • 
        """
        try:
            title = headline.get('title', 'No title')
            feed_name = headline.get('feed_name', 'Unknown')

            # Calculate text dimensions
            draw_temp = ImageDraw.Draw(Image.new('RGB', (1, 1)))
            
            # Get text dimensions for title
            title_bbox = draw_temp.textbbox((0, 0), title, font=self.fonts['headline'])
            title_width = title_bbox[2] - title_bbox[0]
            title_height = title_bbox[3] - title_bbox[1]

            # Load logo if enabled
            logo = None
            logo_width = 0
            logo_spacing = 0
            if self.show_logos:
                logo_path = self._get_feed_logo_path(feed_name)
                if logo_path:
                    logo = self.logo_helper.load_logo(
                        feed_name,
                        logo_path,
                        max_width=self.logo_size,
                        max_height=self.logo_size
                    )
                    if logo:
                        logo_width = logo.width
                        logo_spacing = 4  # Space between logo and text

            # Determine what to show based on logo availability
            # If logo exists: show logo + title (no feed name, no separator)
            # If logo missing: show feed name + title + separator
            has_logo = logo is not None
            
            if has_logo:
                # With logo: [Logo] Title
                feed_text = ""
                separator_text = ""
            else:
                # Without logo: [Feed Name]: Title • 
                feed_text = f"{feed_name}: "
                separator_text = " • "

            # Calculate dimensions for feed name and separator (only if no logo)
            feed_width = 0
            feed_height = 0
            if feed_text:
                feed_bbox = draw_temp.textbbox((0, 0), feed_text, font=self.fonts['info'])
                feed_width = feed_bbox[2] - feed_bbox[0]
                feed_height = feed_bbox[3] - feed_bbox[1]

            separator_width = 0
            separator_height = 0
            if separator_text:
                separator_bbox = draw_temp.textbbox((0, 0), separator_text, font=self.fonts['separator'])
                separator_width = separator_bbox[2] - separator_bbox[0]
                separator_height = separator_bbox[3] - separator_bbox[1]

            # Calculate total width
            total_width = logo_width + logo_spacing + feed_width + title_width + separator_width + 32  # Add padding
            total_height = max(title_height, feed_height, self.logo_size if logo else 0) + 4  # Add padding

            # Create image for this headline
            headline_img = Image.new('RGB', (total_width, total_height), (0, 0, 0))
            draw = ImageDraw.Draw(headline_img)

            # Draw components
            current_x = 0

            # Draw logo if available (replaces feed name and separator)
            if logo:
                # Center logo vertically
                logo_y = (total_height - logo.height) // 2
                headline_img.paste(logo, (current_x, logo_y), logo if logo.mode == 'RGBA' else None)
                current_x += logo_width + logo_spacing

            # Draw feed name (only if no logo)
            if feed_text:
                feed_text_y = (total_height - feed_height) // 2
                draw.text((current_x, feed_text_y), feed_text, font=self.fonts['info'], fill=(150, 150, 150))
                current_x += feed_width

            # Draw title
            title_y = (total_height - title_height) // 2
            draw.text((current_x, title_y), title, font=self.fonts['headline'], fill=self.text_color)
            current_x += title_width

            # Draw separator (only if no logo) - use bullet point separator
            if separator_text:
                separator_x = current_x + 8
                separator_y = (total_height - separator_height) // 2
                draw.text((separator_x, separator_y), separator_text, font=self.fonts['separator'], fill=self.separator_color)

            return headline_img

        except Exception as e:
            self.logger.error(f"Error rendering headline: {e}")
            return None

    def _display_no_headlines(self):
        """Display message when no headlines are available."""
        img = Image.new('RGB', (self.display_width, self.display_height), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.text((5, 12), "No News Headlines", font=self.fonts.get('headline', ImageFont.load_default()), fill=(150, 150, 150))

        self.display_manager.image = img
        self.display_manager.update_display()

    def _display_error(self, message: str):
        """Display error message."""
        img = Image.new('RGB', (self.display_width, self.display_height), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.text((5, 12), message, font=self.fonts.get('headline', ImageFont.load_default()), fill=(255, 0, 0))

        self.display_manager.image = img
        self.display_manager.update_display()

    def get_display_duration(self) -> float:
        """Get display duration, using dynamic duration if enabled."""
        # If dynamic duration is enabled and scroll helper has calculated a duration, use it
        if (self.dynamic_duration_enabled and 
            hasattr(self.scroll_helper, 'calculated_duration') and 
            self.scroll_helper.calculated_duration > 0):
            return float(self.scroll_helper.calculated_duration)
        
        # Fallback to configured duration
        return float(self.display_duration)

    def get_info(self) -> Dict[str, Any]:
        """Return plugin info for web UI."""
        info = super().get_info()
        info.update({
            'total_headlines': len(self.current_headlines),
            'enabled_feeds': self.feeds_config.get('enabled_feeds', []),
            'custom_feeds': list(self.feeds_config.get('custom_feeds', {}).keys()),
            'last_update': self.last_update,
            'display_duration': self.display_duration,
            'scroll_speed': self.scroll_speed,
            'rotation_enabled': self.rotation_enabled,
            'rotation_threshold': self.rotation_threshold,
            'headlines_per_feed': self.headlines_per_feed,
            'font_size': self.font_size,
            'text_color': self.text_color,
            'separator_color': self.separator_color,
            'show_logos': self.show_logos,
            'logo_size': self.logo_size,
            'feed_logo_map': self.feed_logo_map
        })
        return info

    def cleanup(self) -> None:
        """Cleanup resources."""
        self.current_headlines = []
        if hasattr(self, 'scroll_helper'):
            self.scroll_helper.clear_cache()
        self.logger.info("News ticker plugin cleaned up")
