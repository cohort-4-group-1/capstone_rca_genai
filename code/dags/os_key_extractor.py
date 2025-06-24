import re
import csv
import os
from datetime import datetime
import boto3
from botocore.exceptions import ClientError
import tempfile
import io

# Try to import pandas, fallback to csv if not available
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    print("Warning: pandas not found. Using csv module instead.")

class OpenStackLogParser:
    def __init__(self, log_file_path, template_file_path, debug=True):
        self.log_file_path = log_file_path
        self.template_file_path = template_file_path
        self.templates = {}
        self.parsed_logs = []
        self.debug = debug
        
    def debug_print(self, message):
        """Print debug messages if debug mode is enabled"""
        if self.debug:
            print(f"[DEBUG] {message}")
        
    def load_templates(self):
        """Load event templates from S3 object"""
        try:
            if HAS_PANDAS:
                print("Loading templates with pandas")
                print(self.template_file_path['Body'])
                raw_content = self.template_file_path['Body'].read()
                # print(f"Raw content type: {type(raw_content)}")
                # print(f"Raw content length: {len(raw_content)}")
                # print(f"First 100 chars: {raw_content[:100]}")
                csv_string = raw_content.decode('utf-8')

                df = pd.read_csv(io.StringIO(csv_string))

                print("Dataframe loaded")
                print(df.head(10))
                for _, row in df.iterrows():
                    event_id = row['EventId']
                    template = row['EventTemplate']
                    regex_pattern = self.template_to_regex(template)
                    self.templates[event_id] = {
                        'template': template,
                        'regex': regex_pattern
                    }
            else:
                print("Loading templates with csv")
                reader = csv.DictReader(io.StringIO(self.template_file_path['Body'].read().decode('utf-8')))
                for row in reader:
                    event_id = row['EventId']
                    template = row['EventTemplate']
                    regex_pattern = self.template_to_regex(template)
                    self.templates[event_id] = {
                        'template': template,
                        'regex': regex_pattern
                    }
            print(f"Loaded {len(self.templates)} templates")
            return True
        except Exception as e:
            print(f"Error loading templates: {e}")
            return False
    
    def template_to_regex(self, template):
        """Convert template with <*> wildcards to regex pattern"""
        # Replace 'time: <*>.<*>' first with a single greedy group
        template = re.sub(r'time: <\*>.<\*>', r'time: (.+)', template)
        
        # Replace all remaining <*> with non-greedy regex groups
        template = template.replace('<*>', '(.+?)')

        # Now escape everything else, except the regex group markers
        parts = re.split(r'(\(\.\+\??\)|\(\.\+\))', template)
        escaped_parts = [
            part if part.startswith('(.') else re.escape(part)
            for part in parts
        ]
        regex = ''.join(escaped_parts)
        
        return f'^{regex}$'

    

    def extract_log_content(self, log_line):
        """Extract the main content from a log line"""
        # self.debug_print(f"Processing line: {log_line[:100]}...")
        
        # Pattern to match OpenStack log format
        patterns = [
            # HTTP API logs
            r'^\S+\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)\s+\d+\s+\w+\s+[\w\.]+\s+\[.*?\]\s+(.*?"[^"]*"\s+status:\s+\d+\s+len:\s+\d+\s+time:\s+[\d\.]+)$',
            # Instance lifecycle logs
            r'^\S+\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)\s+\d+\s+\w+\s+[\w\.]+\s+\[.*?\]\s+(.*)$',
            # General pattern
            r'^\S+\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)\s+\d+\s+\w+\s+[\w\.]+\s+\[.*?\]\s+(.*)$'
        ]
        
        for i, pattern in enumerate(patterns):
            match = re.match(pattern, log_line.strip())
            if match:
                timestamp = match.group(1)
                content = match.group(2)
                # self.debug_print(f"Matched pattern {i+1}, extracted content: {content}")
                return timestamp, content
        
        self.debug_print("No pattern matched for this line")
        return None, None
    
    def match_template(self, content):
        """Match content against templates"""
        # self.debug_print(f"Trying to match: '{content}'")
       # processed_content = re.sub(r'time: (\d+)\.(\d+)', r'time: \1.\2', content)
        for event_id, template_info in self.templates.items():
            try:
                # self.debug_print(f"Testing {event_id}: '{template_info['template']}'")
                # self.debug_print(f"Regex: '{template_info['regex']}'")
                
                match = re.match(template_info['regex'], content)
                if match:
                    # self.debug_print(f"MATCHED! Event ID: {event_id}, Template: {template_info['template']}")
                    # self.debug_print(f"Captured groups: {match.groups()}")
                    return event_id, template_info['template']
                # else:
                    # self.debug_print(f"No match for {event_id}")
                    
            except re.error as e:
                self.debug_print(f"Regex error for {event_id}: {e}")
                continue
        
        return None, None
    
    def test_specific_content(self, test_content):
        """Test a specific content string against all templates"""
        print(f"\n=== TESTING CONTENT ===")
        print(f"Content: '{test_content}'")
        print("=" * 50)
        
        for event_id, template_info in self.templates.items():
            print(f"\nTesting {event_id}:")
            print(f"Template: {template_info['template']}")
            print(f"Regex: {template_info['regex']}")
            
            try:
                match = re.match(template_info['regex'], test_content)
                if match:
                    print(f"MATCH! Groups: {match.groups()}")
                    return event_id, template_info['template']
                else:
                    print("No match")
            except re.error as e:
                print(f"Regex error: {e}")
        
        print("\n No templates matched")
        return None, None
    
    def parse_logs(self):
        """Parse the log file and match against templates"""
        try:
            
                
            log_stream = io.StringIO(self.log_file_path['Body'].read().decode('utf-8'))
            for line_num, line in enumerate(log_stream, 1):
                    if line.strip():
                        timestamp, content = self.extract_log_content(line)
                        if content:
                            event_id, template = self.match_template(content)
                            
                            self.parsed_logs.append({
                                'line_number': line_num,
                                'timestamp': timestamp,
                                'content': content,
                                'event_id': event_id,
                                'template': template,
                                'original_line': line.strip()
                            })
            
            print(f"Parsed {len(self.parsed_logs)} log entries")
            return True
        except Exception as e:
            print(f"Error parsing logs: {e}")
            return False
    
    def save_results(self, output_file='templates_output.txt'):
        """Save only the matched templates to text file"""
        try:
            with open(output_file, 'w', encoding='utf-8') as file:
                for log_entry in self.parsed_logs:
                    if log_entry['template']:  # Only write if template was matched
                        file.write(f"{log_entry['template']}\n")
            
            print(f"Templates saved to {output_file}")
            
        except Exception as e:
            print(f"Error saving results: {e}")
    
    def get_statistics(self):
        """Get parsing statistics"""
        total = len(self.parsed_logs)
        matched = sum(1 for log in self.parsed_logs if log['event_id'])
        unmatched = total - matched
        
        print(f"\nParsing Statistics:")
        print(f"Total log entries: {total}")
        print(f"Matched entries: {matched}")
        print(f"Unmatched entries: {unmatched}")
        print(f"Match rate: {matched/total*100:.2f}%" if total > 0 else "Match rate: 0%")
        
        # Event distribution
        event_counts = {}
        for log in self.parsed_logs:
            if log['event_id']:
                event_counts[log['event_id']] = event_counts.get(log['event_id'], 0) + 1
        
        if event_counts:
            print(f"\nEvent Distribution:")
            for event_id, count in sorted(event_counts.items()):
                print(f"{event_id}: {count} occurrences")

