// How well the model does on the test years, over all courts: its calibration, and how well it and three
// simpler methods put cases in order at each point in a case's life. No DOM access.

/** The methods on the ranking chart, the demo's model first and then from the simplest, with what each is. */
export const METHODS = [
  {
    key: 'gru ensemble',
    name: 'This model',
    about: 'Five recurrent neural networks, which read a case\'s events one by one, with their forecasts averaged. It\'s '
      + 'the model on the Forecast tab.',
  },
  {
    key: 'court average',
    name: 'Court average',
    about: 'How long the court\'s cases from 2020–2023 took to end, counted from the day of the forecast. It knows '
      + 'only the court and the time since filing.',
  },
  {
    key: 'process map',
    name: 'Process map',
    about: 'Of the court\'s cases from 2020–2023 that were in the same stage of the Process map for about as long, '
      + 'the share that ended within each time. It doesn\'t know how the case got there, or when it was filed.',
  },
  {
    key: 'trees',
    name: 'Boosted trees',
    about: 'Gradient-boosted decision trees (LightGBM), given features chosen by hand: the court, the stage, the times '
      + 'since filing, since the last event and in the stage, the hearings, and whether the case was decided, appealed '
      + 'or revived.',
  },
];

/** The model the demo runs. */
export const MODEL = 'gru ensemble';

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
 * The methods from the simplest to the model, each with its concordance at each landmark as `values`, in
 * the order of LANDMARKS.
 */
export function ranking(data) {
  return [...METHODS.slice(1), METHODS[0]]
    .map((method) => ({ ...method, values: LANDMARKS.map((when) => scores(data, method.key, when)('concordance')) }));
}

/** How many forecasts were scored, and on how many cases: each case is forecast at filing. */
export function counts(data) {
  return { forecasts: scores(data, MODEL, 'all')('cuts'), cases: scores(data, MODEL, 0)('cuts') };
}
