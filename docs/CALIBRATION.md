# Calibration (v0.5.1)

**Where:** Prediction vs Reality → **5 · Calibrate → new prediction…** (`analysis/calibration.py`,
`ui/calibration_dialog.py`).

## What it does

1. Starts from a frozen prediction and the measurements you imported and mapped on the same page.
2. You tick up to five parameters. Suggested defaults: yoghurt `muS`, `muL`, `alpha`; chemostat `bC`, `bB`, `m`;
   community `mu_scale`. Experimental settings (temperature, dilution, inoculum controls with evidence
   `control`) are not offered, because they are known, not fitted.
3. Weighted least squares (`scipy.optimize.least_squares`, trust-region reflective) inside each parameter's
   allowed range. Positive parameters are fitted on a log scale. Each measured series counts equally (residuals
   divided by the spread of its own observations and by √n). Counts are compared on log10, like the comparison
   metrics. If the frozen initial state was derived from the parameters (e.g. yoghurt inoculum `XS0`), fitting
   such a parameter also changes the initial state.
4. Shows the fitted values with approximate 95 % intervals (linearised at the optimum: `s²(JᵀJ)⁻¹`), the error
   before and after on this data set, and warnings:
   * a parameter ended at a limit of its allowed range: the data want an implausible value, which usually means
     part of the model structure, not this number, is wrong;
   * an interval wider than a factor of 10: poorly determined;
   * two parameters with |correlation| > 0.95: these data cannot tell them apart; a different measurement is
     needed.
5. **Freeze as new prediction…** stores the fitted configuration as a NEW, append-only prediction. Its summary
   records `calibration.from_prediction`, the file name and SHA-256, the variables used, the fitted values and
   intervals. The fitted values also go into `parameters` (evidence `fitted`) under a new `model_versions` row
   whose `calibration_data` describes the file.

## What it never does

* It never edits or deletes the prediction it started from (database triggers forbid it; tests check it).
* It does not validate anything. A fit always matches its own data. If you compare a calibrated prediction with
  the same file it was fitted to, the page and the saved report say: *"a fit, not a test"*.

## The intended workflow

1. Freeze a prediction **before** the experiment (data set A is still unknown).
2. Compare it with data set A → that comparison is a genuine test of the original model.
3. Calibrate on data set A → new prediction #B.
4. Run a **different** experiment (another batch, temperature or day): data set B.
5. Compare prediction #B with data set B → a genuine test of the calibrated model.

## Checked by tests (`tests/test_calibration.py`)

* Known parameters are recovered within their intervals from noisy synthetic data, and exactly from noise-free
  data.
* A true value outside the allowed range is flagged as "at limit".
* Fitting the inoculum changes the initial state.
* Too few measurements, too many parameters and unknown names are refused.
* Freezing creates a new prediction with full provenance; the old record is byte-for-byte unchanged and
  re-simulates to the old curve; the new one re-simulates to the fitted curve.
* Reports on the fitting file carry the warning.
