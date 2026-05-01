"""Skills package for local_agents/perfect_agent."""
from local_agents.perfect_agent.skills.search_code import search_code
from local_agents.perfect_agent.skills.git_ops import git_ops
from local_agents.perfect_agent.skills.run_tests import run_tests
from local_agents.perfect_agent.skills.web_search import web_search
from local_agents.perfect_agent.skills.code_review import code_review

__all__ = ["search_code", "git_ops", "run_tests", "web_search", "code_review"]
