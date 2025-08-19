# Training-specific defaults

# MLFLOW
EXPERIMENT_NAME = "testing_mlflow_training"

# Logging
USE_LOGGING = True
LOG_LEVEL = "WARNING"  # "DEBUG", "INFO", "WARNING"

# Data loader
BATCH_SIZE = 512
NUM_WORKERS = 0
PIN_MEMORY = False
FORCE_REBUILD = False
SEED = 7683  # SOUD = 7 6 8 3

# Training
EPOCHS = 2
LR = 1e-4
DEVICE = "cuda"  # "cpu", "cuda", or "auto"
USE_HUBER = True
PATIENCE = 5

# Model
EMBED_DIM_SINGLE = 32
EMBED_DIM_MULTI = 32
HIDDEN = (128, 64)
DROPOUT = 0.1
WEIGHT_DECAY = 1e-4
