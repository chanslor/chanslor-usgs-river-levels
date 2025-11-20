#!/usr/bin/env python3
"""
River Gauge Dashboard Validator 🔍
Validates that all expected data elements are present in the generated HTML dashboard.
Supports both local files and remote URLs (for testing live deployments).
Makes testing fun with emojis and colorful output! 🎨
"""

import re
import sys
import argparse
from html.parser import HTMLParser
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import ssl

# ANSI color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

# Fun emojis for different validation states
class Emojis:
    CHECK = '✅'
    CROSS = '❌'
    WARNING = '⚠️'
    RIVER = '🌊'
    THERMOMETER = '🌡️'
    WIND = '💨'
    RAIN = '🌧️'
    CHART = '📊'
    CLOCK = '🕐'
    ROCKET = '🚀'
    PARTY = '🎉'
    THINKING = '🤔'
    TARGET = '🎯'
    STAR = '⭐'

class RiverSiteData:
    """Container for river site data extracted from HTML"""
    def __init__(self, name):
        self.name = name
        self.has_name = False
        self.has_cfs = False
        self.has_feet = False
        self.has_timestamp = False
        self.has_sparkline = False
        self.has_threshold = False
        self.has_trend = False
        self.has_qpf = False
        self.has_weather = False
        self.has_weather_secondary = False
        self.has_city_label = False
        self.row_class = None
        self.timestamp_value = None
        self.cfs_value = None
        self.feet_value = None

class DashboardParser(HTMLParser):
    """Parse HTML dashboard and extract site data"""
    def __init__(self):
        super().__init__()
        self.sites = []
        self.current_site = None
        self.in_tbody = False
        self.in_river_cell = False
        self.in_sub = False
        self.in_obs = False
        self.current_row_class = None
        self.current_cell_index = 0
        self.current_text = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag == 'tbody':
            self.in_tbody = True
        elif tag == 'tr' and self.in_tbody:
            # New row = new site
            self.current_row_class = attrs_dict.get('class', 'unknown')
            self.current_cell_index = 0
        elif tag == 'td' and self.in_tbody and self.current_row_class:
            self.current_cell_index += 1
        elif tag == 'div':
            class_name = attrs_dict.get('class', '')
            if 'river' in class_name:
                self.in_river_cell = True
            elif 'sub' in class_name:
                self.in_sub = True
                if 'obs' in class_name:
                    self.in_obs = True
            elif 'sparkline' in class_name:
                if self.current_site:
                    self.current_site.has_sparkline = True
        elif tag == 'a' and self.in_river_cell:
            # River name link found
            pass
        elif tag == 'span':
            class_name = attrs_dict.get('class', '')
            if self.current_site and self.in_sub:
                if 'trend-' in class_name:
                    self.current_site.has_trend = True
                elif 'rain-alert' in class_name or 'qpf' in self.current_text:
                    self.current_site.has_qpf = True

    def handle_endtag(self, tag):
        if tag == 'tbody':
            self.in_tbody = False
        elif tag == 'tr' and self.in_tbody:
            # End of row
            if self.current_site:
                self.sites.append(self.current_site)
            self.current_site = None
            self.current_row_class = None
        elif tag == 'div':
            self.in_river_cell = False
            if self.in_sub:
                self.in_sub = False
                self.in_obs = False

    def handle_data(self, data):
        data = data.strip()
        if not data:
            return

        self.current_text.append(data)

        # First cell = river name and details
        if self.current_cell_index == 1:
            if self.in_river_cell and not self.current_site:
                # Create new site entry
                self.current_site = RiverSiteData(data)
                self.current_site.has_name = True
                self.current_site.row_class = self.current_row_class
            elif self.in_sub and self.current_site:
                # Check for threshold info
                if '≥' in data or 'ft' in data or 'cfs' in data:
                    self.current_site.has_threshold = True
                # Check for QPF
                if 'QPF' in data or 'Today:' in data or 'Tomorrow:' in data:
                    self.current_site.has_qpf = True
                # Check for weather observations
                if '°F' in data or 'Wind:' in data or 'mph' in data:
                    self.current_site.has_weather = True
                # Check for city labels (new abbreviations)
                if re.search(r'\(([A-Z]{4,7})\)', data):
                    self.current_site.has_city_label = True
                    # Check for secondary weather (will appear as second obs line)
                    if self.current_site.has_weather:
                        self.current_site.has_weather_secondary = True

        # Third cell = CFS
        elif self.current_cell_index == 3:
            if data and data != '—' and re.match(r'[\d,]+', data):
                self.current_site.has_cfs = True
                self.current_site.cfs_value = data

        # Fourth cell = Feet
        elif self.current_cell_index == 4:
            if data and data != '—' and re.match(r'\d+\.\d+', data):
                self.current_site.has_feet = True
                self.current_site.feet_value = data

        # Fifth cell = Timestamp
        elif self.current_cell_index == 5:
            # Look for time format like "10:29AM" or date format
            if re.search(r'\d{1,2}:\d{2}[AP]M', data) or re.search(r'\d{2}-\d{2}-\d{4}', data):
                if self.current_site:
                    self.current_site.has_timestamp = True
                    self.current_site.timestamp_value = data

