-----------------------------------------------------------------------------------
### Connect with ChuckBuilds

- Show support on Youtube: https://www.youtube.com/@ChuckBuilds
- Stay in touch on Instagram: https://www.instagram.com/ChuckBuilds/
- Want to chat or need support? Reach out on the ChuckBuilds Discord: https://discord.com/invite/uW36dVAtcT
- Feeling Generous? Support the project:
  - Github Sponsorship: https://github.com/sponsors/ChuckBuilds
  - Buy Me a Coffee: https://buymeacoffee.com/chuckbuilds
  - Ko-fi: https://ko-fi.com/chuckbuilds/ 

-----------------------------------------------------------------------------------

# News Ticker Plugin

A plugin for LEDMatrix that displays scrolling news headlines from RSS feeds including sports news from ESPN, NCAA updates, and custom RSS sources.

## Features

- **Multiple RSS Sources**: ESPN sports feeds, NCAA updates, and custom RSS URLs
- **Scrolling Headlines**: Continuous scrolling ticker display
- **News Source Logos**: Display logos for news sources (ESPN, NFL Network, MLB Network, etc.)
- **Headline Rotation**: Cycle through headlines after multiple viewings
- **Custom Feeds**: Add your own RSS feed URLs
- **Sports Focus**: Pre-configured feeds for NFL, NBA, MLB, NCAA, and more
- **Configurable Display**: Adjustable scroll speed, colors, and timing
- **Background Data Fetching**: Efficient RSS parsing without blocking display

## Configuration

### Global Settings

- `display_duration`: How long to show the ticker (10-300 seconds, default: 30)
- `display.scroll_speed`: Scrolling speed in pixels per frame (0.5-5.0, default: 1.0) - **Recommended format**
- `display.scroll_delay`: Delay between scroll steps in seconds (0.001-0.1, default: 0.01) - **Recommended format**
- `scroll_speed`: [Deprecated] Legacy scrolling speed multiplier - use `display.scroll_speed` instead
- `scroll_delay`: [Deprecated] Legacy delay setting - use `display.scroll_delay` instead
- `scroll_pixels_per_second`: [Deprecated] Legacy time-based scrolling - use frame-based `display.scroll_speed` and `display.scroll_delay` instead
- `target_fps`: Target frames per second for scrolling (30-200, default: 100)
- `dynamic_duration`: Enable dynamic duration based on content width (default: true)
  - `enabled`: Enable/disable dynamic duration (default: true)
  - `min_duration_seconds`: Minimum display duration (10-300 seconds, default: 30)
  - `max_duration_seconds`: Maximum display duration (30-600 seconds, default: 300)
  - `buffer_ratio`: Extra buffer applied to calculated duration (0.01-1.0, default: 0.1)
- `rotation_enabled`: Enable headline rotation (default: true)
- `rotation_threshold`: Cycles before rotating headlines (1-10, default: 3)
- `headlines_per_feed`: Headlines to fetch per feed (1-10, default: 2)
- `font_size`: Font size for headlines (8-20, default: 12)

### Feed Settings

#### Enabled Predefined Feeds

```json
{
  "feeds": {
    "enabled_feeds": ["NFL", "NCAA FB", "NBA", "MLB"]
  }
}
```

#### Custom RSS Feeds

```json
{
  "feeds": {
    "custom_feeds": {
      "Tech News": "https://example.com/rss.xml",
      "Local Sports": "https://local-sports.com/feed.xml"
    }
  }
}
```

#### Display Colors

```json
{
  "feeds": {
    "text_color": [255, 255, 255],
    "separator_color": [255, 0, 0]
  }
}
```

#### News Source Logos

```json
{
  "feeds": {
    "show_logos": true,
    "logo_size": 28,
    "feed_logo_map": {
      "My Custom Feed": "my_logo.png",
      "Tech News": "tech_logo.png"
    }
  }
}
```

- `show_logos`: Enable/disable news source logos (default: true)
- `logo_size`: Logo size in pixels (default: display height - 4 pixels)
- `feed_logo_map`: Custom logo file mapping for feeds (optional)

**Logo Behavior:**
- When a logo is present: Logo replaces the "[Feed Name]: " prefix and " • " separator
  - Format: `[Logo] Title`
- When a logo is missing: Shows original format with feed name and separator
  - Format: `[Feed Name]: Title • `

**Logo Resolution Priority:**
1. User-configured `feed_logo_map` (custom logo file names)
2. Predefined feed mappings (ESPN, NFL Network, MLB Network)
3. Inferred from feed name (checks for "espn", "nfl", "mlb", etc.)
4. Normalized feed name as filename (fallback)

**Logo Directory Search Order:**
1. `assets/news_logos/` (primary location for news source logos)
2. `assets/broadcast_logos/` (fallback for broadcast network logos)
3. Plugin `assets/logos/` (plugin-specific logos)

**Adding Custom Logos:**
1. Place your logo file (PNG format recommended) in `assets/news_logos/`
2. Configure the mapping in `feed_logo_map`:
   ```json
   "feed_logo_map": {
     "My Feed Name": "my_logo.png"
   }
   ```
