#!/usr/bin/env python3

import argparse
import csv
import re
import time
import logging
import ssl
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Set, Tuple, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup
from robotexclusionrulesparser import RobotExclusionRulesParser
from tqdm import tqdm
import validators
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.poolmanager import PoolManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        """Create and initialize the urllib3 PoolManager with TLS configuration."""
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_version=ssl.PROTOCOL_TLS,
            ssl_context=ctx
        )

class SalesforceAnalyzer:
    def __init__(self, max_pages_per_domain: int = 20, request_delay: float = 1.0):
        self.max_pages_per_domain = max_pages_per_domain
        self.request_delay = request_delay
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
        }
        self.robots_parser = RobotExclusionRulesParser()
        
        # Configure session with retries and SSL handling
        self.session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        self.session.mount('https://', TLSAdapter(max_retries=retries))
        self.session.mount('http://', TLSAdapter(max_retries=retries))

    def is_valid_url(self, url: str) -> bool:
        """Check if URL is valid and not a blog/article/thread page."""
        if not validators.url(url):
            return False
        
        path = urlparse(url).path.lower()
        excluded_patterns = [
            '/blog/', '/article', '/thread', '/news/', '/press/', '/post',
            '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.doc', '.docx',
            '/category/', '/tag/', '/author/', '/archive/'
        ]
        return not any(pattern in path for pattern in excluded_patterns)

    def get_base_url(self, url: str) -> str:
        """Extract base URL from a given URL."""
        parsed = urlparse(url)
        # Ensure we don't include any path components in the base URL
        return f"{parsed.scheme}://{parsed.netloc}"

    def check_robots_txt(self, domain: str) -> None:
        """Fetch and parse robots.txt for the domain."""
        try:
            base_url = self.get_base_url(domain)
            robots_url = f"{base_url}/robots.txt"
            response = self.session.get(robots_url, headers=self.headers, timeout=20)
            self.robots_parser.parse(response.text)
            logger.debug(f"Successfully fetched robots.txt for {domain}")
        except Exception as e:
            logger.warning(f"Could not fetch robots.txt for {domain}: {str(e)}")
            self.robots_parser.parse('')

    def extract_links(self, url: str, html: str) -> Set[str]:
        """Extract valid links from HTML content."""
        soup = BeautifulSoup(html, 'html.parser')
        base_url = self.get_base_url(url)
        links = set()
        
        for link in soup.find_all('a', href=True):
            try:
                href = link['href']
                # Skip empty or javascript links
                if not href or href.startswith(('javascript:', '#', 'mailto:', 'tel:')):
                    continue
                
                # Handle absolute and relative URLs correctly
                if href.startswith('http'):
                    parsed_href = urlparse(href)
                    # Skip external links
                    if not self.is_same_domain(href, base_url):
                        continue
                    full_url = href
                else:
                    # Remove any leading/trailing slashes from href
                    href = href.strip('/')
                    # Get the base URL without any path
                    parsed_base = urlparse(base_url)
                    clean_base = f"{parsed_base.scheme}://{parsed_base.netloc}"
                    full_url = f"{clean_base}/{href}" if href else clean_base
                
                # Skip invalid URLs and file extensions
                if not self.is_valid_url(full_url):
                    continue
                
                links.add(full_url)
            except Exception as e:
                logger.debug(f"Error processing link {href}: {str(e)}")
                continue
        
        return links

    def count_salesforce_mentions(self, html: str) -> int:
        """Count occurrences of 'Salesforce' in HTML content."""
        soup = BeautifulSoup(html, 'html.parser')
        # Remove script, style, meta, and other non-content elements
        for element in soup(['script', 'style', 'meta', 'link', 'noscript', 'header', 'footer', 'nav']):
            element.decompose()
        
        text = soup.get_text()
        
        # Simple count of 'salesforce' mentions
        return len(re.findall(r'\bsalesforce\b', text, re.IGNORECASE))

    def calculate_score(self, mentions: int) -> float:
        """Calculate score based on number of mentions (0.2 points per mention, max 10.0)."""
        return min(10.0, round(mentions * 0.2, 1))

    def is_same_domain(self, domain1: str, domain2: str) -> bool:
        """Check if two domains are effectively the same."""
        # Remove www. and get base domain
        def clean_domain(d: str) -> str:
            return urlparse(d).netloc.replace('www.', '').lower()
        return clean_domain(domain1) == clean_domain(domain2)

    def analyze_domain(self, domain: str) -> Tuple[float, str, Dict]:
        """Analyze a single domain for Salesforce mentions."""
        # Clean up the domain first
        if not domain.startswith(('http://', 'https://')):
            domain = f'https://{domain}'
        
        try:
            # Validate and clean up domain
            parsed = urlparse(domain)
            if not parsed.netloc:
                return 0.0, "Error: Invalid domain format", {}
            
            # Remove www. and any trailing slashes
            base_domain = parsed.netloc.replace('www.', '').rstrip('/')
            
            # Skip invalid domains
            if not validators.domain(base_domain):
                return 0.0, "Error: Invalid domain name", {}
            
            clean_domain = f"{parsed.scheme}://{base_domain}"
            logger.info(f"Starting analysis of {clean_domain}")
            
            # Try to connect to the domain first before proceeding
            response = None
            try:
                # First try without www
                try:
                    response = self.session.get(clean_domain, headers=self.headers, timeout=10, allow_redirects=True)
                    response.raise_for_status()
                except requests.exceptions.RequestException:
                    # If that fails, try with www
                    clean_domain = f"{parsed.scheme}://www.{base_domain}"
                    response = self.session.get(clean_domain, headers=self.headers, timeout=10, allow_redirects=True)
                    response.raise_for_status()
            except requests.exceptions.RequestException as e:
                logger.error(f"Cannot connect to {clean_domain}: {str(e)}")
                return 0.0, f"Error: Cannot connect to domain - {str(e)}", {
                    'pages_crawled': 0,
                    'total_mentions': 0,
                    'urls_with_mentions': [],
                    'error_urls': [{'url': clean_domain, 'error': str(e)}]
                }
            
            # If we can't get the main page, skip this domain
            if not response or not response.ok:
                return 0.0, f"Error: Domain returned status code {response.status_code if response else 'unknown'}", {}
            
            # Check if we got redirected and update the domain
            final_url = response.url.rstrip('/')
            redirected = not self.is_same_domain(final_url, clean_domain)
            if redirected:
                logger.info(f"Domain {clean_domain} redirected to {final_url}")
                # Get the base URL without any path
                parsed_final = urlparse(final_url)
                clean_domain = f"{parsed_final.scheme}://{parsed_final.netloc}"
            
            stats = {
                'pages_crawled': 0,
                'total_mentions': 0,
                'urls_with_mentions': [],
                'error_urls': [],
                'redirected_to': final_url if redirected else None
            }
            
            # Process the main page first
            stats['pages_crawled'] += 1
            mentions = self.count_salesforce_mentions(response.text)
            if mentions > 0:
                stats['urls_with_mentions'].append({
                    'url': final_url,
                    'mentions': mentions
                })
            stats['total_mentions'] += mentions
            current_score = self.calculate_score(stats['total_mentions'])
            
            # If we already hit max score, no need to crawl further
            if current_score >= 10.0:
                logger.info(f"Reached maximum score for {clean_domain}")
                status = "Success (redirected)" if redirected else "Success"
                return current_score, status, stats
            
            # Only proceed with subpages if main page was successful
            try:
                visited_urls = {final_url}
                to_visit = set(self.extract_links(final_url, response.text))
                
                while to_visit and len(visited_urls) < self.max_pages_per_domain and current_score < 10.0:
                    url = to_visit.pop()
                    if url in visited_urls:
                        continue
                    
                    try:
                        response = self.session.get(url, headers=self.headers, timeout=20, allow_redirects=True)
                        response.raise_for_status()
                        
                        # Skip if redirected to a different domain than our current working domain
                        if not self.is_same_domain(response.url, clean_domain):
                            continue
                        
                        visited_urls.add(response.url)
                        stats['pages_crawled'] += 1
                        
                        mentions = self.count_salesforce_mentions(response.text)
                        if mentions > 0:
                            stats['urls_with_mentions'].append({
                                'url': response.url,
                                'mentions': mentions
                            })
                        
                        stats['total_mentions'] += mentions
                        current_score = self.calculate_score(stats['total_mentions'])
                        
                        # Early termination if we hit max score
                        if current_score >= 10.0:
                            logger.info(f"Reached maximum score for {clean_domain}")
                            break
                        
                        logger.debug(f"Successfully processed {url} ({mentions} mentions)")
                        time.sleep(self.request_delay)
                        
                    except requests.exceptions.RequestException as e:
                        logger.warning(f"Error fetching {url}: {str(e)}")
                        stats['error_urls'].append({
                            'url': url,
                            'error': str(e)
                        })
                        continue
                
            except Exception as e:
                # If we fail processing subpages but have a score from the main page,
                # return that score rather than failing completely
                if stats['total_mentions'] > 0:
                    logger.warning(f"Error processing subpages for {clean_domain}: {str(e)}")
                    status = "Success (main page only, redirected)" if redirected else "Success (main page only)"
                    return current_score, status, stats
                raise
            
            score = self.calculate_score(stats['total_mentions'])
            if stats['pages_crawled'] == 0:
                status = "Error: No pages could be crawled"
                score = 0.0
            else:
                status = "Success (redirected)" if redirected else "Success"
            logger.info(f"Completed analysis of {clean_domain} (score: {score})")
            
        except Exception as e:
            logger.error(f"Error analyzing {domain}: {str(e)}", exc_info=True)
            score = 0.0
            status = f"Error: {str(e)}"
        
        return score, status, stats

