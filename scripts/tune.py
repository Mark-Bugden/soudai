import itertools
import json
import math
import random
import subprocess
import tempfile
from typing import Dict, Generator

import mlflow

from config import TRAIN_SCRIPT_PATH
from tuning.tuning_config import EXPERIMENT_NAME, SAMPLER, SEARCH_SPACE


def build_param_grid(
    search_space: Dict[str, tuple],
) -> Generator[Dict[str, object], None, None]:
    """Expand categorical search space into a full parameter grid."""
    keys = list(search_space.keys())
    values = [spec[1] for spec in search_space.values()]  # categorical choices
    for combo in itertools.product(*values):
        yield dict(zip(keys, combo))


def sample_params(
    search_space: Dict[str, tuple], n_trials: int
) -> Generator[Dict[str, object], None, None]:
    """Randomly sample parameter sets from the search space."""
    for _ in range(n_trials):
        params: Dict[str, object] = {}
        for name, spec in search_space.items():
            if spec[0] == "categorical":
                params[name] = random.choice(spec[1])
            elif spec[0] == "float":
                _, low, high, log = spec
                if log:
                    params[name] = 10 ** random.uniform(
                        math.log10(low), math.log10(high)
                    )
                else:
                    params[name] = random.uniform(low, high)
            else:
                raise ValueError(f"Unsupported spec type {spec[0]}")
        yield params


def run_with_params(params: Dict[str, object]) -> None:
    """Run training with given parameters via subprocess."""

    # force override of experiment name
    params["experiment_name"] = EXPERIMENT_NAME

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(params, f)
        config_path = f.name
    subprocess.run(["python", TRAIN_SCRIPT_PATH, "--config", config_path], check=True)


def main() -> None:
    """Run hyperparameter search with grid or random sampler and report best run."""
    if SAMPLER == "grid":
        param_sets = list(build_param_grid(SEARCH_SPACE))
    elif SAMPLER == "random":
        from tuning.tuning_config import N_TRIALS

        param_sets = list(sample_params(SEARCH_SPACE, N_TRIALS))
    else:
        raise ValueError(f"Unknown sampler: {SAMPLER}")

    for i, params in enumerate(param_sets):
        print(f"=== Running trial {i + 1}/{len(param_sets)} with {params}")
        run_with_params(params)


if __name__ == "__main__":
    main()