def check_mark(passed, label, emoji=''):
    """Return a colorful checkmark or cross with label"""
    if passed:
        return f"{Colors.GREEN}{Emojis.CHECK} {emoji} {label}{Colors.RESET}"
    else:
        return f"{Colors.RED}{Emojis.CROSS} {emoji} {label}{Colors.RESET}"

def validate_site(site, verbose=False):
    """Validate a single site and return results"""
    checks = []
    score = 0
    total = 0

    # Core data checks
    core_checks = [
        (site.has_name, "River name", Emojis.RIVER),
        (site.has_feet, "Feet measurement", "📏"),
        (site.has_timestamp, "Timestamp", Emojis.CLOCK),
        (site.has_threshold, "Threshold info", Emojis.TARGET),
    ]

    for passed, label, emoji in core_checks:
        checks.append(check_mark(passed, label, emoji))
        total += 1
        if passed:
            score += 1

    # CFS check (optional for some sites)
    if site.has_cfs:
        checks.append(check_mark(True, f"CFS data ({site.cfs_value})", "💧"))
        score += 1
        total += 1
    else:
        checks.append(f"{Colors.YELLOW}{Emojis.WARNING} 💧 CFS data (optional){Colors.RESET}")
        total += 1

    # Enhanced features
    feature_checks = [
        (site.has_sparkline, "12hr Sparkline chart", Emojis.CHART),
        (site.has_trend, "Trend indicator", "📈"),
    ]

    for passed, label, emoji in feature_checks:
        checks.append(check_mark(passed, label, emoji))
        total += 1
        if passed:
            score += 1

    # Weather data checks
    if site.has_weather:
        checks.append(check_mark(True, "Weather observations", f"{Emojis.THERMOMETER}{Emojis.WIND}"))
        score += 1
        total += 1

        # Check for city label (new feature!)
        if site.has_city_label:
            checks.append(check_mark(True, "City abbreviation label", Emojis.STAR))
            score += 1
            total += 1
        else:
            checks.append(check_mark(False, "City abbreviation label", Emojis.STAR))
            total += 1

        # Secondary weather station
        if site.has_weather_secondary:
            checks.append(check_mark(True, "Secondary weather (valley)", "🏔️"))
            score += 1
            total += 1
    else:
        checks.append(f"{Colors.YELLOW}{Emojis.WARNING} {Emojis.THERMOMETER} Weather observations (optional){Colors.RESET}")
        total += 1

    # QPF data check
    if site.has_qpf:
        checks.append(check_mark(True, "Rainfall forecast (QPF)", Emojis.RAIN))
        score += 1
        total += 1
    else:
        checks.append(f"{Colors.YELLOW}{Emojis.WARNING} {Emojis.RAIN} Rainfall forecast (optional){Colors.RESET}")
        total += 1

    return checks, score, total

