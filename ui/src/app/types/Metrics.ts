/**
 * TypeScript types for the metrics dashboard API responses.
 */

export interface DailyMetrics {
    date: string;
    runs_started: number;
    runs_succeeded: number;
    runs_failed: number;
    llm_cost_usd: number;
}

export interface OverviewMetrics {
    total_runs: number;
    succeeded_runs: number;
    failed_runs: number;
    cancelled_runs: number;
    success_rate: number;
    unique_users: number;
    total_experiments: number;
    total_experiments_requested: number;
    experiment_completion_rate: number;
    llm_cost_usd: number;
    hypotheses_with_usage: number;
    cost_per_hypothesis_usd: number | null;
    share_rate: number;
    runs_by_status: Record<string, number>;
    time_series: DailyMetrics[];
    cache_refreshed_at: string | null;
}

export interface UserMetricsSummary {
    userid: string;
    total_runs: number;
    succeeded_runs: number;
    failed_runs: number;
    success_rate: number;
    total_experiments: number;
    llm_cost_usd: number;
    shared_runs: number;
    last_activity: string | null;
}

export interface RunSummary {
    runid: string;
    userid: string;
    status: string;
    name: string | null;
    domain: string | null;
    created_at: string | null;
    finished_at: string | null;
    duration_seconds: number | null;
    n_experiments_requested: number;
    n_experiments_completed: number;
    is_shared: boolean;
    model: string | null;
    llm_cost_usd: number;
}

export interface UserDetailMetrics {
    userid: string;
    summary: UserMetricsSummary;
    runs: RunSummary[];
}

export interface LLMUsageBucket {
    calls: number;
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    reasoning_tokens: number;
}

export interface LLMUsageSummary {
    totals: LLMUsageBucket;
    by_model: Record<string, LLMUsageBucket>;
    by_agent: Record<string, LLMUsageBucket>;
    by_node: Record<string, LLMUsageBucket>;
    by_component: Record<string, LLMUsageBucket>;
}

export interface RunMetrics {
    runid: string;
    userid: string;
    status: string;
    name: string | null;
    domain: string | null;
    created_at: string | null;
    finished_at: string | null;
    duration_seconds: number | null;
    llm_usage_summary: LLMUsageSummary | null;
    llm_cost_usd: number;
    llm_cost_by_model: Record<string, number>;
    n_experiments_requested: number;
    n_experiments_completed: number;
    is_shared: boolean;
    model: string | null;
}

export interface UsersListResponse {
    users: UserMetricsSummary[];
    cache_refreshed_at: string | null;
}

export interface AggregatedUsageBucket {
    total_calls: number;
    total_prompt_tokens: number;
    total_completion_tokens: number;
    total_reasoning_tokens: number;
    total_tokens: number;
    total_cost_usd: number;
    total_prompt_cost_usd: number;
    total_completion_cost_usd: number;
    total_reasoning_cost_usd: number;
    run_count: number;
    mean_tokens_per_run: number;
    stddev_tokens_per_run: number;
    mean_cost_per_run: number;
    stddev_cost_per_run: number;
}

export interface AggregatedUsageResponse {
    totals: AggregatedUsageBucket;
    by_model: Record<string, AggregatedUsageBucket>;
    by_agent: Record<string, AggregatedUsageBucket>;
    by_node: Record<string, AggregatedUsageBucket>;
    by_component: Record<string, AggregatedUsageBucket>;
    runs_included: number;
}

export interface CacheStatusResponse {
    refreshed_at: string | null;
    job_count: number;
    user_count: number;
    scan_duration_seconds: number | null;
    is_refreshing: boolean;
}
