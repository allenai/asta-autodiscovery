"""Pydantic response models for the metrics API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DailyMetrics(BaseModel):
    """Metrics aggregated for a single day."""

    date: str = Field(..., description="Date in YYYY-MM-DD format")
    runs_started: int = Field(0)
    runs_succeeded: int = Field(0)
    runs_failed: int = Field(0)
    llm_cost_usd: float = Field(0.0)


class OverviewMetrics(BaseModel):
    """Overall dashboard metrics."""

    total_runs: int = Field(0, description="Total number of runs")
    succeeded_runs: int = Field(0)
    failed_runs: int = Field(0)
    cancelled_runs: int = Field(0)
    success_rate: float = Field(0.0, description="Succeeded / (Succeeded + Failed)")
    unique_users: int = Field(0)
    total_experiments: int = Field(0)
    total_experiments_requested: int = Field(0)
    experiment_completion_rate: float = Field(0.0)
    llm_cost_usd: float = Field(0.0)
    # Cost-per-hypothesis breakdown (only jobs with LLM usage data)
    hypotheses_with_usage: int = Field(0, description="Completed experiments from runs with LLM usage data")
    cost_per_hypothesis_usd: float | None = Field(None)
    share_rate: float = Field(0.0, description="Runs with is_shared / total runs")
    runs_by_status: dict[str, int] = Field(default_factory=dict)
    time_series: list[DailyMetrics] = Field(default_factory=list)
    cache_refreshed_at: str | None = Field(None)


class UserMetricsSummary(BaseModel):
    """Per-user summary row for the users table."""

    userid: str
    total_runs: int = Field(0)
    succeeded_runs: int = Field(0)
    failed_runs: int = Field(0)
    success_rate: float = Field(0.0)
    total_experiments: int = Field(0)
    llm_cost_usd: float = Field(0.0)
    shared_runs: int = Field(0)
    last_activity: str | None = Field(None, description="Most recent run created_at")


class UserDetailMetrics(BaseModel):
    """Detailed metrics for a single user."""

    userid: str
    summary: UserMetricsSummary
    runs: list[RunSummary] = Field(default_factory=list)


class RunSummary(BaseModel):
    """Summary of a single run (used in user detail and overview)."""

    runid: str
    userid: str
    status: str
    name: str | None = None
    domain: str | None = None
    created_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None
    n_experiments_requested: int = Field(0)
    n_experiments_completed: int = Field(0)
    is_shared: bool = Field(False)
    model: str | None = None
    llm_cost_usd: float = Field(0.0)


class LLMUsageSummary(BaseModel):
    """LLM usage summary (mirrors llm_usage_summary.json structure)."""

    totals: dict[str, Any] = Field(default_factory=dict)
    by_model: dict[str, Any] = Field(default_factory=dict)
    by_agent: dict[str, Any] = Field(default_factory=dict)
    by_node: dict[str, Any] = Field(default_factory=dict)
    by_component: dict[str, Any] = Field(default_factory=dict)


class RunMetrics(BaseModel):
    """Detailed metrics for a single run."""

    runid: str
    userid: str
    status: str
    name: str | None = None
    domain: str | None = None
    created_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None
    llm_usage_summary: LLMUsageSummary | None = None
    llm_cost_usd: float = Field(0.0)
    llm_cost_by_model: dict[str, float] = Field(default_factory=dict)
    n_experiments_requested: int = Field(0)
    n_experiments_completed: int = Field(0)
    is_shared: bool = Field(False)
    model: str | None = None


class AggregatedUsageBucket(BaseModel):
    """Aggregated LLM usage with statistics across runs."""

    total_calls: int = Field(0)
    total_prompt_tokens: int = Field(0)
    total_completion_tokens: int = Field(0)
    total_reasoning_tokens: int = Field(0)
    total_tokens: int = Field(0)
    total_cost_usd: float = Field(0.0)
    total_prompt_cost_usd: float = Field(0.0)
    total_completion_cost_usd: float = Field(0.0)
    total_reasoning_cost_usd: float = Field(0.0)
    run_count: int = Field(0, description="Number of runs contributing to this bucket")
    mean_tokens_per_run: float = Field(0.0)
    stddev_tokens_per_run: float = Field(0.0)
    mean_cost_per_run: float = Field(0.0)
    stddev_cost_per_run: float = Field(0.0)


class AggregatedUsageResponse(BaseModel):
    """Aggregated LLM usage across all runs with usage data."""

    totals: AggregatedUsageBucket = Field(default_factory=AggregatedUsageBucket)
    by_model: dict[str, AggregatedUsageBucket] = Field(default_factory=dict)
    by_agent: dict[str, AggregatedUsageBucket] = Field(default_factory=dict)
    by_node: dict[str, AggregatedUsageBucket] = Field(default_factory=dict)
    by_component: dict[str, AggregatedUsageBucket] = Field(default_factory=dict)
    runs_included: int = Field(0)


class CacheStatusResponse(BaseModel):
    """Response for cache status endpoint."""

    refreshed_at: str | None = None
    job_count: int = Field(0)
    user_count: int = Field(0)
    scan_duration_seconds: float | None = None
    is_refreshing: bool = Field(False)


class UsersListResponse(BaseModel):
    """Response for the users list endpoint."""

    users: list[UserMetricsSummary]
    cache_refreshed_at: str | None = None


# Resolve forward reference for UserDetailMetrics.runs
UserDetailMetrics.model_rebuild()
