# Common workflows

Recipes chaining the pipeline steps into the classic exercises of operational hydrology.
Each links to the step pages for the details.

## Manual calibration of one model

1. **[Stations](stations.md)**: pick the calibration station and period; pick the same station as simulation station (any period) so the pipeline can unlock.
2. **[Weather](weather.md)**: pick a method.
3. **[Model](model.md)**: "Single" mode, pick a model, activate CemaNeige.
4. **[Calibration](calibration.md)**: choose the objective and transformation, set "Algorithm" to Manual, open the model's section and iterate on the sliders.
   Each move re-simulates immediately; judge the fit on the objective chip *and* on the hydrograph (zoom into floods and recessions).
5. **"Export"** the result — the JSON keeps the parameters and your whole trajectory, the CSV holds the simulated series for your figures.

## Automatic calibration with a split-sample test

Calibrate on one period, validate on another: performance on data the model never saw is the only honest measure.

1. **[Stations](stations.md)**: same station for both roles; calibration period = the fitting window, simulation period = a *disjoint* validation window.
2. **[Weather](weather.md)** and **[Model](model.md)**: as above.
3. **[Calibration](calibration.md)**: "Algorithm" SCE, then **"Calibrate"**; export the fitted parameters.
4. **[Simulation](simulation.md)**: the validation runs automatically — read the KGE chips and the six-metric profile; export the series and metrics.

To study the effect of the calibration period itself, re-run step 3 with a different (for example much shorter) calibration period and compare the validation metrics: the parameters are only as general as the climate they were fitted on.

## Comparing weather sources and models

1. Set up a split-sample calibration as above, with the [Model](model.md) step in "Ensemble" mode over the models to compare — one SCE run calibrates them all, and every chart overlays them with their median.
2. To change the weather source, revisit **[Weather](weather.md)** and pick another method.
   Downstream steps turn stale and the calibrated parameters are discarded — recalibrate, then compare validation metrics between runs.
3. **Export the calibration of each configuration to its own file**; re-importing a file restores its whole context ([import](calibration.md#export-and-import)), so you can flip between configurations at will.

## Proxy-basin test (spatial transfer)

Can parameters calibrated on one watershed reproduce another?

1. **[Stations](stations.md)**: calibration station = the donor basin, simulation station = the receiver basin, with their periods.
2. Calibrate (SCE) on the donor as above.
3. **[Simulation](simulation.md)** evaluates the donor's parameters on the receiver: the metric profile tells you which aspects of the transfer hold (timing, volume) and which degrade.

## Reconstructing an unobserved event

A calibrated model plus weather is enough to estimate flow where and when no gauge was recording — for example the July 1996 Saguenay flood at a station whose record starts later.

1. Calibrate on the closest suitable station and period ([manual](#manual-calibration-of-one-model) or [automatic](#automatic-calibration-with-a-split-sample-test)).
2. **[Stations](stations.md)**: set the simulation station to the target and the simulation period around the event — the period may extend outside the observed record.
3. **[Simulation](simulation.md)**: the hydrograph renders from weather alone (metrics stay blank without observations); zoom to the event and export the series.

## Saving and presenting your work

- Every step has an **"Export"** button; the CSVs (streamflow, weather, simulated series, regime, indicators) are ready to plot in your report figures.
- The browser keeps only the latest state: **export each calibration you care about to its own JSON** and re-import to return to it.