3. The plugin will automatically find and use your logo

**Default Feed Mappings:**
- ESPN feeds (NFL, NBA, NHL, NCAA, etc.) → `espn.png`
- MLB feed → `mlbn.png`
- NFL feed → `nfln.png`
- Custom feeds → Inferred from name or normalized feed name

## Available Predefined Feeds

The plugin includes these predefined RSS feeds:

- **MLB**: ESPN MLB News (`http://espn.com/espn/rss/mlb/news`)
- **NFL**: ESPN NFL News (`http://espn.go.com/espn/rss/nfl/news`)
- **NCAA FB**: ESPN NCAA Football News (`https://www.espn.com/espn/rss/ncf/news`)
- **NHL**: ESPN NHL News (`https://www.espn.com/espn/rss/nhl/news`)
- **NBA**: ESPN NBA News (`https://www.espn.com/espn/rss/nba/news`)
- **TOP SPORTS**: ESPN Top Sports News (`https://www.espn.com/espn/rss/news`)
- **BIG10**: Big Ten Conference News (`https://www.espn.com/blog/feed?blog=bigten`)
- **NCAA**: ESPN NCAA News (`https://www.espn.com/espn/rss/ncaa/news`)
- **Other**: Alternative Sports News (`https://www.coveringthecorner.com/rss/current.xml`)

## Display Format

The news ticker displays information in a scrolling format showing:

- **Feed Source**: Name of the RSS feed (e.g., "NFL", "ESPN")
- **Headline**: News headline text (truncated if too long)
- **Separator**: Visual separator between headlines ("---")
- **Timestamp**: When the headline was published (if available)

## Background Service

The plugin uses background data fetching for efficient RSS parsing:

- Requests timeout after 30 seconds (configurable)
- Up to 3 retries for failed requests
- Priority level 2 (medium priority)
- Updates every 5 minutes by default (configurable)

## Adding Custom Feeds

You can add custom RSS feeds by specifying them in the configuration:

```json
{
  "feeds": {
    "custom_feeds": {
      "My Sports": "https://mysportsfeed.com/rss",
      "Local News": "https://localnews.com/sports.xml"
    }
  }
}
```

## Data Processing

- **RSS Parsing**: Uses Python's xml.etree.ElementTree for reliable parsing
- **Text Cleaning**: Removes HTML entities and extra whitespace
- **Length Limiting**: Truncates long headlines for display
- **Caching**: Stores headlines for 10 minutes to avoid excessive API calls

## Dependencies

This plugin requires the main LEDMatrix installation and uses the cache manager for data storage.

## Installation

1. Copy this plugin directory to your `ledmatrix-plugins/plugins/` folder
2. Ensure the plugin is enabled in your LEDMatrix configuration
3. Configure your preferred RSS feeds and display options
4. Restart LEDMatrix to load the new plugin

## Troubleshooting

- **No headlines showing**: Check if feeds are enabled and URLs are accessible
- **RSS parsing errors**: Verify feed URLs are valid and return proper XML
- **Slow scrolling**: Adjust scroll speed and delay settings
- **Network errors**: Check your internet connection and RSS server availability

## Advanced Features

- **Headline Rotation**: Automatically rotates through headlines after multiple cycles
- **Dynamic Duration**: Adjusts display time based on content length
- **Color Customization**: Configure text and separator colors
- **Font Sizing**: Adjustable font size for readability
- **Feed Prioritization**: Control which feeds are displayed and in what order

## Performance Notes

- The plugin uses the **ScrollHelper API** for high-performance scrolling with numpy array optimization
- **Frame-based scrolling** provides smooth, consistent scrolling at 100+ FPS
- **Dynamic duration** automatically calculates display time based on content width and scroll speed
- RSS parsing happens in background to avoid blocking the display
- Configurable update intervals balance freshness vs. network load
- Caching reduces unnecessary network requests

## Scrolling Implementation

This plugin uses the LEDMatrix **ScrollHelper** API for optimized scrolling:

- **High-FPS Mode**: Automatically enables high frame rate (100+ FPS) for smooth scrolling
- **Frame-Based Scrolling**: Uses `display.scroll_speed` (pixels per frame) and `display.scroll_delay` (seconds per frame) for precise control
- **Dynamic Duration**: Automatically calculates display duration based on content width, ensuring all headlines are shown
- **Numpy Optimization**: Uses fast numpy array slicing for minimal CPU usage
- **Smooth Animation**: Pre-allocated buffers and optimized rendering for consistent performance

### Recommended Configuration

For best performance, use the frame-based scrolling format:

```json
{
  "global": {
    "display": {
      "scroll_speed": 1.0,
      "scroll_delay": 0.01
    },
    "target_fps": 100,
    "dynamic_duration": {
      "enabled": true,
      "min_duration_seconds": 30,
      "max_duration_seconds": 300,
      "buffer_ratio": 0.1
    }
  }
}
```

This configuration provides:
- 1 pixel per frame scrolling
- 0.01 second delay = 100 FPS effective rate
- Dynamic duration that adjusts to content length
- Smooth, consistent scrolling performance
