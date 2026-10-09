# Surprisal

Surprisal measures **how much an experiment changed what we believe** about a
hypothesis. It is the reward that steers the [tree search](tree_search.md),
and it marks which findings show up as "surprising" in the results.

The idea in one sentence: ask an LLM how likely the hypothesis is *before*
seeing the experiment, ask again *after*, and measure the gap.

## Step 1: ask for beliefs, several times

The belief model (`--belief_model`, which defaults to `--model`) is asked
`--n_belief_samples` times (default 5) for its view of the hypothesis. Asking
more than once captures how *confident* the model is, not just its single
best guess.

There are two rounds of questions:

| | What the model sees | What it is told |
|---|---|---|
| **Prior** | Only the hypothesis | "Use your prior knowledge of the research domain." |
| **Evidence** | The hypothesis plus the experiment's plan, analysis and review | "Disregard any prior beliefs… focus only on the provided evidence." |

The evidence round deliberately asks the model to *ignore* what it already
knows. The prior and the evidence are combined afterwards with plain
arithmetic (Step 3), so the model never has to do that combination itself.

In the default `boolean_cat` belief mode, each answer is one of six labels:

| Answer | Counts as "true" | Counts as "false" |
|---|---|---|
| definitely true | 1.0 | 0.0 |
| maybe true | 0.75 | 0.25 |
| uncertain | 0.5 | 0.5 |
| maybe false | 0.25 | 0.75 |
| definitely false | 0.0 | 1.0 |
| cannot comment | *ignored* | *ignored* |

"Cannot comment" answers are dropped, so a round may end up with fewer than 5
usable samples.

## Step 2: turn answers into a belief distribution

