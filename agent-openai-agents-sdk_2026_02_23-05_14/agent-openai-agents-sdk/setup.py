from setuptools import setup, find_packages

setup(
    name="agent-openai-agents-sdk",
    version="0.1.0",
    packages=find_packages(include=["agent_server*", "local_agents*", "api*", "ui*", "scripts*", "sdk*"]),
    py_modules=["verify_setup", "standalone_server", "setup_and_launch"],
    include_package_data=True,
    install_requires=[
        "openai>=1.0",
        "fastapi",
        "uvicorn",
        "gradio",
        "httpx",
        "pytest",
        "python-dotenv",
        "mlflow>=2.0",
    ],
    extras_require={
        "databricks": [
            "databricks-openai>=0.9.0",
            "databricks-agents",
            "unitycatalog-openai[databricks]>=0.2.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "perfect-agent=local_agents.perfect_agent.runner:main",
            "quickstart=scripts.quickstart:main",
            "verify-setup=verify_setup:main",
            "start-app=scripts.start_app:main",
            "start-server=agent_server.start_server:main",
            "agent-evaluate=agent_server.evaluate_agent:evaluate",
            "discover-tools=scripts.discover_tools:main",
        ]
    },
    package_data={
        "local_agents.perfect_agent": ["system_prompt.txt"],
    },
)
