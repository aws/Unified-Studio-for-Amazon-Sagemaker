"""
Marketing utilities for both MWAA and Serverless pipelines
"""
import logging

def process_marketing_data(env_name="dev", log_level="INFO", **context):
    """
    Process marketing data with environment-specific configuration
    """
    # Set up logging
    logging.basicConfig(level=getattr(logging, log_level.upper()))
    logger = logging.getLogger(__name__)
    
    logger.info(f"Processing marketing data in {env_name} environment")
    logger.info(f"Execution date: {context.get('ds', 'N/A')}")
    
    # Environment-specific processing
    if env_name == "prod":
        logger.info("Running production data processing")
    elif env_name == "test":
        logger.info("Running test data processing with validation")
    else:
        logger.info("Running development data processing")
    
    return f"Marketing data processed successfully in {env_name}"