def is_url(path):
    """Check if the path is a URL"""
    return path.startswith('http://') or path.startswith('https://')

def fetch_html(source, timeout=30):
    """
    Fetch HTML content from either a local file or remote URL.
    Returns (html_content, source_type, source_info)
    """
    if is_url(source):
        # Remote URL
        try:
            print(f"{Emojis.ROCKET} Fetching remote dashboard from: {Colors.CYAN}{source}{Colors.RESET}")

            # Create request with user agent
            req = Request(source, headers={
                'User-Agent': 'RiverGaugeDashboardValidator/1.0 (Dashboard Testing Tool)'
            })

            # Handle SSL context for HTTPS
            context = ssl.create_default_context()

            with urlopen(req, timeout=timeout, context=context) as response:
                html_content = response.read().decode('utf-8')
                status_code = response.getcode()

            print(f"{Colors.GREEN}{Emojis.CHECK} Successfully fetched (HTTP {status_code}){Colors.RESET}\n")
            return html_content, 'remote', f"{source} (HTTP {status_code})"

        except HTTPError as e:
            print(f"{Colors.RED}{Emojis.CROSS} HTTP Error {e.code}: {e.reason}{Colors.RESET}")
            raise
        except URLError as e:
            print(f"{Colors.RED}{Emojis.CROSS} URL Error: {e.reason}{Colors.RESET}")
            raise
        except Exception as e:
            print(f"{Colors.RED}{Emojis.CROSS} Error fetching URL: {e}{Colors.RESET}")
            raise
    else:
        # Local file
        try:
            print(f"{Emojis.ROCKET} Reading local file: {Colors.CYAN}{source}{Colors.RESET}\n")
            with open(source, 'r', encoding='utf-8') as f:
                html_content = f.read()
            return html_content, 'local', source
        except FileNotFoundError:
            print(f"{Colors.RED}{Emojis.CROSS} Error: File not found: {source}{Colors.RESET}")
            raise
        except Exception as e:
            print(f"{Colors.RED}{Emojis.CROSS} Error reading file: {e}{Colors.RESET}")
            raise

