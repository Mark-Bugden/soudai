// How well the model and the simpler methods do on the test years, over all courts: their calibration,
// and how well they put cases in order at each point in a case's life. No DOM access.

// The features of a case chosen by hand, which Cox, the trees and the network on features are given.
const FEATURES = 'its court and stage, the time since filing, since its last event and in its stage, its number of '
  + 'hearings, and whether it has been decided, appealed or revived';

/**
 * Every method scored, the demo's model first and then from the simplest, with its name in running text
 * (`the`) and what it is (`about`).
 */
export const METHODS = [
  {
    key: 'gru ensemble',
    name: 'This model',
    the: 'this model',
    about: 'Five recurrent neural networks, which read a case\'s events one by one, with their forecasts averaged. It\'s '
      + 'the model on the Forecast tab.',
  },
  {
    key: 'court average',
    name: 'Court average',
    the: 'the court average',
    about: 'How long the court\'s cases registered in 2020–2023 took to end, counted from the day of the forecast. It '
      + 'knows only the court and the time since filing.',
  },
  {
    key: 'process map',
    name: 'Process map',
    the: 'the process map',
    about: 'The Process map\'s numbers for a single case: of the court\'s cases registered in 2020–2023 that were in '
      + 'the same stage (such as decided, or on appeal), and had been in it about as long, the share that ended within '
      + 'each time. It knows nothing of how the case got there, or when it was filed.',
  },
  {
    key: 'cox',
    name: 'Cox model',
    the: 'the Cox model',
    about: `A Cox proportional hazards model, a standard statistical model of the time until an event, given features of the case chosen by hand: ${FEATURES}.`,
  },
  {
    key: 'trees',
    name: 'Boosted trees',
    the: 'the boosted trees',
    about: `Gradient-boosted decision trees (LightGBM), a standard machine-learning method for tables of data, given features of the case chosen by hand: ${FEATURES}.`,
  },
  {
    key: 'features network',
    name: 'Network on features',
    the: 'the network on features',
    about: `The output layers of this model's networks, given features of the case chosen by hand instead of its events: ${FEATURES}.`,
  },
];

/** The model the demo runs. */
export const MODEL = 'gru ensemble';

/** The method the model is compared with at first: the simplest. */
export const FIRST = 'court average';

/** The landmarks: forecasts made at filing, and this many months after it. */
export const LANDMARKS = [0, 1, 3, 6, 12];

/** The bins of the calibration tables: 10 points each. */
export const BINS = 10;

/** A lookup of a table's rows, by column name. */
const column = (table) => (name) => table.columns.indexOf(name);

/** A method's scores over all courts, at a landmark or 'all' of them together. */
function scores(data, model, landmark) {
  const at = column(data.scores);
  const row = data.scores.rows.find((r) => r[at('model')] === model && r[at('court')] === 'all' && r[at('landmark')] === String(landmark));
  return (name) => row[at(name)];
}

/**
 * A method's calibration within `horizon` months, over all the test forecasts: for each bin of 10
 * points, the share of the forecasts in it, their mean, and the share of those cases that ended in time.
 */
export function calibration(data, model, horizon) {
  const at = column(data.calibration);
  return data.calibration.rows
    .filter((row) => row[at('model')] === model && row[at('horizon')] === horizon)
    .map((row) => ({ bin: row[at('bin')], share: row[at('share')], forecast: row[at('forecast')], observed: row[at('observed')] }))
    .sort((a, b) => a.bin - b.bin);
}

/**
 * The mean gap between a method's forecasts and what happened, within `horizon` months: the bins'
 * distances from the diagonal, weighted by their forecasts.
 */
export const gap = (data, model, horizon) => scores(data, model, 'all')(`calibration_${horizon}`);

/**
 * The method compared with the model, if any (`compare`, a key or null), and then the model, each with its
 * concordance at each landmark as `values`, in the order of LANDMARKS.
 */
export function ranking(data, compare = null) {
  const keys = compare ? [compare, MODEL] : [MODEL];
  return keys.map((key) => METHODS.find((method) => method.key === key))
    .map((method) => ({ ...method, values: LANDMARKS.map((when) => scores(data, method.key, when)('concordance')) }));
}

/** How many forecasts were scored, and on how many cases: each case is forecast at filing. */
export function counts(data) {
  return { forecasts: scores(data, MODEL, 'all')('cuts'), cases: scores(data, MODEL, 0)('cuts') };
}
