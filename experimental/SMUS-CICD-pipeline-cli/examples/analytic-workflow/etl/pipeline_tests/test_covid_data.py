"""
Pytest tests to validate COVID-19 ETL workflow data.
Tests run using Athena to query Glue catalog tables.
"""
import boto3
import pytest
import time


@pytest.fixture(scope="module")
def athena_client(smus_config):
    """Create Athena client."""
    return boto3.client('athena', region_name=smus_config['region'])


@pytest.fixture(scope="module")
def glue_client(smus_config):
    """Create Glue client."""
    return boto3.client('glue', region_name=smus_config['region'])


@pytest.fixture(scope="module")
def s3_output_location(smus_config):
    """S3 location for Athena query results."""
    account_id = smus_config.get('account_id', '198737698272')
    return f"s3://amazon-sagemaker-{account_id}-{smus_config['region']}-{smus_config['project_id']}/athena-results/"


def execute_athena_query(athena_client, query, s3_output_location, database='covid19_db'):
    """Execute Athena query and return results."""
    response = athena_client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': database},
        ResultConfiguration={'OutputLocation': s3_output_location}
    )
    
    query_execution_id = response['QueryExecutionId']
    
    # Wait for query to complete
    max_attempts = 30
    for _ in range(max_attempts):
        result = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
        state = result['QueryExecution']['Status']['State']
        
        if state == 'SUCCEEDED':
            break
        elif state in ['FAILED', 'CANCELLED']:
            reason = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
            raise Exception(f"Query {state}: {reason}")
        
        time.sleep(1)
    
    # Get results
    results = athena_client.get_query_results(QueryExecutionId=query_execution_id)
    return results


def test_covid19_db_exists(glue_client):
    """Test that covid19_db database exists."""
    response = glue_client.get_database(Name='covid19_db')
    assert response['Database']['Name'] == 'covid19_db'
    print("✅ Database covid19_db exists")


def test_us_simplified_table_exists(glue_client):
    """Test that us_simplified table exists."""
    
    response = glue_client.get_table(DatabaseName='covid19_db', Name='us_simplified')
    assert response['Table']['Name'] == 'us_simplified'
    print("✅ Table us_simplified exists")


def test_us_simplified_has_data(athena_client, s3_output_location):
    """Test that us_simplified table has data."""
    query = "SELECT COUNT(*) as row_count FROM us_simplified"
    results = execute_athena_query(athena_client, query, s3_output_location)
    
    # Parse results (skip header row)
    rows = results['ResultSet']['Rows']
    assert len(rows) > 1, "No data returned"
    
    count = int(rows[1]['Data'][0]['VarCharValue'])
    assert count > 0, f"Table is empty, expected rows > 0, got {count}"
    print(f"✅ Table has {count} rows")


def test_us_simplified_schema(athena_client, s3_output_location):
    """Test that us_simplified has expected columns."""
    query = "SELECT * FROM us_simplified LIMIT 1"
    results = execute_athena_query(athena_client, query, s3_output_location)
    
    # Get column names from header
    columns = [col['Name'] for col in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    
    expected_columns = ['date', 'state', 'confirmed', 'deaths']
    for col in expected_columns:
        assert col in columns, f"Missing column: {col}"
    
    print(f"✅ Table has expected columns: {columns}")


def test_covid19_summary_db_exists(glue_client):
    """Test that covid19_summary_db database exists."""
    response = glue_client.get_database(Name='covid19_summary_db')
    assert response['Database']['Name'] == 'covid19_summary_db'
    print(f"✅ Database covid19_summary_db exists")


def test_us_state_summary_table_exists(glue_client):
    """Test that us_state_summary table exists."""
    
    response = glue_client.get_table(DatabaseName='covid19_summary_db', Name='us_state_summary')
    assert response['Table']['Name'] == 'us_state_summary'
    print("✅ Table us_state_summary exists")


def test_us_state_summary_has_data(athena_client, s3_output_location):
    """Test that us_state_summary table has summary data."""
    query = "SELECT COUNT(*) as state_count FROM us_state_summary"
    results = execute_athena_query(athena_client, query, s3_output_location, database='covid19_summary_db')
    
    # Parse results (skip header row)
    rows = results['ResultSet']['Rows']
    assert len(rows) > 1, "No summary data returned"
    
    count = int(rows[1]['Data'][0]['VarCharValue'])
    assert count > 0, f"Summary table is empty, expected states > 0, got {count}"
    print(f"✅ Summary table has {count} states")


def test_summary_values_are_valid(athena_client, s3_output_location):
    """Test that summary values are valid numbers."""
    query = "SELECT state, total_confirmed, total_deaths FROM us_state_summary ORDER BY total_confirmed DESC LIMIT 1"
    results = execute_athena_query(athena_client, query, s3_output_location, database='covid19_summary_db')
    
    # Get data row (skip header)
    data_row = results['ResultSet']['Rows'][1]['Data']
    
    state = data_row[0]['VarCharValue']
    total_confirmed = int(data_row[1]['VarCharValue'])
    total_deaths = int(data_row[2]['VarCharValue'])
    
    assert total_confirmed > 0, f"total_confirmed should be > 0, got {total_confirmed}"
    assert total_deaths >= 0, f"total_deaths should be >= 0, got {total_deaths}"
    
    print(f"✅ Summary values valid for {state}: confirmed={total_confirmed}, deaths={total_deaths}")
