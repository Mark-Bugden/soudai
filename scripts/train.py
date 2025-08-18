import json
from dataclasses import asdict

import training.training_config as cfg_defaults
from config import RUNS_PATH
from training.data import make_dataloaders
from training.io import load_or_prepare_encoded
from training.models import DecisionRegressor
from training.trainer import Trainer
from training.training_config_schema import training_config_from_dict
from utils import get_logger, parse_args, prepare_run_dir, save_json, set_random_seeds


def main() -> None:
    """ """

    # Parse arguments for config override
    args = parse_args()

    # Load defaults
    cfg_dict = {k: getattr(cfg_defaults, k) for k in dir(cfg_defaults) if k.isupper()}

    # Apply overrides if provided
    if args.config:
        with open(args.config) as f:
            overrides = json.load(f)
        cfg_dict.update(overrides)

    # Build structured config
    cfg = training_config_from_dict(cfg_dict)

    # Set random seeds for training
    set_random_seeds(cfg.seed)

    # Prepare the logger
    logger = get_logger("train", cfg.log_level, cfg.use_logging)

    # Prepare a timestamped run directory under the global RUNS_DIR
    run_dir = prepare_run_dir(base_path=RUNS_PATH, logger=logger)

    # Data
    df_train, df_eval, df_test, vocab_sizes = load_or_prepare_encoded(
        force_rebuild=cfg.force_rebuild,
        seed=cfg.seed,
        logger=logger,
    )
    train_dl, eval_dl, _ = make_dataloaders(
        df_train=df_train,
        df_eval=df_eval,
        df_test=df_test,
        batch_size=cfg.batch_size,
        num_workers=cfg.num_workers,
        pin_memory=cfg.pin_memory,
        seed=cfg.seed,
        logger=logger,
    )

    # Instantiate model
    model = DecisionRegressor(
        vocab_sizes=vocab_sizes,
        embed_dim_single=cfg.embed_dim_single,
        embed_dim_multi=cfg.embed_dim_multi,
        hidden=cfg.hidden,
        dropout=cfg.dropout,
    )

    # Save a config snapshot for reproducibility
    save_json(
        run_dir / "config_snapshot.json", {**asdict(cfg), "vocab_sizes": vocab_sizes}
    )

    # Trainer
    trainer = Trainer(
        model,
        lr=cfg.lr,
        weight_decay=cfg.weight_decay,
        patience=cfg.patience,
        device=cfg.device,
        use_huber=cfg.use_huber,
        logger=logger,
        run_dir=run_dir,
        save_best=cfg.save_best,
    )

    # Train
    metrics = trainer.fit(
        train_dl=train_dl,
        val_dl=eval_dl,
        epochs=cfg.epochs,
    )

    if logger:
        logger.info("Finished training", metrics)


if __name__ == "__main__":
    main()
