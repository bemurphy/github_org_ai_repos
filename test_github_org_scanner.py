import unittest
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime

# Attempt to import the class and dependent types
# This might require adjustments based on the actual file structure and sys.path
# For now, assuming github_org_scanner.py is in the same directory or accessible via PYTHONPATH
from github_org_scanner import GithubOrgScanner
from github.Repository import Repository # For spec if needed

class TestGithubOrgScanner(unittest.TestCase):

    def _create_mock_repo(self, name, description, archived, topics=None, html_url=None, updated_at=None):
        repo = Mock(spec=Repository)
        repo.name = name
repo.description = description
        repo.archived = archived
        repo.get_topics = Mock(return_value=topics if topics is not None else [])
        repo.html_url = html_url if html_url else f"https://github.com/org/{name}"
        repo.updated_at = updated_at if updated_at is not None else datetime.now()
        # Add full_name attribute, as it's used in _generate_analysis_cache_key
        repo.full_name = f"org/{name}" 
        return repo

    @patch('github_org_scanner.os.getenv') # Mock getenv to control caching
    @patch('github_org_scanner.Github')
    def test_search_repos_excludes_archived_by_default(self, MockGithub, mock_getenv):
        # Disable caching for this test
        mock_getenv.side_effect = lambda key, default='': {'ENABLE_CACHING': 'false', 'LLM_MODEL': 'dummy'}.get(key, default)

        mock_org = Mock()
        MockGithub.return_value.get_organization.return_value = mock_org

        repo1_active = self._create_mock_repo("active-repo", "Keyword repo", False, ["keyword"])
        repo2_archived = self._create_mock_repo("archived-repo", "Keyword repo", True, ["keyword"])
        repo3_active_no_keyword = self._create_mock_repo("active-no-keyword", "Non relevant", False)
        repo4_archived_no_keyword = self._create_mock_repo("archived-no-keyword", "Non relevant", True)

        mock_org.get_repos.return_value = [
            repo1_active, 
            repo2_archived, 
            repo3_active_no_keyword,
            repo4_archived_no_keyword
        ]

        scanner = GithubOrgScanner()
        keywords = ["keyword"]
        
        # Test with include_archived_repos=False (default or explicit)
        results = scanner.search_org_repos("test-org", keywords, include_archived_repos=False)
        
        self.assertEqual(len(results), 1)
        self.assertIn(repo1_active, results)
        self.assertNotIn(repo2_archived, results)

    @patch('github_org_scanner.os.getenv')
    @patch('github_org_scanner.Github')
    def test_search_repos_includes_archived_when_flagged(self, MockGithub, mock_getenv):
        # Disable caching
        mock_getenv.side_effect = lambda key, default='': {'ENABLE_CACHING': 'false', 'LLM_MODEL': 'dummy'}.get(key, default)

        mock_org = Mock()
        MockGithub.return_value.get_organization.return_value = mock_org

        repo1_active = self._create_mock_repo("active-repo", "Keyword repo", False, ["keyword"])
        repo2_archived = self._create_mock_repo("archived-repo", "Keyword repo", True, ["keyword"])
        repo3_active_no_keyword = self._create_mock_repo("active-no-keyword", "Non relevant", False)
        
        mock_org.get_repos.return_value = [repo1_active, repo2_archived, repo3_active_no_keyword]

        scanner = GithubOrgScanner()
        keywords = ["keyword"]
        results = scanner.search_org_repos("test-org", keywords, include_archived_repos=True)
        
        self.assertEqual(len(results), 2)
        self.assertIn(repo1_active, results)
        self.assertIn(repo2_archived, results)

    @patch('github_org_scanner.os.getenv')
    def test_report_header_archived_excluded(self, mock_getenv):
        mock_getenv.side_effect = lambda key, default='': {'ENABLE_CACHING': 'false', 'LLM_MODEL': 'dummy'}.get(key, default)
        scanner = GithubOrgScanner()
        mock_results = [{
            'name': 'repo1', 'description': 'desc1', 'url': 'url1', 
            'readme': 'readme1', 'topics': [], 'is_archived': False, 
            'last_updated': datetime.now().isoformat(), 'has_readme': True,
            'confidence_score': 3, 'reason': 'reason1'
        }]
        report = scanner.generate_markdown_report("test-org", mock_results, 0, archived_included=False)
        self.assertIn("Archived repositories: Excluded from scan", report)

    @patch('github_org_scanner.os.getenv')
    def test_report_header_archived_included(self, mock_getenv):
        mock_getenv.side_effect = lambda key, default='': {'ENABLE_CACHING': 'false', 'LLM_MODEL': 'dummy'}.get(key, default)
        scanner = GithubOrgScanner()
        mock_results = [{
            'name': 'repo1', 'description': 'desc1', 'url': 'url1', 
            'readme': 'readme1', 'topics': [], 'is_archived': False, 
            'last_updated': datetime.now().isoformat(), 'has_readme': True,
            'confidence_score': 3, 'reason': 'reason1'
        }]
        report = scanner.generate_markdown_report("test-org", mock_results, 0, archived_included=True)
        self.assertIn("Archived repositories: Included in scan", report)

# This allows running the tests from the command line
if __name__ == '__main__':
    unittest.main()
