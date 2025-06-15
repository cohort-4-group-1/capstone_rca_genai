import boto3
import pandas as pd
import re
from io import StringIO

SOURCE_BUCKET = 'rca.logs.openstack'
DEST_BUCKET = 'rca.logs.openstack'
FILE_KEY = 'raw/OpenStack_2k.log'
OUTPUT_KEY = "silver/OpenStack_structured.csv"
AWS_REGION = 'us-east-1'

def read_raw_log_from_s3():
    print(f"Started to read file from S3 bucket: {SOURCE_BUCKET}")
    s3 = boto3.client('s3', region_name=AWS_REGION)
    print("Create S3 object")
    obj = s3.get_object(Bucket=SOURCE_BUCKET, Key=FILE_KEY)
    print(f"Successfully read file from S3 bucket: {SOURCE_BUCKET} , File Key {FILE_KEY}")
    print("Started to read raw file in Dataframe")
    lines = obj['Body'].read().decode('utf-8').strip().split('\n')
    parsed_data = []
    
    for line in lines:
        if not line.strip():
            continue
            
        # Regex pattern to parse the log structure
        pattern = r'^(\S+)\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})\s+(\d+)\s+(\w+)\s+([^\[]+)\s+\[([^\]]+)\]\s+(.+)$'
        
        match = re.match(pattern, line)
        if match:
            log_file = match.group(1)
            timestamp = match.group(2)
            process_id = match.group(3)
            log_level = match.group(4)
            component = match.group(5).strip()
            request_info = match.group(6)
            message = match.group(7)
            
            # Parse additional fields from message if it's an API request
            ip_address = None
            http_method = None
            endpoint = None
            status_code = None
            response_length = None
            response_time = None
            instance_id = None
            
            # Check if it's an API server log with HTTP request info
            if 'osapi_compute.wsgi.server' in component:
                api_pattern = r'(\d+\.\d+\.\d+\.\d+)\s+"(\w+)\s+([^"]+)"\s+status:\s+(\d+)\s+len:\s+(\d+)\s+time:\s+([\d.]+)'
                api_match = re.search(api_pattern, message)
                if api_match:
                    ip_address = api_match.group(1)
                    http_method = api_match.group(2)
                    endpoint = api_match.group(3)
                    status_code = int(api_match.group(4))
                    response_length = int(api_match.group(5))
                    response_time = float(api_match.group(6))
            
            # Check if it's a compute log with instance info
            elif 'nova.compute.manager' in component or 'nova.virt.libvirt' in component:
                instance_pattern = r'\[instance:\s+([a-f0-9-]+)\]'
                instance_match = re.search(instance_pattern, message)
                if instance_match:
                    instance_id = instance_match.group(1)
            
            # Parse request ID from request_info
            request_id = None
            if request_info:
                req_parts = request_info.split()
                if req_parts and req_parts[0].startswith('req-'):
                    request_id = req_parts[0]
            
            parsed_data.append({
                'log_file': log_file,
                'timestamp': pd.to_datetime(timestamp),
                'process_id': int(process_id),
                'log_level': log_level,
                'component': component,
                'request_id': request_id,
                'request_info': request_info,
                'message': message,
                'ip_address': ip_address,
                'http_method': http_method,
                'endpoint': endpoint,
                'status_code': status_code,
                'response_length': response_length,
                'response_time': response_time,
                'instance_id': instance_id
            })
    
    df = pd.DataFrame(parsed_data)
    print("Genared Dataframe")
    print(df.head(10))
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    try:
        s3.put_object(Bucket=DEST_BUCKET, Key=OUTPUT_KEY, Body=csv_buffer.getvalue())
        print(f"Successfully saved cleaned data to S3 bucket: {DEST_BUCKET}, File Key: {OUTPUT_KEY}")
        # Verify the upload
        response = s3.head_object(Bucket=DEST_BUCKET, Key=OUTPUT_KEY)
        print(f"✓ File verified - Size: {response['ContentLength']} bytes")
            
        # List objects in the bucket to show folder structure
        print(f"\nObjects in bucket '{DEST_BUCKET}':")
        response = s3.list_objects_v2(Bucket=DEST_BUCKET)
            
        if 'Contents' in response:
                for obj in response['Contents']:
                    print(f"  - {obj['Key']} ({obj['Size']} bytes)")
        else:
                print("  No objects found")
                
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        raise


if __name__ == "__main__":
        read_raw_log_from_s3()
