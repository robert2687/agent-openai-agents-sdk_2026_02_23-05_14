"""Skills package for local_agents/perfect_agent."""
from local_agents.perfect_agent.skills.search_code import search_code
from local_agents.perfect_agent.skills.git_ops import git_ops
from local_agents.perfect_agent.skills.run_tests import run_tests
from local_agents.perfect_agent.skills.web_search import web_search
from local_agents.perfect_agent.skills.code_review import code_review
from local_agents.perfect_agent.skills.todo_scan import todo_scan
from local_agents.perfect_agent.skills.list_symbols import list_symbols
from local_agents.perfect_agent.skills.dependency_check import dependency_check
from local_agents.perfect_agent.skills.code_generator import code_generator
from local_agents.perfect_agent.skills.app_creator import app_creator

__all__ = [
	"search_code",
	"git_ops",
	"run_tests",
	"web_search",
	"code_review",
	"todo_scan",
	"list_symbols",
	"dependency_check",
	"code_generator",
	"app_creator",
]
