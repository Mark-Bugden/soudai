from dataclasses import dataclass
from typing import Tuple

from tuning.tuning_config import ARCHITECTURES


@dataclass
class TrainingConfig:
    """Full training configuration snapshot."""

    # MLFLOW
    experiment_name: str

    # Logging
    use_logging: bool
    log_level: str

    # Data loader
    batch_size: int
    num_workers: int
    pin_memory: bool
    force_rebuild: bool
    seed: int

    # Training
    epochs: int
    lr: float
    device: str
    use_huber: bool
    patience: int

    # Model
    embed_dim_single: int
    embed_dim_multi: int
    hidden: Tuple[int, ...]
    dropout: float
    weight_decay: float


def resolve_hidden(spec: object) -> tuple[int]:
    """Normalize different hidden layer specifications into a tuple of ints."""
    if isinstance(spec, str) and spec in ARCHITECTURES:
        return tuple(ARCHITECTURES[spec])
    if isinstance(spec, str):
        return tuple(int(x) for x in spec.split(","))
    if isinstance(spec, (list, tuple)):
        return tuple(spec)
    raise ValueError(f"Unsupported HIDDEN spec: {spec}")


def training_config_from_dict(cfg_dict: dict) -> TrainingConfig:
    d = {k.upper(): v for k, v in cfg_dict.items()}
    return TrainingConfig(
        experiment_name=d["EXPERIMENT_NAME"],
        use_logging=d["USE_LOGGING"],
        log_level=d["LOG_LEVEL"],
        batch_size=d["BATCH_SIZE"],
        num_workers=d["NUM_WORKERS"],
        pin_memory=d["PIN_MEMORY"],
        force_rebuild=d["FORCE_REBUILD"],
        seed=d.get("SEED", 42),
        epochs=d["EPOCHS"],
        lr=d["LR"],
        weight_decay=d["WEIGHT_DECAY"],
        device=d["DEVICE"],
        use_huber=d["USE_HUBER"],
        patience=d["PATIENCE"],
        embed_dim_single=d["EMBED_DIM_SINGLE"],
        embed_dim_multi=d["EMBED_DIM_MULTI"],
        hidden=resolve_hidden(d["HIDDEN"]),
        dropout=d["DROPOUT"],
    )
