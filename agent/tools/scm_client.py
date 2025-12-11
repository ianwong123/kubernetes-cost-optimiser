import os
import yaml
from typing import Any, Dict, Optional
from github import Github
from abc import ABC, abstractmethod 

class SCMClient(ABC):
    @abstractmethod
    def create_pr(self, job_id: str, deployment_name: str, patch: Dict[str, Any], reasoning: str) -> Optional[str]:
        """
        Create a branch, applies the patch, and opens a PR.
        Returns the PR URL if successful, none otherwise"
        """
        pass

# Reference: https://pygithub.readthedocs.io/en/latest/apis.html
class GitHubClient(SCMClient):
    def __init__(self):
        token = os.getenv("GH_TOKEN")
        repo_name = os.getenv("GH_REPO")

        if not token or not repo_name:
            raise ValueError("GitHub token or repository name not set in environment variables")

        self.g = Github(token)
        self.repo = self.g.get_repo(repo_name)

    # the idea is to create a branch, get file content, apply patch, commit, and create a PR
    def create_pr(self, job_id: str, deployment_name: str, patch: Dict[str, Any], reasoning: str) -> Optional[str]:
        base_branch = "main"
        new_branch = f"optimise-{deployment_name}--{job_id[:8]}"

        # create a new branch from the latest commit sha of main
        try:
            try:
                gb = self.repo.get_branch(base_branch)
                self.repo.create_git_ref(ref=f"refs/heads/{new_branch}", sha=gb.commit.sha)
            except Exception:
                print(f"Branch {new_branch} already exist")

            # get the file content
            file_path=f"deployments/google-online-boutique/base/{deployment_name}.yaml"
            try:
                contents = self.repo.get_contents(file_path, ref=new_branch)
            except Exception:
                print(f"File not found at path: {file_path}")
            # decode from bytes 
            decoded_content = contents.decoded_content.decode("utf-8")

            # apply patch
            yaml_content = yaml.safe_load(decoded_content)
            success = self._apply_patch(yaml_content, patch)
            if not success:
                print("Failed to apply patch, could not find container")
                return None

            # format yaml
            new_content = yaml.dump(yaml_content, default_flow_style=False, sort_keys=False, width=1000)

            # commit the change
            self.repo.update_file(path=contents.path, message=f"optimise {deployment_name} resource", content=new_content, sha=contents.sha, branch=new_branch)

            # open pr
            pr = self.repo.create_pull(title=f"Optimise {deployment_name} resource", body=f"##Reasoning\n{reasoning}\n\n -Changes based on metrics analysis", head=new_branch, base=base_branch)
            return pr.html_url

        except Exception as e:
            print(f"SCM failed: {e}")
            return None


    # if pr is accepted, apply the patch
    def _apply_patch(self, manifests: Dict, patch: Dict):
        try:
            containers = manifests['spec']['template']['spec']['containers']

            if not containers:
                return False

            # target the first container 
            target_container = containers[0]

            if 'resources' in patch:
                target_container['resources'] = patch['resources']
                return True

            return False

        except KeyError:
            print("Coudld not find container spec in manifest' to apply patch")
            return False