# GitHub Organization AI Repository Scanner

This tool helps you scan GitHub organizations to find repositories related to AI, machine learning, and similar topics.

## Setup

1. Clone this repository
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up your OpenAI API key:
   - Create a `.env` file and add: `OPENAI_API_KEY=your_api_key_here`
   - Or set it as an environment variable
4. (Optional) Set up a GitHub token for higher API rate limits:
   - If you need to scan many repositories, you might want to create a [GitHub Personal Access Token](https://github.com/settings/tokens) (no special permissions needed - public data access only)
   - Either:
     - Add to your `.env` file: `GITHUB_TOKEN=your_token_here`
     - Or pass the token directly when creating the scanner

## Environment Variables

The following environment variables can be configured in your `.env` file:

- `OPENAI_API_KEY`: Your OpenAI API key (required unless using a different model provider)
- `GITHUB_TOKEN`: Your GitHub Personal Access Token (optional)
- `ENABLE_CACHING`: Set to "true" to enable caching of results using memcached (default: "false")
- `LLM_MODEL`: The LLM model to use for repository analysis (default: "gpt-4o-mini")
  - Examples:
    ```env
    # OpenAI models (requires OPENAI_API_KEY)
    LLM_MODEL=gpt-4o-mini
    
    # Ollama models
    LLM_MODEL=ollama/llama2
    
    # Google models
    LLM_MODEL=gemini-2.0-flash
    ```

## Example Output

The scanner generates detailed markdown reports analyzing repositories for AI-related content. For example, scanning the DataDog organization revealed:

- 3 repositories rated "Definitely AI-related" (5/5):
  - `documentor`: AI-powered technical documentation improvement
  - `llm-observability`: LLM observability instrumentation
  - `MonitoramaEUDesignForAI`: AI-driven monitoring UX prototypes

- 1 repository rated "Possibly AI-related" (3/5):
  - `sketches-dotnet`: Quantile sketch algorithm implementation

Reports include confidence scores, repository details, and analysis reasoning. View sample reports from [DataDog](datadog_sample_report.md) and [Shopify](shopify_sample_report.md).

## Usage

Running the script directly:

```bash
# Basic usage (required)
python github_org_scanner.py --org-name openai

# With optional runtime flags
python github_org_scanner.py --org-name datadog --min-confidence 3 --max-repositories 20
```

### Runtime Flags

- `--org-name`: Name of the GitHub organization to scan (required)
  - Example: `--org-name openai`

- `--min-confidence`: Filter repositories by minimum confidence score (0-5)
  - `0`: Include all repositories (default)
  - `1`: Definitely not AI-related
  - `2`: Probably not AI-related
  - `3`: Possibly AI-related
  - `4`: Likely AI-related
  - `5`: Definitely AI-related

- `--max-repositories`: Limit the number of repositories to analyze
  - Default: Analyze all matching repositories
  - Example: `--max-repositories 10` will analyze at most 10 repositories

### Using as a Module

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

This will run the example search on the OpenAI organization. 

## TODOS
- Check that LLMs other than OpenAI are indeed working.
- Extract all the print debug to an abstraction