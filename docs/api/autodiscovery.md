# AutoDiscovery API Reference

The parts of the `autodiscovery` package that implement the search described in
[How It Works](../autodiscovery/overview.md). Each entry shows its source.

## Search loop

::: autodiscovery.run
    options:
      show_root_heading: true
      heading_level: 3
      filters: []
      members:
        - run_mcts
        - compute_and_store_reward
        - _theoretical_max_boolean_cat

## Tree and node selection

::: autodiscovery.mcts
    options:
      show_root_heading: true
      heading_level: 3
      members:
        - MCTSNode
        - ucb1
        - progressive_widening
        - progressive_widening_all
        - default_mcts_selection
        - ucb1_recursive
        - beam_search

::: autodiscovery.mcts_utils
    options:
      show_root_heading: true
      heading_level: 3
      members:
        - select_nodes
        - get_self_value
        - get_context_string
        - load_mcts_from_json

## Beliefs

::: autodiscovery.beliefs
    options:
      show_root_heading: true
      heading_level: 3
      members:
        - get_belief
        - calculate_prior_and_posterior_beliefs
        - BeliefTrueFalseCat

## Agents and proposals

::: autodiscovery.agents
    options:
      show_root_heading: true
      heading_level: 3
      members:
        - get_agents

::: autodiscovery.transitions
    options:
      show_root_heading: true
      heading_level: 3
      members:
        - SpeakerSelector

::: autodiscovery.structured_outputs
    options:
      show_root_heading: true
      heading_level: 3
      members:
        - ExperimentList
        - Experiment

::: autodiscovery.deduplication
    options:
      show_root_heading: true
      heading_level: 3
      members:
        - dedupe
