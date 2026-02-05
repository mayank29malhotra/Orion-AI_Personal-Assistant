"""
Developer Agent for Orion
=========================

Specialized sub-agent for GitHub, coding, and developer tasks.

Capabilities:
- GitHub repository management
- Issue tracking and creation
- Python code execution
- Code assistance
"""

from typing import List, Optional
from langchain_core.tools import tool, BaseTool

from agents.base_agent import BaseSubAgent


class DeveloperAgent(BaseSubAgent):
    """
    Developer Agent - handles GitHub, coding, and development tasks.
    
    This agent specializes in:
    - GitHub repository management
    - Issue tracking and creation
    - Python code execution (REPL)
    - Code assistance and debugging
    """
    
    def __init__(self, tools: Optional[List[BaseTool]] = None):
        if tools is None:
            tools = get_developer_agent_tools()
        super().__init__(tools)
    
    def get_system_prompt(self) -> str:
        return """You are the Developer Agent, a specialized sub-agent of Orion AI.
Your expertise is in GitHub operations, coding assistance, and development tasks.

🎯 YOUR CAPABILITIES:

💻 GITHUB OPERATIONS:
- List repositories (your own or any user's)
- View repository details
- List issues (open, closed, or all)
- Create new issues with labels
- Search repositories by topic/language
- Check repo stats and activity

🐍 PYTHON EXECUTION:
- Execute Python code snippets
- Run calculations and data processing
- Test code logic
- Debug Python errors

🔧 CODE ASSISTANCE:
- Help debug code errors
- Explain code concepts
- Suggest improvements
- Generate code snippets

📋 ISSUE MANAGEMENT:
- Create well-formatted issues
- Add appropriate labels
- Link related issues
- Follow issue templates

⚠️ BEST PRACTICES:
- Always validate repo format (owner/repo)
- Use descriptive issue titles
- Add relevant labels to issues
- For code execution, handle errors gracefully
- Never expose sensitive tokens

🔧 AVAILABLE TOOLS:
- github_list_repos: List repositories
- github_list_issues: View repo issues
- github_create_issue: Create new issue
- github_search_repos: Search GitHub repos
- python_repl: Execute Python code

💡 TIPS:
- For repo operations, always use format: owner/repo
- For issues, include steps to reproduce bugs
- For code execution, print outputs explicitly
"""

    def get_capabilities(self) -> List[str]:
        return [
            "List GitHub repositories",
            "View repository issues",
            "Create GitHub issues with labels",
            "Search repositories by topic/language",
            "Execute Python code snippets",
            "Debug code errors",
            "Generate code suggestions",
            "Repository statistics"
        ]


def get_developer_agent_tools() -> List[BaseTool]:
    """Get all tools for the Developer Agent."""
    from tools.github import (
        github_list_repos,
        github_list_issues,
        github_create_issue,
        github_search_repos
    )
    
    tools = [
        github_list_repos,
        github_list_issues,
        github_create_issue,
        github_search_repos,
    ]
    
    # Try to add Python REPL if available
    try:
        from langchain_experimental.tools import PythonREPLTool
        tools.append(PythonREPLTool())
    except ImportError:
        pass
    
    return tools


