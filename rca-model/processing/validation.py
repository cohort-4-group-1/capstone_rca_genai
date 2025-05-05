import pandas as pd
import great_expectations as gx
from schema import SchemaDefinition  # only if in separate file

def validate_data(**kwargs):
    # Step 1: Pull raw DataFrame from previous task
    df_json = kwargs['ti'].xcom_pull(task_ids='read_from_s3', key='raw_df')
    df = pd.read_json(df_json)

    # Step 2: Validate with Great Expectations
    context = gx.get_context()
    datasource = context.sources.add_pandas(name="pandas_src")
    asset = datasource.add_dataframe_asset(name="validated_df_asset")
    batch = asset.get_batch(dataframe=df)

    for col, expected_type in SchemaDefinition.expected_types.items():
        if col in df.columns:
            batch.expect_column_values_to_be_of_type(col, expected_type)
        else:
            print(f"⚠️ Column missing in DataFrame: {col}")

    validation_result = batch.validate()

    # Optional: fail DAG if validation fails
    if not validation_result["success"]:
        raise ValueError("Data validation failed")

    # Step 3: Push validated data to XCom
    kwargs['ti'].xcom_push(key='validated_df', value=df.to_json())



class SchemaDefinition:
    expected_types = {
        "Timestamp": "object",        
        "LogLevel": "object",
        "Component": "object",
        "PID": "int64",
        "Message": "object"
    }
