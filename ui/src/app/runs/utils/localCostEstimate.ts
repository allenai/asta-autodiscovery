export interface LocalCostEstimate {
    experiments: number;
    totalTokens: number;
    lowUSD: number;
    highUSD: number;
    livePricing: boolean;
}

interface ModelPrice {
    inputPerMillion: number;
    outputPerMillion: number;
}

// Grounded Round 1 token volumes. Belief volume includes one prior/posterior vote pair.
const TOKENS = {
    reasoningInputPerExperiment: 11_866,
    reasoningOutputPerExperiment: 1_183,
    codingInputPerExperiment: 3_673,
    codingOutputPerExperiment: 2_084,
    beliefInputPerVote: 4_848,
    beliefOutputPerVote: 320,
    beliefVotesPerExperiment: 5,
};

const COST_BAND = { low: 0.7, high: 1.8 };

const FAMILY_PRICES: Array<{ match: string; price: ModelPrice }> = [
    { match: 'opus', price: { inputPerMillion: 5, outputPerMillion: 25 } },
    { match: 'sonnet', price: { inputPerMillion: 3, outputPerMillion: 15 } },
    { match: 'haiku', price: { inputPerMillion: 1, outputPerMillion: 5 } },
    { match: 'gpt-5.4', price: { inputPerMillion: 2.5, outputPerMillion: 15 } },
    { match: 'gpt-5', price: { inputPerMillion: 0.25, outputPerMillion: 2 } },
    { match: 'gemini-3', price: { inputPerMillion: 0.5, outputPerMillion: 3 } },
];

function priceFor(model: string): ModelPrice {
    const normalized = model.toLowerCase();
    return (
        FAMILY_PRICES.find(({ match }) => normalized.includes(match))?.price || {
            inputPerMillion: 3,
            outputPerMillion: 15,
        }
    );
}

export function estimateLocalRunCost(
    experiments: number,
    agentModel: string,
    beliefModel: string,
    agentPrice?: ModelPrice,
    beliefPrice?: ModelPrice
): LocalCostEstimate {
    const safeExperiments = Math.max(0, Math.floor(experiments || 0));
    const reasoningInput = safeExperiments * TOKENS.reasoningInputPerExperiment;
    const reasoningOutput = safeExperiments * TOKENS.reasoningOutputPerExperiment;
    const codingInput = safeExperiments * TOKENS.codingInputPerExperiment;
    const codingOutput = safeExperiments * TOKENS.codingOutputPerExperiment;
    const beliefInput =
        safeExperiments * TOKENS.beliefVotesPerExperiment * TOKENS.beliefInputPerVote;
    const beliefOutput =
        safeExperiments * TOKENS.beliefVotesPerExperiment * TOKENS.beliefOutputPerVote;
    const agentRate = agentPrice || priceFor(agentModel);
    const beliefRate = beliefPrice || priceFor(beliefModel);
    const priceTokens = (input: number, output: number, price: ModelPrice) =>
        (input / 1_000_000) * price.inputPerMillion + (output / 1_000_000) * price.outputPerMillion;
    const pointCost =
        priceTokens(reasoningInput + codingInput, reasoningOutput + codingOutput, agentRate) +
        priceTokens(beliefInput, beliefOutput, beliefRate);

    return {
        experiments: safeExperiments,
        totalTokens:
            reasoningInput +
            reasoningOutput +
            codingInput +
            codingOutput +
            beliefInput +
            beliefOutput,
        lowUSD: pointCost * COST_BAND.low,
        highUSD: pointCost * COST_BAND.high,
        livePricing: Boolean(agentPrice && beliefPrice),
    };
}
