from github import Github
from github.Repository import Repository
from github.Organization import Organization
from github.GithubException import RateLimitExceededException
from typing import List, Dict, Optional
import os
import time
import base64
from dotenv import load_dotenv
from litellm import completion

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
        Now includes LLM analysis for AI relevance.
        
        Args:
            repo (Repository): The GitHub repository object
            
        Returns:
            Dict: Analysis results including description and README content
        """
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
        
        return repo_data

    def search_org_repos(self, org_name: str, keywords: List[str]) -> List[Repository]:
        """
        Search for public repositories in an organization that match given keywords.
        This is step 1: only searching names and descriptions, not fetching READMEs yet.
        
        Args:
            org_name (str): Name of the GitHub organization
            keywords (List[str]): List of keywords to search for
            
        Returns:
            List[Repository]: List of matching repository objects
        """
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
        Now includes LLM analysis for AI relevance.
        
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

def main():
    # Example usage - no token needed for public data
    scanner = GithubOrgScanner()
    org_name = "DataDog"  # Using DataDog as specified in instructions
    keywords = ["llm", "ai", "gpt", "machine learning"]
    
    # Step 1: Search for repositories by name and description
    matching_repos = scanner.search_org_repos(org_name, keywords)
    print(f"\nFound {len(matching_repos)} potentially relevant repositories")
    
    # Step 2: Get detailed information including READMEs for matched repositories (limit to 10)
    repos_to_analyze = matching_repos[:10]  # Take first 10 repos
    print(f"Analyzing first {len(repos_to_analyze)} repositories...")
    detailed_results = scanner.browse_repositories(repos_to_analyze)
    
    # Output results
    print(f"\nAnalyzed {len(detailed_results)} repositories in detail:")
    for repo in detailed_results:
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