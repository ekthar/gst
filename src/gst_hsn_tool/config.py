AUTO_APPROVE_THRESHOLD = 90
SUPERVISOR_REVIEW_THRESHOLD = 75
PUBLISH_MATCH_THRESHOLD = 75
TOP_K_CANDIDATES = 3

LEARNING_DB_PATH = "data/learned_mappings.csv"
LEARNING_FUZZY_THRESHOLD = 92
LEARNING_SAVE_THRESHOLD = 75

TRAINING_DIR = "data/training"
TRAINING_RAW_DIR = "data/training/raw"
TRAINING_SNAPSHOT_DIR = "data/training/snapshots"
TRAINING_PRACTICE_DIR = "data/training/practice"
TRAINING_CORPUS_DIR = "data/training/corpus"
TRAINING_CORPUS_FILE = "data/training/corpus/training_corpus.csv"
TRAINING_GOOGLE_QUERIES_FILE = "data/google_search_queries.txt"
TRAINING_GOOGLE_PRODUCTS_FILE = "data/google_search_products.txt"
TRAINING_SOURCES_FILE = "data/training_sources.txt"
TRAINING_SOURCE_CATALOG_FILE = "data/training_source_catalog.csv"
DEFAULT_BACKUP_FILE = "data/gst_training_backup.zip"

# Scale knobs for larger autonomous data generation.
TRAINING_MAX_PAGES = 2000
TRAINING_PRACTICE_MAX_ROWS = 200000
TRAINING_MAX_SECONDS = 600
TRAINING_GOOGLE_MAX_RESULTS_PER_QUERY = 25
TRAINING_GOOGLE_PRODUCT_LIMIT = 300
TRAINING_FETCH_WORKERS = 8
TRAINING_GOOGLE_DISCOVERY_DELAY_SECONDS = 0.2

REQUIRED_CLIENT_COLUMNS = ["description"]
REQUIRED_HSN_COLUMNS = ["hsn8", "description"]