# Additional developer tools
@tool
def analyze_code_error(error_message: str, code_snippet: str = "") -> str:
    """
    Analyze a code error and provide suggestions.
    
    Args:
        error_message: The error message received
        code_snippet: Optional code that caused the error
        
    Returns:
        Analysis and suggestions for fixing the error
    """
    # Common error patterns and solutions
    error_patterns = {
        "ModuleNotFoundError": {
            "cause": "Missing Python package",
            "solution": "Install the package with: pip install <package_name>"
        },
        "ImportError": {
            "cause": "Import problem - package exists but module not found",
            "solution": "Check the import path and package structure"
        },
        "SyntaxError": {
            "cause": "Python syntax error",
            "solution": "Check for missing colons, brackets, or indentation"
        },
        "IndentationError": {
            "cause": "Inconsistent indentation",
            "solution": "Use consistent spaces (4) or tabs throughout"
        },
        "TypeError": {
            "cause": "Wrong data type used",
            "solution": "Check variable types with type() and convert if needed"
        },
        "ValueError": {
            "cause": "Correct type but invalid value",
            "solution": "Validate input data before processing"
        },
        "KeyError": {
            "cause": "Dictionary key doesn't exist",
            "solution": "Use .get() method or check key existence first"
        },
        "AttributeError": {
            "cause": "Object doesn't have the attribute/method",
            "solution": "Check object type and available methods with dir()"
        },
        "IndexError": {
            "cause": "List index out of range",
            "solution": "Check list length before accessing index"
        },
        "FileNotFoundError": {
            "cause": "File or directory doesn't exist",
            "solution": "Check file path and use os.path.exists() to verify"
        },
        "PermissionError": {
            "cause": "Insufficient permissions",
            "solution": "Check file/folder permissions or run with elevated privileges"
        },
        "ConnectionError": {
            "cause": "Network connection failed",
            "solution": "Check internet connection and API endpoint"
        },
        "TimeoutError": {
            "cause": "Operation timed out",
            "solution": "Increase timeout or check network latency"
        },
        "JSONDecodeError": {
            "cause": "Invalid JSON format",
            "solution": "Validate JSON structure and check for trailing commas"
        }
    }
    
    # Detect error type
    detected_errors = []
    for error_type, info in error_patterns.items():
        if error_type.lower() in error_message.lower():
            detected_errors.append((error_type, info))
    
    # Build response
    analysis = f"""
🔍 CODE ERROR ANALYSIS
══════════════════════════════════════════

📛 Error Message:
{error_message}

"""
    
    if code_snippet:
        analysis += f"""📝 Code Snippet:
```python
{code_snippet}
```

"""
    
    if detected_errors:
        for error_type, info in detected_errors:
            analysis += f"""🎯 Detected: {error_type}
   💡 Cause: {info['cause']}
   ✅ Solution: {info['solution']}

"""
    else:
        analysis += """🤔 Error type not recognized.
   💡 Try: 
   - Check the full traceback
   - Google the exact error message
   - Verify all dependencies are installed
   
"""
    
    analysis += """══════════════════════════════════════════
💬 Need more help? Provide the full traceback!
"""
    
    return analysis


@tool
def create_bug_report(
    repo: str,
    title: str,
    description: str,
    steps_to_reproduce: str,
    expected_behavior: str,
    actual_behavior: str
) -> str:
    """
    Create a well-formatted bug report issue on GitHub.
    
    Args:
        repo: Repository in format "owner/repo"
        title: Bug title
        description: Brief description of the bug
        steps_to_reproduce: Steps to reproduce (numbered list)
        expected_behavior: What should happen
        actual_behavior: What actually happens
        
    Returns:
        Confirmation of issue creation
    """
    from tools.github import github_create_issue
    
    body = f"""## 🐛 Bug Report

### Description
{description}

### Steps to Reproduce
{steps_to_reproduce}

### Expected Behavior
{expected_behavior}

### Actual Behavior
{actual_behavior}

### Environment
- OS: [Please fill]
- Python Version: [Please fill]
- Related Dependencies: [Please fill]

---
*This issue was created via Orion AI Developer Agent*
"""
    
    result = github_create_issue.invoke({
        "repo": repo,
        "title": f"🐛 {title}",
        "body": body,
        "labels": "bug"
    })
    
    return f"""
🐛 BUG REPORT CREATED
══════════════════════════════════════════

📁 Repository: {repo}
📌 Title: {title}

{result}
"""


@tool
def create_feature_request(
    repo: str,
    title: str,
    description: str,
    use_case: str,
    proposed_solution: str = ""
) -> str:
    """
    Create a feature request issue on GitHub.
    
    Args:
        repo: Repository in format "owner/repo"
        title: Feature title
        description: Description of the feature
        use_case: Why this feature is needed
        proposed_solution: Optional proposed implementation
        
    Returns:
        Confirmation of issue creation
    """
    from tools.github import github_create_issue
    
    body = f"""## ✨ Feature Request

### Description
{description}

### Use Case
{use_case}

### Proposed Solution
{proposed_solution if proposed_solution else "Open to suggestions"}

### Additional Context
[Add any other context or screenshots here]

---
*This feature request was created via Orion AI Developer Agent*
"""
    
    result = github_create_issue.invoke({
        "repo": repo,
        "title": f"✨ {title}",
        "body": body,
        "labels": "enhancement"
    })
    
    return f"""
✨ FEATURE REQUEST CREATED
══════════════════════════════════════════

📁 Repository: {repo}
📌 Title: {title}

{result}
"""


if __name__ == "__main__":
    # Test the agent
    agent = DeveloperAgent()
    print("Developer Agent initialized")
    print(f"Tools: {[t.name for t in agent.tools]}")
    print(f"\nCapabilities:\n" + "\n".join(f"  • {c}" for c in agent.get_capabilities()))
