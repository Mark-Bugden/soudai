from __future__ import annotations

import argparse
import json
import logging
import random
import time
import types
from pathlib import Path
from typing import Any, Dict, Optional, Union

import numpy as np
import torch
import yaml
from tqdm.auto import tqdm


class TqdmLoggingHandler(logging.Handler):
    """Console handler that writes via tqdm.write() to avoid breaking bars."""

    def emit(self, record: logging.LogRecord) -> None:
        """Write the formatted log record via tqdm to avoid breaking progress bars.

        Args:
            record (logging.LogRecord): The log record to emit.

        """
        try:
            msg = self.format(record)
            tqdm.write(msg)
        except Exception:
            self.handleError(record)


def get_logger(
    name: str, level: str = "INFO", enable: bool = True
) -> Optional[logging.Logger]:
    """Create a logger instance with a tqdm-friendly console handler.

    Args:
        name (str): Logger name.
        level (str, optional): Logging level (case-insensitive). Defaults to "INFO".
        enable (bool, optional): Whether to return a logger or None. Defaults to True.

    Returns:
        Optional[logging.Logger]: Configured logger, or None if `enable` is False.
    """
    if not enable:
        return None
    logger = logging.getLogger(name)
    logger.propagate = False  # prevent duplicate logs via root

    # remove any existing handlers once, to avoid duplicates in notebooks
    if logger.handlers:
        for h in list(logger.handlers):
            logger.removeHandler(h)

    # console handler that plays nice with tqdm
    ch = TqdmLoggingHandler()
    fmt = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    ch.setFormatter(logging.Formatter(fmt))
    logger.addHandler(ch)

    logger.setLevel(level.upper())
    return logger


def prepare_run_dir(
    base_path: Path,
    logger: logging.Logger | None = None,
) -> Path:
    """Create a timestamped run directory under the given base path.

    Args:
        base_path (Path): Directory under which the new run directory will be created.
        logger (logging.Logger): Logger instance for status messages.
            If None, logging is skipped.

    Returns:
        Path: The created run directory path.
    """
    ts = time.strftime("%Y%m%d-%H%M%S")
    run_dir = base_path / ts
    run_dir.mkdir(parents=True, exist_ok=False)

    if logger:
        logger.info("Run directory: %s", str(run_dir))

    return run_dir


def save_json(path: Path, obj: Dict[str, Any]) -> None:
    """Save a small JSON file with pretty formatting.

    Args:
        path (Path): File path to write.
        obj (Dict[str, Any]): Dictionary to save as JSON.

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def load_json(path: Path) -> Union[Dict[str, Any], list, str, int, float, bool, None]:
    """Load a small JSON file.

    Args:
        path (Path): File path to read.

    Returns:
        Union[dict, list, str, int, float, bool, None]: Parsed JSON content.

    """
    with open(path, "r") as f:
        return json.load(f)


def save_config_snapshot(cfg_module: types.ModuleType, run_dir: Path) -> None:
    """Extract ALLCAPS constants from training_config module and save to run_dir."""

    # Extract only public ALLCAPS attributes
    config_dict = {
        k: (list(v) if isinstance(v, tuple) else v)
        for k, v in vars(cfg_module).items()
        if k.isupper() and not k.startswith("_")
    }

    with open(run_dir / "config.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(config_dict, f, sort_keys=True, allow_unicode=True)


def set_random_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

    # Make CUDA deterministic (slower, but exact reproducibility)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default=None, help="Path to config JSON")
    return parser.parse_args()


def load_config_dict(args) -> dict:
    import training.training_config as cfg

    cfg_dict = {k: getattr(cfg, k) for k in dir(cfg) if k.isupper()}
    if args.config:
        with open(args.config) as f:
            overrides = json.load(f)
        cfg_dict.update(overrides)
    return cfg_dict
