# GitHub Organization AI Repository Scanner

This tool helps you scan GitHub organizations to find repositories related to AI, machine learning, and similar topics.

## Setup

1. Clone this repository
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. (Optional) Set up a GitHub token for higher API rate limits:
   - If you need to scan many repositories, you might want to create a [GitHub Personal Access Token](https://github.com/settings/tokens) (no special permissions needed - public data access only)
   - Either:
     - Create a `.env` file and add: `GITHUB_TOKEN=your_token_here`
     - Or pass the token directly when creating the scanner

## Usage

```python
from github_org_scanner import GithubOrgScanner

# Initialize the scanner without a token (for public data access)
scanner = GithubOrgScanner()

# Or initialize with token if you need higher rate limits
# scanner = GithubOrgScanner(github_token="your_token_here")

# Search for repositories
org_name = "openai"
keywords = ["llm", "ai", "gpt", "machine learning"]
matching_repos = scanner.search_org_repos(org_name, keywords)

# Print results
for repo in matching_repos:
    print(f"Repository: {repo.name}")
    print(f"Description: {repo.description}")
    print(f"URL: {repo.html_url}")
```

You can also run the script directly:
```bash
python github_org_scanner.py
```

This will run the example search on the OpenAI organization. 