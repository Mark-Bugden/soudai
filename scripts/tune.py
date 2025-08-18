import json
import subprocess
import tempfile
from pathlib import Path

import optuna
import pandas as pd
from optuna.samplers import GridSampler, RandomSampler

from config import RUNS_PATH, TRAIN_SCRIPT_PATH
from tuning.tuning_config import DIRECTION, N_TRIALS, SAMPLER, SEARCH_SPACE, STUDY_NAME


def get_last_run_dir() -> Path:
    """Return the most recently created run directory."""
    run_dirs = sorted(
        RUNS_PATH.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not run_dirs:
        raise FileNotFoundError("No run directories found under runs/")
    return run_dirs[0]


def suggest_from_space(
    trial: optuna.trial.Trial,
    name: str,
    spec: tuple,
) -> object:
    """Suggest a hyperparameter value for a given trial based on a search space spec.

    Args:
        trial (optuna.trial.Trial):
            The active Optuna trial object, used to sample parameter values.
        name (str):
            The name of the hyperparameter (e.g. "LR", "DROPOUT").
        spec (tuple):
            A tuple describing the search space. Supported formats:
              - ("float", low: float, high: float) → float
              - ("categorical", choices: Sequence[T]) → T

    Returns:
        object: A sampled value of the hyperparameter.

    Raises:
        ValueError: If the spec type is not recognized.
    """

    kind = spec[0]
    if kind == "float":
        _, low, high, log = spec
        return trial.suggest_float(name, low, high, log=log)
    elif kind == "categorical":
        _, choices = spec
        return trial.suggest_categorical(name, choices)
    else:
        raise ValueError(f"Unknown search space type '{kind}' for {name}")


def objective(trial: optuna.trial.Trial) -> float:
    """Optuna objective: run training with sampled hyperparameters."""

    # Build override config
    overrides = {
        name: suggest_from_space(trial, name, spec)
        for name, spec in SEARCH_SPACE.items()
    }

    # Save to temp JSON
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(overrides, f)
        config_path = f.name

    # Run training
    subprocess.run(["python", TRAIN_SCRIPT_PATH, f"--config={config_path}"], check=True)

    # Find last run folder
    run_dir = get_last_run_dir()

    # Record run_dir as a user attribute for this trial
    trial.set_user_attr("run_dir", str(run_dir))

    # Load metrics from CSV
    metrics_path = run_dir / "metrics.csv"
    if not metrics_path.exists():
        raise FileNotFoundError(f"Metrics file not found: {metrics_path}")

    df = pd.read_csv(metrics_path)
    eval_rmse: float = float(df["val_rmse"].min())

    return eval_rmse


def main() -> None:
    # Select sampler
    if SAMPLER == "grid":
        # Build grid from categorical params only
        grid_space = {}
        for name, spec in SEARCH_SPACE.items():
            if spec[0] != "categorical":
                raise ValueError(
                    f"Grid search requires categorical params, but {name} is {spec[0]}"
                )
            grid_space[name] = spec[1]
        sampler = GridSampler(grid_space)
        n_trials = None  # Optuna will infer from grid
    else:
        sampler = RandomSampler()
        n_trials = N_TRIALS

    study = optuna.create_study(
        study_name=STUDY_NAME,
        direction=DIRECTION,
        storage="sqlite:///db.sqlite3",
        sampler=sampler,
    )

    study.optimize(objective, n_trials=n_trials)

    print("Best params:", study.best_params)
    print("Best value:", study.best_value)


if __name__ == "__main__":
    main()
