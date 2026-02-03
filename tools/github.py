"""
GitHub Integration Tools for Orion
Manage repos, issues, PRs via GitHub API.
"""

import os
import logging
from typing import Optional
from langchain_core.tools import tool

logger = logging.getLogger("Orion")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


def _get_headers():
    """Get GitHub API headers"""
    if not GITHUB_TOKEN:
        return None
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }


@tool
def github_list_repos(username: Optional[str] = None) -> str:
    """
    List GitHub repositories. If username not provided, lists authenticated user's repos.
    
    Args:
        username: GitHub username (optional, defaults to authenticated user)
    """
    if not GITHUB_TOKEN:
        return "❌ GITHUB_TOKEN not configured. Get one at https://github.com/settings/tokens"
    
    try:
        import httpx
        
        if username:
            url = f"https://api.github.com/users/{username}/repos"
        else:
            url = "https://api.github.com/user/repos"
        
        response = httpx.get(url, headers=_get_headers(), timeout=30)
        response.raise_for_status()
        repos = response.json()
        
        if not repos:
            return "📁 No repositories found."
        
        output = ["📁 **GitHub Repositories**\n"]
        for repo in repos[:15]:  # Limit to 15
            stars = repo.get('stargazers_count', 0)
            lang = repo.get('language', 'Unknown')
            private = "🔒" if repo.get('private') else "🌐"
            output.append(f"{private} **{repo['name']}** ({lang}) ⭐ {stars}")
            if repo.get('description'):
                output.append(f"   {repo['description'][:80]}")
        
        logger.info(f"GitHub: Listed {len(repos)} repos")
        return "\n".join(output)
        
    except Exception as e:
        return f"❌ GitHub error: {str(e)}"


@tool
def github_list_issues(repo: str, state: str = "open") -> str:
    """
    List issues in a GitHub repository.
    
    Args:
        repo: Repository in format "owner/repo" (e.g., "mayank29malhotra/Orion-AI_Personal-Assistant")
        state: Issue state - "open", "closed", or "all" (default: "open")
    """
    if not GITHUB_TOKEN:
        return "❌ GITHUB_TOKEN not configured."
    
    try:
        import httpx
        
        url = f"https://api.github.com/repos/{repo}/issues"
        response = httpx.get(
            url, 
            headers=_get_headers(), 
            params={"state": state, "per_page": 20},
            timeout=30
        )
        response.raise_for_status()
        issues = response.json()
        
        if not issues:
            return f"📋 No {state} issues in {repo}"
        
        output = [f"📋 **Issues in {repo}** ({state})\n"]
        for issue in issues:
            if 'pull_request' in issue:
                continue  # Skip PRs
            labels = ", ".join([l['name'] for l in issue.get('labels', [])])
            output.append(f"#{issue['number']} - {issue['title']}")
            if labels:
                output.append(f"   🏷️ {labels}")
        
        logger.info(f"GitHub: Listed issues for {repo}")
        return "\n".join(output)
        
    except Exception as e:
        return f"❌ GitHub error: {str(e)}"


@tool
def github_create_issue(repo: str, title: str, body: str = "", labels: str = "") -> str:
    """
    Create a new issue in a GitHub repository.
    
    Args:
        repo: Repository in format "owner/repo"
        title: Issue title
        body: Issue description/body (optional)
        labels: Comma-separated labels (optional, e.g., "bug,urgent")
    """
    if not GITHUB_TOKEN:
        return "❌ GITHUB_TOKEN not configured."
    
    try:
        import httpx
        
        url = f"https://api.github.com/repos/{repo}/issues"
        data = {"title": title, "body": body}
        
        if labels:
            data["labels"] = [l.strip() for l in labels.split(",")]
        
        response = httpx.post(url, headers=_get_headers(), json=data, timeout=30)
        response.raise_for_status()
        issue = response.json()
        
        logger.info(f"GitHub: Created issue #{issue['number']} in {repo}")
        return f"✅ Issue created: #{issue['number']} - {title}\n🔗 {issue['html_url']}"
        
    except Exception as e:
        return f"❌ GitHub error: {str(e)}"


@tool
def github_get_repo_info(repo: str) -> str:
    """
    Get detailed information about a GitHub repository.
    
    Args:
        repo: Repository in format "owner/repo"
    """
    if not GITHUB_TOKEN:
        return "❌ GITHUB_TOKEN not configured."
    
    try:
        import httpx
        
        url = f"https://api.github.com/repos/{repo}"
        response = httpx.get(url, headers=_get_headers(), timeout=30)
        response.raise_for_status()
        r = response.json()
        
        output = [
            f"📁 **{r['full_name']}**",
            f"📝 {r.get('description', 'No description')}",
            f"⭐ Stars: {r['stargazers_count']} | 🍴 Forks: {r['forks_count']}",
            f"👁️ Watchers: {r['watchers_count']} | 📋 Issues: {r['open_issues_count']}",
            f"🔤 Language: {r.get('language', 'Unknown')}",
            f"📅 Created: {r['created_at'][:10]} | Updated: {r['updated_at'][:10]}",
            f"🔗 {r['html_url']}"
        ]
        
        if r.get('homepage'):
            output.append(f"🌐 Homepage: {r['homepage']}")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"❌ GitHub error: {str(e)}"


@tool
def github_search_repos(query: str, language: str = "") -> str:
    """
    Search for GitHub repositories.
    
    Args:
        query: Search query (e.g., "AI assistant python")
        language: Filter by programming language (optional)
    """
    if not GITHUB_TOKEN:
        return "❌ GITHUB_TOKEN not configured."
    
    try:
        import httpx
        
        search_query = query
        if language:
            search_query += f" language:{language}"
        
        url = "https://api.github.com/search/repositories"
        response = httpx.get(
            url, 
            headers=_get_headers(), 
            params={"q": search_query, "sort": "stars", "per_page": 10},
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        repos = data.get('items', [])
        if not repos:
            return f"🔍 No repositories found for: {query}"
        
        output = [f"🔍 **Search results for: {query}**\n"]
        for repo in repos:
            output.append(f"⭐ {repo['stargazers_count']} - **{repo['full_name']}**")
            if repo.get('description'):
                output.append(f"   {repo['description'][:100]}")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"❌ GitHub error: {str(e)}"


@tool
def github_list_pull_requests(repo: str, state: str = "open") -> str:
    """
    List pull requests in a GitHub repository.
    
    Args:
        repo: Repository in format "owner/repo"
        state: PR state - "open", "closed", or "all" (default: "open")
    """
    if not GITHUB_TOKEN:
        return "❌ GITHUB_TOKEN not configured."
    
    try:
        import httpx
        
        url = f"https://api.github.com/repos/{repo}/pulls"
        response = httpx.get(
            url, 
            headers=_get_headers(), 
            params={"state": state, "per_page": 15},
            timeout=30
        )
        response.raise_for_status()
        prs = response.json()
        
        if not prs:
            return f"🔀 No {state} pull requests in {repo}"
        
        output = [f"🔀 **Pull Requests in {repo}** ({state})\n"]
        for pr in prs:
            output.append(f"#{pr['number']} - {pr['title']}")
            output.append(f"   By @{pr['user']['login']} | {pr['head']['ref']} → {pr['base']['ref']}")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"❌ GitHub error: {str(e)}"


# ============ TOOL EXPORTS ============

def get_github_tools():
    """Get all GitHub tools."""
    return [
        github_list_repos,
        github_list_issues,
        github_create_issue,
        github_get_repo_info,
        github_search_repos,
        github_list_pull_requests,
    ]
