"""
Git operations for cloning, branching, committing, and pushing.
"""
import os
import logging
import shutil
from pathlib import Path
from git import Repo, GitCommandError

logger = logging.getLogger(__name__)


class GitOperations:
    """Handles all Git operations for the worker."""

    def __init__(self, repo_url: str, work_dir: str = "/tmp/git-workspace"):
        """
        Initialize Git operations.

        Args:
            repo_url: Git repository URL (HTTPS with token or SSH)
            work_dir: Local directory for Git operations
        """
        self.repo_url = repo_url
        self.work_dir = Path(work_dir)
        self.repo = None
        
        # Ensure work directory exists
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def clone_or_update(self, token: str = None) -> bool:
        """
        Clone repository if not exists, otherwise pull latest changes.

        Args:
            token: GitHub Personal Access Token for authentication

        Returns:
            True if successful, False otherwise
        """
        try:
            repo_path = self.work_dir / "repo"

            # Add token to URL if provided
            if token and self.repo_url.startswith("https://"):
                # Format: https://TOKEN@github.com/owner/repo.git
                auth_url = self.repo_url.replace("https://", f"https://{token}@")
            else:
                auth_url = self.repo_url

            if repo_path.exists():
                logger.info("Repository exists, pulling latest changes...")
                self.repo = Repo(repo_path)
                
                # Checkout main branch and pull
                self.repo.git.checkout(os.getenv("GITHUB_DEFAULT_BRANCH", "main"))
                origin = self.repo.remotes.origin
                origin.pull()
                
                logger.info("Successfully updated repository")
            else:
                logger.info(f"Cloning repository from {self.repo_url}...")
                self.repo = Repo.clone_from(auth_url, repo_path)
                logger.info("Successfully cloned repository")

            return True

        except GitCommandError as e:
            logger.error(f"Git command error: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Error cloning/updating repository: {e}", exc_info=True)
            return False

    def create_branch(self, branch_name: str) -> bool:
        """
        Create and checkout a new branch.

        Args:
            branch_name: Name of the new branch

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.repo:
                logger.error("Repository not initialized")
                return False

            # Create and checkout new branch
            new_branch = self.repo.create_head(branch_name)
            new_branch.checkout()
            
            logger.info(f"Created and checked out branch: {branch_name}")
            return True

        except Exception as e:
            logger.error(f"Error creating branch: {e}", exc_info=True)
            return False

    def commit_changes(self, file_path: str, commit_message: str) -> bool:
        """
        Stage and commit changes.

        Args:
            file_path: Path to file relative to repo root
            commit_message: Commit message

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.repo:
                logger.error("Repository not initialized")
                return False

            # Stage the file
            self.repo.index.add([file_path])
            
            # Commit
            self.repo.index.commit(commit_message)
            
            logger.info(f"Committed changes to {file_path}")
            return True

        except Exception as e:
            logger.error(f"Error committing changes: {e}", exc_info=True)
            return False

    def push_branch(self, branch_name: str, token: str = None) -> bool:
        """
        Push branch to remote.

        Args:
            branch_name: Name of the branch to push
            token: GitHub token for authentication

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.repo:
                logger.error("Repository not initialized")
                return False

            # Configure remote with token if provided
            if token:
                origin = self.repo.remotes.origin
                auth_url = self.repo_url.replace("https://", f"https://{token}@")
                origin.set_url(auth_url)

            # Push the branch
            origin = self.repo.remotes.origin
            origin.push(branch_name)
            
            logger.info(f"Successfully pushed branch: {branch_name}")
            return True

        except Exception as e:
            logger.error(f"Error pushing branch: {e}", exc_info=True)
            return False

    def get_repo_path(self) -> Path:
        """Get the path to the local repository."""
        return self.work_dir / "repo"

    def cleanup(self):
        """Clean up the workspace."""
        try:
            if self.work_dir.exists():
                shutil.rmtree(self.work_dir)
                logger.info("Cleaned up workspace")
        except Exception as e:
            logger.error(f"Error cleaning up: {e}", exc_info=True)
