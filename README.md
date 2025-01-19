# Salesforce Mention Analyzer

A Python application that analyzes websites for Salesforce mentions and generates a score based on the frequency of mentions.

## Features

- Reads company domains from a CSV file
- Crawls websites respecting robots.txt
- Skips blog posts, articles, and thread pages
- Generates a Salesforce mention score (0.0-10.0)
- Outputs results in CSV format

## Setup

1. Create a virtual environment (recommended):
```bash
python -m venv .venv
source .venv/bin/activate  # On Unix/macOS
# OR
.venv\Scripts\activate  # On Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Prepare your input CSV file with a list of domains (one domain per line)
2. Run the analyzer:
```bash
python salesforce_analyzer.py --input input.csv --output results.csv
```

## Input CSV Format

Your input CSV should have a header row and contain domains in the following format:
```
domain
example.com
company.org
```

## Output Format

The program will generate a CSV file with the following columns:
- domain: The website domain
- score: Salesforce mention score (0.0-10.0)
- status: Success/Error message 