Requirements Summary
Input

The application should accept a CSV file containing a list of company domains (e.g., example.com, anothercompany.org).
Web Crawler / Scraper

For each domain, the application should fetch all accessible webpages (main pages and subpages) under that domain.
The scraper should automatically exclude or skip pages that appear to be blog posts, articles, or threads. (For example, any URL containing /blog/, /thread/, /articles/, or similar patterns should be ignored.)
Keyword Search & Rating

Within the pages that are crawled, the application should search for the keyword "Salesforce".
Each domain should receive a "Salesforce Mention" score between 0.0 and 10.0, depending on how many times the keyword appears on the site.
Output

The application should produce an output (e.g., a new CSV or a displayed list) showing each domain and its associated "Salesforce Mention" score.
Optionally, it can categorize domains based on whether they have any mentions (score > 0) versus no mentions (score = 0).
Purpose

The goal is to analyze which companies (from a CSV of registered vendors) are likely to be doing technology projects, specifically Salesforce-related work, and which ones are not.
Additional Considerations

Implement error handling:
Invalid domains or unreachable sites should yield an indication that the domain could not be analyzed.
Limit the crawler’s depth or set a maximum number of pages per domain to prevent overly extensive crawling.
Ensure the system is sufficiently performant to handle large CSV files with many domains.