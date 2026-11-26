// How well the model does against the simpler methods: their scores on the test years, for all courts or
// one, and their calibration. No DOM access.

/** The methods, from the simplest to the demo's model, with what each knows of a case. */
export const MODELS = [
  { key: 'court average', name: 'Court average', about: 'How long the court\'s cases took to finish, read from the day of the forecast. It knows only the court and the time since filing.' },
  { key: 'process map', name: 'Process map', about: 'How long the court\'s cases took to finish from the same stage, after about as long in it.' },
  { key: 'cox', name: 'Cox model', about: 'A Cox proportional hazards model, on features of the case chosen by hand: its court and stage, the time since filing, in its stage and since its last event, its hearings, and whether it has been decided, appealed or revived.' },
  { key: 'trees', name: 'Boosted trees', about: 'Gradient-boosted trees (LightGBM), on the same features.' },
  { key: 'features network', name: 'Network on features', about: 'The network\'s output layers, given the same features instead of the case\'s events.' },
  { key: 'gru ensemble', name: 'GRU network', about: 'The demo\'s model: five recurrent networks that read the case\'s events one by one, with their forecasts averaged.' },
];

/** The model the demo runs. */
export const MODEL = 'gru ensemble';

/** The landmarks: forecasts made at filing and this many months after, or 'all' of them together. */
export const LANDMARKS = ['all', '0', '1', '3', '6', '12'];

/**
 * The methods' scores for a court's test cases (or all courts', when it's null) and a landmark, as
 * { forecasts, rows }, each row a method with its `concordance`, and its `brier` and `calibration` by
 * horizon in months. A court's scores are for all its forecasts together, so its landmark is 'all'.
 */
export function scoreTable(data, court, landmark = 'all') {
  const { columns, rows } = data.scores;
  const at = (name) => columns.indexOf(name);
  const scope = court ? court.code : 'all';
  const when = court ? 'all' : landmark;
  const found = new Map(rows.filter((row) => row[at('court')] === scope && row[at('landmark')] === when).map((row) => [row[at('model')], row]));
  const table = MODELS.map((model) => {
    const row = found.get(model.key);
    const byHorizon = (metric) => Object.fromEntries(data.horizons.map((h) => [h, row[at(`${metric}_${h}`)]]));
    return { ...model, concordance: row[at('concordance')], brier: byHorizon('brier'), calibration: byHorizon('calibration') };
  });
  return { forecasts: found.get(MODEL)[at('cuts')], rows: table };
}

/**
 * The methods with the best value of a score, as shown to `digits` decimal places: the highest, or the
 * lowest when `lower`. A tie at that precision is a tie.
 */
export function best(rows, value, { lower = false, digits = 3 } = {}) {
  const shown = rows.map((row) => Number(value(row).toFixed(digits)));
  const top = lower ? Math.min(...shown) : Math.max(...shown);
  return rows.filter((_, i) => shown[i] === top);
}

/**
 * A method's calibration within `horizon` months, over all the test forecasts: for each bin of 10
 * points, the share of the forecasts in it, their mean, and the share of those cases that ended in time.
 */
export function calibration(data, model, horizon) {
  const { columns, rows } = data.calibration;
  const at = (name) => columns.indexOf(name);
  return rows
    .filter((row) => row[at('model')] === model && row[at('horizon')] === horizon)
    .map((row) => ({ bin: row[at('bin')], share: row[at('share')], forecast: row[at('forecast')], observed: row[at('observed')] }))
    .sort((a, b) => a.bin - b.bin);
}