def main():
    # File paths - modify these according to your file locations
    SOURCE_BUCKET = 'rca.logs.openstack'
    DEST_BUCKET = 'rca.logs.openstack'
    log_file = 'raw/OpenStack_2k.log'  # Your log file
    template_file = 'raw/OpenStack_2k.log_templates.csv'  # Your template file
    s3_output_file = 'silver/log_keys.txt'  # Output file
    AWS_REGION = 'us-east-1'
    output_file = 'log_keys.txt'
    s3 = boto3.client('s3', region_name=AWS_REGION)

    # Check if files exist
    try:
        # Try to read the file from S3
        print(f"Started to read file from S3 bucket: {SOURCE_BUCKET}")
        
        print("Create S3 object")
        log_file = s3.get_object(Bucket=SOURCE_BUCKET, Key=log_file)
        print(f"Successfully read file from S3 bucket: {SOURCE_BUCKET} , File Key {log_file}")
        print("Log file found in S3")
        # Process your log content here
      #  log_content = log_file['Body'].read().decode('utf-8')
        #print(log_content)
        print("Log file found in S3")
        # Read template from S3
        print(f"Started to read template from S3 bucket: {SOURCE_BUCKET}")
        template_file = s3.get_object(Bucket=SOURCE_BUCKET, Key=template_file)
        print(f"Successfully read template from S3 bucket: {SOURCE_BUCKET} , File Key {template_file}")
        print("Template file found in S3")
       # template_content = template_file['Body'].read().decode('utf-8')
       # print(template_content)
        # # Save the S3 file contents to a temporary file
        # with tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8', suffix='.log') as log_tmp:
        #     log_tmp.write(log_content)
        #     log_file_path = log_tmp.name

        # with tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8', suffix='.csv') as tmpl_tmp:
        #     tmpl_tmp.write(template_content)
        #     template_file_path = tmpl_tmp.name

        parser = OpenStackLogParser(log_file, template_file, debug=True)
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            print("Log file does not exist in S3")
            # Handle case when file doesn't exist
            # Create new log file or initialize empty content
            log_content = ""
        else:
            print(f"Error accessing S3: {e}")
            raise

    
    
    
    # Load templates
    print("Loading templates...")
    if not parser.load_templates():
        print("Failed to load templates. Exiting.")
        return
    
    # Test the specific content you mentioned
    test_content = '10.11.10.1 "GET /v2/54fadb412c4e40cdbaed9335e4c35a9e/servers/detail HTTP/1.1" status: 200 len: 1893 time: 0.2477829'
    parser.test_specific_content(test_content)
    
    # Parse logs
    print("\nParsing log file...")
    if not parser.parse_logs():
        print("Failed to parse logs. Exiting.")
        return
    
    # Save results
    print("Saving results...")
    parser.save_results(output_file)
    s3.upload_file(output_file, DEST_BUCKET, s3_output_file)


    print(f"Uploaded {output_file} to {DEST_BUCKET} with key {s3_output_file}")
    # Display statistics
    parser.get_statistics()
    
    print(f"\nProcessing complete! Check '{output_file}' for detailed results.")

if __name__ == "__main__":
    # Set debug mode here
    DEBUG_MODE = True
    
    if DEBUG_MODE:
        print("=== DEBUG MODE ENABLED ===")
        print("Current working directory:", os.getcwd())
        print("Files in directory:", os.listdir('.'))
        print("=" * 30)
    
    main()