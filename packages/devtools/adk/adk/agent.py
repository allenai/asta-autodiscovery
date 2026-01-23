"""ADK Web entrypoint for the experiment workflow agent."""

from agents import experiment_workflow_agent

# ADK Web looks for a top-level ``root_agent`` in agent.py.
root_agent = experiment_workflow_agent
