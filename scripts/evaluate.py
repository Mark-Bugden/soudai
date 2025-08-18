import json

import matplotlib.pyplot as plt
import pandas as pd
import torch

from config import RUNS_PATH
from training.data import make_dataloaders
from training.io import load_or_prepare_encoded
from training.models import DecisionRegressor
from training.trainer import Trainer
from training.training_config_schema import training_config_from_dict
from utils import get_logger, set_random_seeds

# Choose a run directory to evaluate
run_dir = RUNS_PATH / "20250818-012323"

# Load the config
with open(run_dir / "config_snapshot.json", "r", encoding="utf-8") as f:
    cfg_dict = json.load(f)
cfg = training_config_from_dict(cfg_dict)

# Load the training metrics
train_metrics = pd.read_csv(run_dir / "metrics.csv")

# Set random seeds for evaluation
set_random_seeds(cfg.seed)

# Prepare the logger
logger = get_logger("train", cfg.log_level, cfg.use_logging)

# Data
df_train, df_eval, df_test, vocab_sizes = load_or_prepare_encoded(
    force_rebuild=False,
    seed=cfg.seed,
    logger=logger,
)

_, _, test_dl = make_dataloaders(
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

model_checkpoint_path = run_dir / "best.ckpt"

model.load_state_dict(torch.load(model_checkpoint_path))
model.eval()

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

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
    save_best=False,
)


# Evaluate
avg_loss, rmse, mae = trainer.evaluate(test_dl)
print("Test metrics:")
print("avg_loss: ", avg_loss)
print("rmse: ", rmse)
print("mae: ", mae)