def print_header():
    """Print a fun header"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*70}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}   🌊 River Gauge Dashboard Validator {Emojis.ROCKET}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'='*70}{Colors.RESET}\n")

def print_site_report(site, verbose=False):
    """Print validation report for a single site"""
    checks, score, total = validate_site(site, verbose)

    # Calculate percentage
    percentage = (score / total * 100) if total > 0 else 0

    # Determine status emoji
    if percentage == 100:
        status_emoji = Emojis.PARTY
        status_color = Colors.GREEN
    elif percentage >= 80:
        status_emoji = Emojis.CHECK
        status_color = Colors.GREEN
    elif percentage >= 60:
        status_emoji = Emojis.WARNING
        status_color = Colors.YELLOW
    else:
        status_emoji = Emojis.CROSS
        status_color = Colors.RED

    # Print site header
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'─'*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Emojis.RIVER} {site.name}{Colors.RESET} {Colors.MAGENTA}[{site.row_class}]{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'─'*70}{Colors.RESET}")

    # Print checks
    for check in checks:
        print(f"  {check}")

    # Print score
    print(f"\n  {status_color}{Colors.BOLD}{status_emoji} Score: {score}/{total} ({percentage:.0f}%){Colors.RESET}")

def print_summary(sites):
    """Print overall summary"""
    total_sites = len(sites)
    perfect_sites = sum(1 for site in sites if validate_site(site)[1] == validate_site(site)[2])

    total_score = sum(validate_site(site)[1] for site in sites)
    total_possible = sum(validate_site(site)[2] for site in sites)
    overall_percentage = (total_score / total_possible * 100) if total_possible > 0 else 0

    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}📊 Overall Summary{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'='*70}{Colors.RESET}\n")

    print(f"  {Emojis.TARGET} Total Sites: {Colors.BOLD}{total_sites}{Colors.RESET}")
    print(f"  {Emojis.PARTY} Perfect Sites: {Colors.BOLD}{Colors.GREEN}{perfect_sites}{Colors.RESET}/{total_sites}")
    print(f"  {Emojis.STAR} Overall Score: {Colors.BOLD}{total_score}{Colors.RESET}/{total_possible}")

    # Overall grade
    if overall_percentage == 100:
        grade = f"{Colors.GREEN}{Colors.BOLD}A+ {Emojis.PARTY} PERFECT!{Colors.RESET}"
    elif overall_percentage >= 90:
        grade = f"{Colors.GREEN}{Colors.BOLD}A {Emojis.STAR} EXCELLENT!{Colors.RESET}"
    elif overall_percentage >= 80:
        grade = f"{Colors.GREEN}{Colors.BOLD}B {Emojis.CHECK} GOOD!{Colors.RESET}"
    elif overall_percentage >= 70:
        grade = f"{Colors.YELLOW}{Colors.BOLD}C {Emojis.WARNING} OKAY{Colors.RESET}"
    else:
        grade = f"{Colors.RED}{Colors.BOLD}D {Emojis.CROSS} NEEDS WORK{Colors.RESET}"

    print(f"  {Emojis.CHART} Overall Grade: {grade} ({overall_percentage:.1f}%)")

    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*70}{Colors.RESET}\n")

def main():
    parser = argparse.ArgumentParser(
        description='🌊 Validate river gauge dashboard HTML with style!',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Local file
  %(prog)s usgs-site/index.html
  %(prog)s usgs-site/index.html --verbose
  %(prog)s usgs-site/index.html --site "Town Creek"

  # Remote URL (test live deployment)
  %(prog)s http://docker-blue-sound-1751.fly.dev
  %(prog)s https://docker-blue-sound-1751.fly.dev --site "Town Creek"
  %(prog)s https://your-app.fly.dev/index.html
        """
    )
    parser.add_argument('source', metavar='FILE_OR_URL',
                       help='Path to local HTML file or remote URL (http:// or https://)')
    parser.add_argument('--site', help='Validate specific site only')
    parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed information')
    parser.add_argument('--no-color', action='store_true', help='Disable colored output')
    parser.add_argument('--timeout', type=int, default=30, help='Timeout for remote URL fetching (default: 30s)')

    args = parser.parse_args()

    # Disable colors if requested
    if args.no_color:
        for attr in dir(Colors):
            if not attr.startswith('_'):
                setattr(Colors, attr, '')

    print_header()

    # Fetch HTML (from file or URL)
    try:
        html_content, source_type, source_info = fetch_html(args.source, timeout=args.timeout)
    except Exception:
        sys.exit(1)

    print(f"{Emojis.ROCKET} Parsing dashboard HTML...\n")

    # Parse the HTML
    parser_obj = DashboardParser()
    parser_obj.feed(html_content)
    sites = parser_obj.sites

    if not sites:
        print(f"{Colors.RED}{Emojis.CROSS} No sites found in HTML! {Emojis.THINKING}{Colors.RESET}")
        sys.exit(1)

    print(f"{Colors.GREEN}{Emojis.CHECK} Found {len(sites)} sites!{Colors.RESET}")

    # Filter by site name if requested
    if args.site:
        sites = [s for s in sites if args.site.lower() in s.name.lower()]
        if not sites:
            print(f"{Colors.RED}{Emojis.CROSS} No sites matching '{args.site}' found!{Colors.RESET}")
            sys.exit(1)

    # Validate each site
    for site in sites:
        print_site_report(site, args.verbose)

    # Print summary
    if not args.site:  # Only show summary for full validation
        print_summary(sites)

    # Exit code based on results
    total_score = sum(validate_site(site)[1] for site in sites)
    total_possible = sum(validate_site(site)[2] for site in sites)
    overall_percentage = (total_score / total_possible * 100) if total_possible > 0 else 0

    if overall_percentage >= 80:
        sys.exit(0)  # Success
    else:
        sys.exit(1)  # Needs improvement

if __name__ == '__main__':
    main()
