from github import Github
from github.Repository import Repository
from github.Organization import Organization
from github.GithubException import RateLimitExceededException
from typing import List, Dict, Optional, Tuple
import os
import time
import base64
import json
import hashlib
import memcache
import argparse
from dotenv import load_dotenv
from litellm import completion
from datetime import datetime

class GithubOrgScanner:
    def __init__(self, github_token: str = None):
        """
        Initialize the GitHub organization scanner.
        
        Args:
            github_token (str, optional): GitHub personal access token. Optional since we only access public data.
                                        If provided, it will allow for higher API rate limits.
        """
        if github_token is None:
            load_dotenv()
            github_token = os.getenv('GITHUB_TOKEN')
            
        # Initialize without token if none provided - will use unauthenticated access
        self.github = Github(github_token) if github_token else Github()
        
        # Initialize memcached if enabled
        self.caching_enabled = os.getenv('ENABLE_CACHING', 'false').lower() == 'true'
        if self.caching_enabled:
            self.cache = memcache.Client(['127.0.0.1:11211'], debug=0)
            print("Caching enabled - using memcached")
        else:
            self.cache = None
            print("Caching disabled")

    def _generate_cache_key(self, org_name: str, keywords: List[str]) -> str:
        """
        Generate a unique cache key for the org and keywords combination.
        
        Args:
            org_name (str): Name of the GitHub organization
            keywords (List[str]): List of keywords to search for
            
        Returns:
            str: Cache key
        """
        # Sort keywords to ensure consistent key generation
        sorted_keywords = sorted(keywords)
        key_content = f"{org_name}:{','.join(sorted_keywords)}"
        return f"github_org_scan:{hashlib.md5(key_content.encode()).hexdigest()}"

    def _generate_analysis_cache_key(self, repo_full_name: str) -> str:
        """
        Generate a unique cache key for repository analysis results.
        
        Args:
            repo_full_name (str): Full name of the repository (org/repo)
            
        Returns:
            str: Cache key
        """
        return f"repo_analysis:{hashlib.md5(repo_full_name.encode()).hexdigest()}"

    def _serialize_repo(self, repo: Repository) -> Dict:
        """
        Serialize repository object for caching.
        
        Args:
            repo (Repository): Repository object to serialize
            
        Returns:
            Dict: Serialized repository data
        """
        return {
            'name': repo.name,
            'description': repo.description,
            'url': repo.html_url,
            'topics': repo.get_topics(),
            'is_archived': repo.archived,
            'last_updated': repo.updated_at.isoformat() if repo.updated_at else None
        }

    def _deserialize_repo(self, repo_data: Dict) -> Repository:
        """
        Deserialize repository data from cache.
        
        Args:
            repo_data (Dict): Serialized repository data
            
        Returns:
            Repository: Repository object
        """
        # For simplicity, we'll refetch the repo from GitHub
        # This ensures we have a proper Repository object with all methods
        return self.github.get_repo(f"{repo_data['url'].split('github.com/')[1]}")

    def _serialize_analysis(self, analysis_result: Dict) -> Dict:
        """
        Serialize analysis results for caching.
        
        Args:
            analysis_result (Dict): Analysis results to serialize
            
        Returns:
            Dict: Serialized analysis data
        """
        return {
            'name': analysis_result['name'],
            'description': analysis_result['description'],
            'url': analysis_result['url'],
            'readme': analysis_result['readme'],
            'topics': analysis_result['topics'],
            'is_archived': analysis_result['is_archived'],
            'last_updated': analysis_result['last_updated'],
            'has_readme': analysis_result['has_readme'],
            'confidence_score': analysis_result['confidence_score'],
            'reason': analysis_result['reason']
        }

    def _deserialize_analysis(self, analysis_data: Dict) -> Dict:
        """
        Deserialize analysis data from cache.
        
        Args:
            analysis_data (Dict): Serialized analysis data
            
        Returns:
            Dict: Deserialized analysis results
        """
        return analysis_data

    def analyze_with_llm(self, repo_data: Dict) -> Dict:
        """
        Analyze repository data with LLM to determine if it's AI-related.
        
        Args:
            repo_data (Dict): Repository data including name, description, and README
            
        Returns:
            Dict: Analysis results including confidence score (1-5) and reasoning
        """
        # Construct the prompt
        prompt = f"""Analyze this GitHub repository and determine if it's related to AI/ML/LLM technology.
Repository Name: {repo_data['name']}
Description: {repo_data['description']}

README excerpt (first 1000 chars):
{repo_data['readme'][:1000]}

Rate on a scale of 1-5 how confident you are that this repository is AI-related:
1 = Definitely not AI-related
2 = Probably not AI-related
3 = Possibly AI-related
4 = Likely AI-related
5 = Definitely AI-related

Provide your rating and a brief explanation in the following format exactly:
RATING: <number>
REASON: <your explanation>"""

        try:
            # Call LiteLLM
            response = completion(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            
            # Parse response
            response_text = response.choices[0].message.content
            
            # Extract rating and reason
            rating_line = [line for line in response_text.split('\n') if line.startswith('RATING:')][0]
            reason_line = [line for line in response_text.split('\n') if line.startswith('REASON:')][0]
            
            confidence_score = int(rating_line.split(':')[1].strip())
            reason = reason_line.split(':')[1].strip()
            
            return {
                'confidence_score': confidence_score,
                'reason': reason
            }
            
        except Exception as e:
            print(f"\nError during LLM analysis of {repo_data['name']}: {str(e)}")
            return {
                'confidence_score': 0,
                'reason': f"Error during analysis: {str(e)}"
            }
    
    def get_repo_readme(self, repo: Repository) -> Optional[str]:
        """
        Get the contents of a repository's README file.
        
        Args:
            repo (Repository): The GitHub repository object
            
        Returns:
            Optional[str]: The contents of the README file, or None if not found
        """
        try:
            # Try common README filenames
            readme_files = ['README.md', 'README.rst', 'README', 'README.txt']
            for filename in readme_files:
                try:
                    readme = repo.get_contents(filename)
                    if isinstance(readme, list):
                        continue  # Skip if it's a directory
                    # Decode content from base64
                    content = base64.b64decode(readme.content).decode('utf-8')
                    return content
                except:
                    continue
            return None
        except Exception as e:
            print(f"Error fetching README for {repo.name}: {str(e)}")
            return None

    def analyze_repository(self, repo: Repository) -> Dict:
        """
        Analyze a repository by checking its description and README.
        Now includes LLM analysis for AI relevance and caching support.
        
        Args:
            repo (Repository): The GitHub repository object
            
        Returns:
            Dict: Analysis results including description and README content
        """
        if self.caching_enabled:
            # Check cache for existing analysis
            cache_key = self._generate_analysis_cache_key(repo.full_name)
            cached_analysis = self.cache.get(cache_key)
            if cached_analysis:
                print(f"\rFound cached analysis for {repo.name}", end="", flush=True)
                return self._deserialize_analysis(cached_analysis)
        
        # Get basic repository data
        repo_data = {
            'name': repo.name,
            'description': repo.description or '',
            'url': repo.html_url,
            'readme': self.get_repo_readme(repo) or '',
            'topics': repo.get_topics(),
            'is_archived': repo.archived,
            'last_updated': repo.updated_at.isoformat() if repo.updated_at else None,
            'has_readme': False
        }
        
        repo_data['has_readme'] = bool(repo_data['readme'])
        
        # Add LLM analysis
        llm_analysis = self.analyze_with_llm(repo_data)
        repo_data.update(llm_analysis)
        
        # Cache the analysis results if enabled
        if self.caching_enabled:
            cache_key = self._generate_analysis_cache_key(repo.full_name)
            serialized_analysis = self._serialize_analysis(repo_data)
            # Cache for 1 hour
            self.cache.set(cache_key, serialized_analysis, time=3600)
        
        return repo_data

    def search_org_repos(self, org_name: str, keywords: List[str]) -> List[Repository]:
        """
        Search for public repositories in an organization that match given keywords.
        Now with caching support if enabled via ENABLE_CACHING environment variable.
        
        Args:
            org_name (str): Name of the GitHub organization
            keywords (List[str]): List of keywords to search for
            
        Returns:
            List[Repository]: List of matching repository objects
        """
        # Check cache if enabled
        if self.caching_enabled:
            cache_key = self._generate_cache_key(org_name, keywords)
            cached_results = self.cache.get(cache_key)
            
            if cached_results:
                print("Found results in cache")
                # Deserialize and return cached results
                return [self._deserialize_repo(repo_data) for repo_data in cached_results]
        
        try:
            org = self.github.get_organization(org_name)
            matching_repos = []
            
            # Get rate limit info
            rate_limit = self.github.get_rate_limit()
            core_rate_limit = rate_limit.core
            print(f"API Rate Limit: {core_rate_limit.remaining}/{core_rate_limit.limit} requests remaining")
            
            if core_rate_limit.remaining == 0:
                reset_time = core_rate_limit.reset.timestamp() - time.time()
                print(f"Rate limit exceeded. Reset in {int(reset_time)} seconds")
                return []
            
            try:
                # Get paginated repository list
                repos_paginated = org.get_repos(type='public')
                total_repos = repos_paginated.totalCount
                print(f"Found {total_repos} public repositories in {org_name}")
                print("\nSearching repositories...")
                
                repos_analyzed = 0
                for repo in repos_paginated:
                    repos_analyzed += 1
                    # Show progress
                    print(f"\rChecking {repo.name} ({repos_analyzed}/{total_repos})", end="", flush=True)
                    
                    # Only check name and description for initial search
                    repo_name = repo.name.lower()
                    repo_description = (repo.description or "").lower()
                    
                    # Check if any keyword matches in name or description
                    for keyword in keywords:
                        keyword = keyword.lower()
                        if keyword in repo_name or keyword in repo_description:
                            matching_repos.append(repo)
                            break
                
                print("\nSearch complete!")
                
                # Cache results if enabled
                if self.caching_enabled:
                    cache_key = self._generate_cache_key(org_name, keywords)
                    serialized_repos = [self._serialize_repo(repo) for repo in matching_repos]
                    # Cache for 1 hour
                    self.cache.set(cache_key, serialized_repos, time=3600)
                    print("Results cached for 1 hour")
                
                return matching_repos
                
            except RateLimitExceededException:
                rate_limit = self.github.get_rate_limit()
                reset_time = rate_limit.core.reset.timestamp() - time.time()
                print(f"\nRate limit exceeded while fetching repos. Reset in {int(reset_time)} seconds")
                return []
                
        except Exception as e:
            print(f"\nError searching organization {org_name}: {str(e)}")
            return []

    def browse_repositories(self, repositories: List[Repository]) -> List[Dict]:
        """
        Step 2: Browse through matched repositories to get detailed information including READMEs.
        Now includes LLM analysis for AI relevance and caching support.
        
        Args:
            repositories (List[Repository]): List of repositories to analyze in detail
            
        Returns:
            List[Dict]: Detailed analysis of each repository
        """
        detailed_results = []
        total_repos = len(repositories)
        
        print(f"\nAnalyzing {total_repos} matched repositories in detail...")
        
        for i, repo in enumerate(repositories, 1):
            print(f"\rAnalyzing {repo.name} ({i}/{total_repos})", end="", flush=True)
            analysis = self.analyze_repository(repo)
            detailed_results.append(analysis)
        
        print("\nDetailed analysis complete!")
        return detailed_results

    def generate_markdown_report(self, org_name: str, detailed_results: List[Dict], min_confidence: int = 0) -> str:
        """
        Generate a markdown report of the analysis results.
        
        Args:
            org_name (str): Name of the GitHub organization
            detailed_results (List[Dict]): List of repository analysis results
            min_confidence (int, optional): Minimum confidence score to include (0-5). Defaults to 0.
            
        Returns:
            str: Markdown formatted report
        """
        # Filter results based on minimum confidence
        filtered_results = [repo for repo in detailed_results if repo['confidence_score'] >= min_confidence]
        
        # Start with report header
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report = f"""# AI Repository Analysis Report
## Organization: {org_name}
Generated on: {now}

This report analyzes repositories for AI/ML/LLM-related content and provides confidence scores.
Minimum confidence threshold: {min_confidence}/5

## Analysis Summary
Total repositories analyzed: {len(detailed_results)}
Repositories meeting confidence threshold: {len(filtered_results)}

### Confidence Score Distribution:
"""
        # Calculate confidence score distribution
        score_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 0: 0}  # Include 0 for errors
        for repo in filtered_results:  # Only count filtered results
            score_distribution[repo['confidence_score']] += 1
        
        # Add distribution to report
        confidence_labels = {
            5: "🟣 Definitely AI-related",
            4: "🔵 Likely AI-related",
            3: "🟡 Possibly AI-related",
            2: "🟠 Probably not AI-related",
            1: "🔴 Definitely not AI-related",
            0: "⚪️ Error/Unknown"
        }
        
        for score in sorted(score_distribution.keys(), reverse=True):
            if score_distribution[score] > 0:
                report += f"- {confidence_labels[score]}: {score_distribution[score]} repositories\n"
        
        if not filtered_results:
            report += "\nNo repositories meet the minimum confidence threshold.\n"
            return report
            
        report += "\n## Detailed Analysis\n\n"
        
        # Sort repositories by multiple criteria:
        # 1. Confidence score (high to low)
        # 2. Active status (active first)
        # 3. Last updated date (recent first)
        # 4. Repository name (alphabetical)
        def sort_key(repo):
            # Parse last_updated string to datetime, use epoch start if None
            last_updated = datetime.fromisoformat(repo['last_updated']) if repo['last_updated'] else datetime.min
            return (
                -repo['confidence_score'],  # Negative for descending order
                repo['is_archived'],        # False before True
                -last_updated.timestamp(),  # Negative for descending order
                repo['name'].lower()        # Alphabetical by name
            )
        
        sorted_results = sorted(filtered_results, key=sort_key)  # Sort filtered results
        
        # Group repositories by confidence score for better organization
        current_score = None
        for repo in sorted_results:
            # Add section header when confidence score changes
            if current_score != repo['confidence_score']:
                current_score = repo['confidence_score']
                score_label = confidence_labels[current_score]
                report += f"\n### {score_label} (Score: {current_score}/5)\n\n"
            
            # Create status badges
            status_badge = "🟢 Active" if not repo['is_archived'] else "🔒 Archived"
            readme_badge = "📘 README" if repo['has_readme'] else "❌ No README"
            
            # Format last updated date for better readability
            last_updated = datetime.fromisoformat(repo['last_updated']).strftime("%Y-%m-%d") if repo['last_updated'] else "Unknown"
            
            report += f"""#### [{repo['name']}]({repo['url']})
{status_badge} | {readme_badge} | Last Updated: {last_updated}

**Description:** {repo['description'] or 'No description provided'}

**Topics:** {', '.join(repo['topics']) if repo['topics'] else 'No topics'}

**Analysis:** {repo['reason']}

---
"""
        
        return report

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='GitHub Organization AI Repository Scanner')
    parser.add_argument('--min-confidence', type=int, choices=range(0, 6), default=0,
                      help='Minimum confidence score (0-5) for including repositories in the report')
    args = parser.parse_args()

    # Example usage - no token needed for public data
    scanner = GithubOrgScanner()
    org_name = "DataDog"  # Using DataDog as specified in instructions
    keywords = ["llm", "ai", "gpt", "machine learning"]
    
    # Step 1: Search for repositories by name and description (now with caching)
    matching_repos = scanner.search_org_repos(org_name, keywords)
    print(f"\nFound {len(matching_repos)} potentially relevant repositories")
    
    # Step 2: Get detailed information including READMEs for matched repositories (limit to 10)
    repos_to_analyze = matching_repos[:10]  # Take first 10 repos
    
    # For testing purposes, try to include documentor repository if we're scanning DataDog
    if org_name == "DataDog":
        try:
            documentor = scanner.github.get_repo("DataDog/documentor")
            if documentor not in repos_to_analyze:
                repos_to_analyze.append(documentor)
                print("Added documentor repository for testing")
        except:
            print("Note: documentor repository not found or not accessible")
    
    print(f"Analyzing {len(repos_to_analyze)} repositories...")
    detailed_results = scanner.browse_repositories(repos_to_analyze)
    
    # Generate markdown report with minimum confidence filter
    report = scanner.generate_markdown_report(org_name, detailed_results, args.min_confidence)
    
    # Create reports directory if it doesn't exist
    os.makedirs('reports', exist_ok=True)
    
    # Save report to file in reports directory
    report_filename = os.path.join('reports', f"ai_repos_report_{org_name.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
    with open(report_filename, 'w') as f:
        f.write(report)
    print(f"\nReport generated: {report_filename}")
    
    # Also print results to console for immediate viewing
    print(f"\nAnalyzed {len(detailed_results)} repositories in detail:")
    # Only show repositories that meet the minimum confidence threshold
    filtered_results = [repo for repo in detailed_results if repo['confidence_score'] >= args.min_confidence]
    for repo in filtered_results:
        print(f"\nRepository: {repo['name']}")
        print(f"Description: {repo['description']}")
        print(f"URL: {repo['url']}")
        if repo['topics']:
            print(f"Topics: {', '.join(repo['topics'])}")
        if repo['is_archived']:
            print("Status: Archived")
        print(f"Last Updated: {repo['last_updated']}")
        print(f"README: {'Found' if repo['has_readme'] else 'Not found'}")
        if repo['readme']:
            print(f"README Length: {len(repo['readme'])} characters")
        print(f"AI Confidence Score: {repo['confidence_score']}/5")
        print(f"Reason: {repo['reason']}")
        print("-" * 80)

if __name__ == "__main__":
    main() 