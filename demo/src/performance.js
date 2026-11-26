// How well the model does on the test years, over all courts: its calibration, and how well it and the
// simpler methods put cases in order at each point in a case's life. No DOM access.

/** The methods the Performance tab compares, from the simplest to the demo's model. */
export const METHODS = [
  { key: 'court average', name: 'Court average' },
  { key: 'process map', name: 'Process map' },
  { key: 'trees', name: 'Boosted trees' },
  { key: 'gru ensemble', name: 'This model' },
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

/** Each method's concordance at each landmark, as `values` in the order of LANDMARKS. */
export function ranking(data) {
  return METHODS.map((method) => ({ ...method, values: LANDMARKS.map((when) => scores(data, method.key, when)('concordance')) }));
}

/** How many forecasts were scored, and on how many cases: each case is forecast at filing. */
export function counts(data) {
  return { forecasts: scores(data, MODEL, 'all')('cuts'), cases: scores(data, MODEL, 0)('cuts') };
}
