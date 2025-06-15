import re
import csv
import os
from datetime import datetime
import boto3

# Try to import pandas, fallback to csv if not available
SOURCE_BUCKET = 'rca.logs.openstack'
DEST_BUCKET = 'rca.logs.openstack'
FILE_KEY = 'raw/OpenStack_2k.log'
TEMPLATE_KEY = 'raw/OpenStack_2k.log_templates.csv'
OUTPUT_KEY = "silver/OpenStack_structured.csv"
AWS_REGION = 'us-east-1'

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    print("Warning: pandas not found. Using csv module instead.")

class OpenStackLogParser:
    def __init__(self, log_file_path, template_file_path, debug=False,s3):
        self.log_file_path = log_file_path
        self.template_file_path = template_file_path
        self.templates = {}
        self.parsed_logs = []
        self.debug = debug
        self.s3 = s3
    def debug_print(self, message):
        """Print debug messages if debug mode is enabled"""
        if self.debug:
            print(f"[DEBUG] {message}")
        
    def load_templates(self):
        """Load event templates from CSV file"""
        try:
            if not os.path.exists(self.template_file_path):
                print(f"Error: Template file '{self.template_file_path}' not found!")
                return False
                
            if HAS_PANDAS:
                df = pd.read_csv(self.template_file_path)
                for _, row in df.iterrows():
                    event_id = row['EventId']
                    template = row['EventTemplate']
                    # Convert template wildcards to regex patterns
                    regex_pattern = self.template_to_regex(template)
                    self.templates[event_id] = {
                        'template': template,
                        'regex': regex_pattern
                    }
            else:
                # Fallback to csv module
                with open(self.template_file_path, 'r', encoding='utf-8') as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        event_id = row['EventId']
                        template = row['EventTemplate']
                        # Convert template wildcards to regex patterns
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
                    print(" No match")
            except re.error as e:
                print(f" Regex error: {e}")
        
        print("\n No templates matched")
        return None, None
    
    def parse_logs(self):
        """Parse the log file and match against templates"""
        try:
            if not os.path.exists(self.log_file_path):
                print(f"Error: Log file '{self.log_file_path}' not found!")
                return False
                
            with open(self.log_file_path, 'r', encoding='utf-8') as file:
                for line_num, line in enumerate(file, 1):
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
            self.s3.put_object(Bucket=DEST_BUCKET, Key=OUTPUT_KEY, Body=output_file.getvalue())
            
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
    #log_file = 'OpenStack_2k.txt'  # Your log file
    #template_file = 'OpenStack_2k.log_templates.csv'  # Your template file
    #output_file = 'log_keys.txt'  # Output file
    
    # Check if files exist
    # if not os.path.exists(log_file):
    #     print(f"Error: Log file '{log_file}' not found in current directory!")
    #     print(f"Current directory: {os.getcwd()}")
    #     print("Available files:", os.listdir('.'))
    #     return
    
    # if not os.path.exists(template_file):
    #     print(f"Error: Template file '{template_file}' not found in current directory!")
    #     print(f"Current directory: {os.getcwd()}")
    #     print("Available files:", os.listdir('.'))
    #     return
    s3 = boto3.client('s3', region_name=AWS_REGION)
    print("Create S3 object")
    obj = s3.get_object(Bucket=SOURCE_BUCKET, Key=FILE_KEY)
    log_file = obj['Body'].read().decode('utf-8')
    template_obj = s3.get_object(Bucket=SOURCE_BUCKET, Key=TEMPLATE_KEY)
    template_file = template_obj['Body'].read().decode('utf-8')
    output_file = 'log_keys.txt'
    # Create parser instance with debug enabled
    parser = OpenStackLogParser(log_file, template_file, debug=True,s3)
    
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
    
    # Display statistics
    parser.get_statistics()
    
    print(f"\nProcessing complete! Check '{output_file}' for detailed results.")

if __name__ == "__main__":
    # Set debug mode here
    # DEBUG_MODE = False
    
    # if DEBUG_MODE:
    #     print("=== DEBUG MODE ENABLED ===")
    #     print("Current working directory:", os.getcwd())
    #     print("Files in directory:", os.listdir('.'))
    #     print("=" * 30)
    
    main()