Think of the answers as **votes**. Adding up the "true" and "false" columns
gives two tallies, and these become the parameters of a
[Beta distribution](https://en.wikipedia.org/wiki/Beta_distribution), the
standard way to describe uncertainty about a probability:

$$
\text{Beta}(\alpha, \beta), \qquad
\alpha = \text{starting true} + \text{true votes}, \quad
\beta = \text{starting false} + \text{false votes}
$$

Every distribution starts from half a vote each way, $(0.5, 0.5)$ (the
"Jeffreys prior"), which on its own means "no idea". The **mean belief**,
the model's overall probability that the hypothesis is true, is

$$
\text{mean} = \frac{\alpha}{\alpha + \beta}
$$

More votes make the distribution narrower: five "definitely true" answers
express more confidence than one.

## Step 3: combine prior and evidence

- **Prior** = the starting half-votes + the prior-round votes.
- **Posterior** = the prior's votes + the evidence-round votes, each counted
  **twice** (`--evidence_weight`, default 2.0).

The weighting lets the experiment outvote the model's prior knowledge. Five
samples of evidence carry the weight of ten votes against the prior's five.

> **Note:** `--implicit_bayes_posterior` changes the evidence-round
> instruction so the model is told to *use* its prior knowledge as well. The
> arithmetic combination still happens either way.

## Step 4: measure the change

Two measures of change are computed:

- **Belief change**: $\lvert \text{posterior mean} - \text{prior mean} \rvert$.
  This is how far the probability moved, in either direction.
- **KL divergence** between the posterior and prior Beta distributions. This
  also registers a change in *confidence*, even when the mean barely moves.

These become the node's reward (`--reward_mode`, default `belief`):

$$
\text{reward} = \frac{\text{belief change}}{\text{surprisal width}}
$$

The surprisal width is `--surprisal_width` (default **0.2**). A node is
flagged **surprising** when its reward is at least 1, i.e. the belief moved by
0.2 or more.

| Option | Effect |
|---|---|
| `--use_binary_reward` | Reward is 1 if surprising, else 0, instead of the continuous ratio |
| `--reward_mode kl` | Use KL divergence ÷ `--kl_scale` (default 5.0) instead |
| `--reward_mode belief_and_kl` | Use whichever of the two is larger; surprising if either one is |

## A worked example

Hypothesis: *"In this dataset, X is positively associated with Y."*

**Prior round:** 3 × "maybe false", 2 × "uncertain".

- True votes: $3 \times 0.25 + 2 \times 0.5 = 1.75$. False votes: $5 - 1.75 = 3.25$.
- Prior = Beta(0.5 + 1.75, 0.5 + 3.25) = **Beta(2.25, 3.75)**.
- Prior mean = 2.25 / 6 = **0.375**. The model leans slightly toward "false".

**Evidence round:** the experiment finds a strong, significant association,
and all 5 answers are "definitely true".

- With evidence weight 2: 10 true votes, 0 false votes.
- Posterior = Beta(2.25 + 10, 3.75 + 0) = **Beta(12.25, 3.75)**.
- Posterior mean = 12.25 / 16 = **0.766**.

**Result:**

- Belief change = 0.766 − 0.375 = **0.39**.
- Reward = 0.39 / 0.2 ≈ **1.96**, and the node is **surprising**.

If the experiment had found no association, giving 5 × "definitely false",
the posterior would be Beta(2.25, 13.75) with mean 0.14. The change would be
0.23 and the node would *still* count as surprising. Disproving what the model
mildly expected counts too.

## Things to know

- **Direction doesn't matter.** Confirming a doubted hypothesis and refuting a
  believed one are rewarded the same. The report shows the direction
  separately.
- **Not every node is scored.** Only nodes that the reviewer approved, and that
  are below the dataset-loading node, get beliefs and a reward. Failed
  experiments contribute no reward.
- **The reward is not capped at 1.** With the default settings the mean can
  move by at most about 0.64, so the reward tops out around 3.2.
- **Normalized surprisal.** For `boolean_cat`, each node also records
  `normalized_surprisal`: the *signed* change divided by the largest change
  possible under the current settings. It ranges from −1 to 1 and makes runs
  with different settings comparable. It is recorded for reporting and does
  not affect the search. The derivation is on
  [Surprisal Normalization](surprisal_normalization.md). In its notation,
  $N$ is `--n_belief_samples`, $w$ is `--evidence_weight`, $(\alpha, \beta)$
  are the starting half-votes, $n$ and $x$ are the prior round's usable
  samples and true votes, and $m$ and $y$ are the same for the evidence
  round.

## Optional: surprise relative to earlier discoveries

With `--use_online_beliefs`, the prior round also sees every **earlier
surprising finding** in the run, presented as "previous studies". A new result
that just repeats or follows from something already discovered then looks less
surprising. This pushes the search toward results that are new relative to
what the run has already found, not only relative to the model's background
knowledge.

## Other belief modes

`--belief_mode` selects how answers are collected. They all follow the same
prior → posterior → change pattern:

| Mode | Answer format |
|---|---|
| `boolean_cat` (default) | Five-point scale from "definitely false" to "definitely true" (above) |
| `boolean` | Plain true / false |
| `categorical` | The same five labels, scored 0.1 / 0.3 / 0.5 / 0.7 / 0.9 instead of 0 to 1 |
| `categorical_numeric` | Probability ranges ("0-0.2" … "0.8-1.0"), scored at their midpoints |
| `gaussian` | A probability between 0 and 1 plus a standard deviation for uncertainty |

## In the code

| What | Where |
|---|---|
| Prompts and sampling for one round of beliefs | [`beliefs.get_belief`][autodiscovery.beliefs.get_belief] |
| Prior, posterior, belief change and KL | [`beliefs.calculate_prior_and_posterior_beliefs`][autodiscovery.beliefs.calculate_prior_and_posterior_beliefs] |
| Answer labels, votes and the Beta distribution | [`beliefs.BeliefTrueFalseCat`][autodiscovery.beliefs.BeliefTrueFalseCat] |
| Label scores | [`beliefs.BeliefTrueFalseCat.get_beta_params_from_cat_samples`][autodiscovery.beliefs.BeliefTrueFalseCat.get_beta_params_from_cat_samples] |
| Reward and the surprising flag | [`mcts_utils.get_self_value`][autodiscovery.mcts_utils.get_self_value] |
| Online beliefs and normalized surprisal | [`run.compute_and_store_reward`][autodiscovery.run.compute_and_store_reward] |
| Largest possible belief shift | [`run._theoretical_max_boolean_cat`][autodiscovery.run._theoretical_max_boolean_cat] |