def main():
    parser = argparse.ArgumentParser(description='Analyze websites for Salesforce mentions')
    parser.add_argument('--input', required=True, help='Input CSV file path')
    parser.add_argument('--output', required=True, help='Output CSV file path')
    parser.add_argument('--detailed-output', help='Path for detailed JSON output')
    args = parser.parse_args()
    
    # Read input CSV
    try:
        df = pd.read_csv(args.input)
        if 'domain' not in df.columns:
            raise ValueError("Input CSV must have a 'domain' column")
    except Exception as e:
        logger.error(f"Error reading input file: {e}")
        return
    
    analyzer = SalesforceAnalyzer()
    results = []
    detailed_results = {}
    
    # Process domains with progress bar
    for domain in tqdm(df['domain'], desc="Analyzing domains"):
        score, status, stats = analyzer.analyze_domain(domain)
        # Ensure all required fields are present
        if not isinstance(stats, dict):
            stats = {}
        results.append({
            'domain': domain,
            'score': score,
            'status': status,
            'pages_crawled': stats.get('pages_crawled', 0),
            'total_mentions': stats.get('total_mentions', 0),
            'redirected_to': stats.get('redirected_to', None)
        })
        detailed_results[domain] = stats
    
    # Save results
    results_df = pd.DataFrame(results)
    results_df.to_csv(args.output, index=False)
    logger.info(f"Results saved to {args.output}")
    
    # Save detailed results if requested
    if args.detailed_output:
        import json
        with open(args.detailed_output, 'w') as f:
            json.dump(detailed_results, f, indent=2)
        logger.info(f"Detailed results saved to {args.detailed_output}")

if __name__ == "__main__":
    main() 