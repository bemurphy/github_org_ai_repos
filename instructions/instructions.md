# Project overview
You are building a GitHub API crawler. The intent is to take a given Organization on github, and browse across their repos, then use an LLM to decide if the repo name, description, etc, is related to AI.

Using:
- python
- the best suited python GitHub rest or graphql client for listing and browsing org repositories.
- litellm for wrapping the LLM connection

# Critical Notes
- We're only browsing public repos, so don't use a token unless necessary
- Handle pagination when searching where applicable
- Use the org "DataDog" always as the org for testing or main calls. Never switch this.
- When building Core functionalities, the implementation in main() should chain the calls together.
- when running in Cursor for testing, ensure we pass the flag --max-repositories 10

# Core functionalities
1. Ability to search all public repos for a given org for keywords like "llm" or "ai"
   1. Use a python memcached client to allow caching all the org search results. Caching should be conditional via the env ENABLE_CACHING=true.
2. Ability to individually browse matches from public repo search and extract the description and README.md files
   1. Use a python memcached client to allow caching all the repo results. Follow previous caching pattern.
3. Ability to run repository names, descriptions, and README through an LLM to check if the repository is AI related. Generate a confidence score 1-5.
4. Output matched repositories in a markdown report, with the repo name, url, description, and confidence score provided
   1. Sort the repositories by confidence descending, alpha ascending
   2. Allow a runtime flag, --min-confidence, to optionally filter out repositories that are below the minimum confidence level.
   3. Allow an optional runtime flag, --max-repositories, which controls the maximum number of repositories that are individually crawled. It shouldn't impact overall repo search, only individual analisis. No repository list tructation should occur if the flag is not set.