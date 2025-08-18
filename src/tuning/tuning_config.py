# Global tuning defaults
N_TRIALS = 2
STUDY_NAME = "hyperparam_tuning_lr_tuning"
DIRECTION = "minimize"
SAMPLER = "grid"  # or "random"

ARCHITECTURES = {
    "shallow_small": [64],
    "shallow_medium": [128],
    "shallow_wide": [256],
    "medium_tapering": [128, 64],
    "medium_wide": [256, 128],
    # "two_layer_wide": [512, 256],
    "deep_tapering": [256, 128, 64],
    # "deep_wide": [512, 256, 128],
}

SEARCH_SPACE = {
    "LR": ("categorical", [1e-5, 1e-4, 1e-3]),
    # "WEIGHT_DECAY": ("categorical", [1e-6, 1e-5, 1e-4, 1e-3, 1e-2]),
    # "HIDDEN": ("categorical", list(ARCHITECTURES.keys())),
    # "DROPOUT": ("categorical", [0.0, 0.1, 0.3, 0.5]),
}
