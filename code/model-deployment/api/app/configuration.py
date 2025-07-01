SOURCE_BUCKET = 'rca.logs.openstack'
DEST_BUCKET = 'rca.logs.openstack'
RAW_FILE_KEY = 'raw/OpenStack_2k.log'
SILVER_FILE_NAME = 'OpenStack_structured.csv'
SILVER_FILE_KEY = 'silver/' + SILVER_FILE_NAME
GOLD_FILE_KEY = 'gold/OpenStack_template.csv'
TEMPLATE_FILE_KEY = 'gold/OpenStack_template.csv'
TEMPLATE_DRAIN_FILE = 'log_template_state.json'
TEMPLATE_DRAIN_FILE_KEY = 'gold/' + TEMPLATE_DRAIN_FILE
STRUCTURED_WITH_LOG_KEY='gold/OpenStack_structured_with_log_key.csv'
LOG_SEQUENCE__FILE_KEY='gold/logbert_template_text_input.csv'
CLUSTERING_MODEL_OUTPUT = 'models/clustering/kmeans/rca_log_model'
DEEP_KMEANS_MODEL_OUTPUT = 'models/clustering/deep_neural/kmeans/rca_log_model'
ISOLATION_FOREST_MODEL_OUTPUT = 'models/clustering/isolationforest/rca_log_model'
EDA_OUTPUT = 'logs/eda_output'
MODEL_OUTPUT = 'model/logbert'

AWS_REGION = 'us-east-1'
 
