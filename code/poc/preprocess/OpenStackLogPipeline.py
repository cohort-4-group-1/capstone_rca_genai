#!/usr/bin/env python3
"""
OpenStack Log Processing Pipeline

This pipeline executes:
1. OpenStackKeyExtractor.py - Extracts log keys from raw log files
2. OpenStackLogSequenceBuilder.py - Converts log keys to numeric sequences

Author: Pipeline Builder
Date: 2025
"""

import os
import sys
import subprocess
import time
import logging
from pathlib import Path
from datetime import datetime

class OpenStackLogPipeline:
    def __init__(self, config=None):
        """
        Initialize the pipeline with configuration
        
        Args:
            config (dict): Pipeline configuration parameters
        """
        self.config = config or {}
        self.setup_logging()
        
        # Default paths - can be overridden in config
        self.key_extractor_script = self.config.get('key_extractor_script', 'OpenStackKeyExtractor.py')
        self.sequence_builder_script = self.config.get('sequence_builder_script', 'OpenStackLogSequenceBuilder.py')
        
        # Pipeline status
        self.pipeline_start_time = None
        self.pipeline_end_time = None
        self.execution_status = {}
        
    def setup_logging(self):
        """Setup logging for the pipeline"""
        log_level = self.config.get('log_level', 'INFO')
        log_file = self.config.get('log_file', 'pipeline.log')
        
        # Create logs directory if it doesn't exist
        log_dir = Path(log_file).parent
        log_dir.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def check_script_exists(self, script_path):
        """Check if a script file exists"""
        if not os.path.exists(script_path):
            self.logger.error(f"Script not found: {script_path}")
            return False
        return True
        
    def run_script(self, script_path, script_name, args=None):
        """
        Execute a Python script and capture its output
        
        Args:
            script_path (str): Path to the Python script
            script_name (str): Human-readable name of the script
            args (list): Additional command line arguments
            
        Returns:
            dict: Execution results with status, output, and timing
        """
        self.logger.info(f"Starting {script_name}...")
        
        if not self.check_script_exists(script_path):
            return {
                'success': False,
                'error': f"Script not found: {script_path}",
                'start_time': None,
                'end_time': None,
                'duration': 0,
                'output': '',
                'error_output': ''
            }
        
        start_time = time.time()
        
        try:
            # Build command
            cmd = [sys.executable, script_path]
            if args:
                cmd.extend(args)
            
            self.logger.info(f"Executing command: {' '.join(cmd)}")
            
            # Execute the script
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.get('script_timeout', 300)  # 5 minute default timeout
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            if result.returncode == 0:
                self.logger.info(f"{script_name} completed successfully in {duration:.2f} seconds")
                return {
                    'success': True,
                    'return_code': result.returncode,
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration': duration,
                    'output': result.stdout,
                    'error_output': result.stderr
                }
            else:
                self.logger.error(f"{script_name} failed with return code {result.returncode}")
                self.logger.error(f"Error output: {result.stderr}")
                return {
                    'success': False,
                    'return_code': result.returncode,
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration': duration,
                    'output': result.stdout,
                    'error_output': result.stderr,
                    'error': f"Script failed with return code {result.returncode}"
                }
                
        except subprocess.TimeoutExpired:
            end_time = time.time()
            duration = end_time - start_time
            error_msg = f"{script_name} timed out after {duration:.2f} seconds"
            self.logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'start_time': start_time,
                'end_time': end_time,
                'duration': duration,
                'output': '',
                'error_output': 'Process timed out'
            }
            
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            error_msg = f"Error executing {script_name}: {str(e)}"
            self.logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'start_time': start_time,
                'end_time': end_time,
                'duration': duration,
                'output': '',
                'error_output': str(e)
            }
    
    def run_pipeline(self, extractor_args=None, builder_args=None):
        """
        Execute the complete pipeline
        
        Args:
            extractor_args (list): Arguments for OpenStackKeyExtractor.py
            builder_args (list): Arguments for OpenStackLogSequenceBuilder.py
            
        Returns:
            dict: Complete pipeline execution results
        """
        self.pipeline_start_time = time.time()
        self.logger.info("=" * 80)
        self.logger.info("STARTING OPENSTACK LOG PROCESSING PIPELINE")
        self.logger.info("=" * 80)
        
        pipeline_results = {
            'pipeline_success': False,
            'start_time': self.pipeline_start_time,
            'steps': {}
        }
        
        # Step 1: Execute OpenStackKeyExtractor.py
        self.logger.info("STEP 1: Executing OpenStack Key Extractor")
        self.logger.info("-" * 50)
        
        extractor_result = self.run_script(
            self.key_extractor_script,
            "OpenStack Key Extractor",
            extractor_args
        )
        
        pipeline_results['steps']['key_extractor'] = extractor_result
        self.execution_status['key_extractor'] = extractor_result['success']
        
        if not extractor_result['success']:
            self.logger.error("Key Extractor failed. Stopping pipeline.")
            pipeline_results['pipeline_success'] = False
            pipeline_results['failure_reason'] = "Key Extractor failed"
            return self.finalize_pipeline(pipeline_results)
        
        # Step 2: Execute OpenStackLogSequenceBuilder.py
        self.logger.info("\nSTEP 2: Executing OpenStack Log Sequence Builder")
        self.logger.info("-" * 50)
        
        builder_result = self.run_script(
            self.sequence_builder_script,
            "OpenStack Log Sequence Builder",
            builder_args
        )
        
        pipeline_results['steps']['sequence_builder'] = builder_result
        self.execution_status['sequence_builder'] = builder_result['success']
        
        if not builder_result['success']:
            self.logger.error("Log Sequence Builder failed.")
            pipeline_results['pipeline_success'] = False
            pipeline_results['failure_reason'] = "Log Sequence Builder failed"
            return self.finalize_pipeline(pipeline_results)
        
        # Pipeline completed successfully
        pipeline_results['pipeline_success'] = True
        self.logger.info("Pipeline completed successfully!")
        
        return self.finalize_pipeline(pipeline_results)
    
    def finalize_pipeline(self, results):
        """Finalize pipeline execution and generate summary"""
        self.pipeline_end_time = time.time()
        total_duration = self.pipeline_end_time - self.pipeline_start_time
        
        results['end_time'] = self.pipeline_end_time
        results['total_duration'] = total_duration
        
        self.logger.info("\n" + "=" * 80)
        self.logger.info("PIPELINE EXECUTION SUMMARY")
        self.logger.info("=" * 80)
        self.logger.info(f"Pipeline Status: {'SUCCESS' if results['pipeline_success'] else 'FAILED'}")
        self.logger.info(f"Total Duration: {total_duration:.2f} seconds")
        self.logger.info(f"Start Time: {datetime.fromtimestamp(self.pipeline_start_time)}")
        self.logger.info(f"End Time: {datetime.fromtimestamp(self.pipeline_end_time)}")
        
        # Step-by-step summary
        self.logger.info("\nStep Results:")
        for step_name, step_result in results['steps'].items():
            status = "SUCCESS" if step_result['success'] else "FAILED"
            duration = step_result.get('duration', 0)
            self.logger.info(f"  {step_name}: {status} ({duration:.2f}s)")
            
            if not step_result['success'] and 'error' in step_result:
                self.logger.error(f"    Error: {step_result['error']}")
        
        self.logger.info("=" * 80)
        
        return results
    
    def save_results(self, results, output_file='pipeline_results.json'):
        """Save pipeline results to a JSON file"""
        import json
        
        # Convert timestamps to readable format
        results_copy = results.copy()
        if 'start_time' in results_copy:
            results_copy['start_time_readable'] = datetime.fromtimestamp(results_copy['start_time']).isoformat()
        if 'end_time' in results_copy:
            results_copy['end_time_readable'] = datetime.fromtimestamp(results_copy['end_time']).isoformat()
        
        for step_name, step_result in results_copy['steps'].items():
            if 'start_time' in step_result and step_result['start_time']:
                step_result['start_time_readable'] = datetime.fromtimestamp(step_result['start_time']).isoformat()
            if 'end_time' in step_result and step_result['end_time']:
                step_result['end_time_readable'] = datetime.fromtimestamp(step_result['end_time']).isoformat()
        
        with open(output_file, 'w') as f:
            json.dump(results_copy, f, indent=2)
        
        self.logger.info(f"Pipeline results saved to: {output_file}")


def main():
    """Main function to run the pipeline"""
    
    # Configuration
    config = {
        'log_level': 'INFO',
        'log_file': 'logs/openstack_pipeline.log',
        'script_timeout': 600,  # 10 minutes timeout per script
        'key_extractor_script': 'OpenStackKeyExtractor.py',
        'sequence_builder_script': 'OpenStackLogSequenceBuilder.py'
    }
    
    # Initialize pipeline
    pipeline = OpenStackLogPipeline(config)
    
    # Arguments for each script (modify as needed)
    extractor_args = []  # Add any arguments for OpenStackKeyExtractor.py
    builder_args = []    # Add any arguments for OpenStackLogSequenceBuilder.py
    
    # Run the pipeline
    results = pipeline.run_pipeline(extractor_args, builder_args)
    
    # Save results
    pipeline.save_results(results, 'logs/pipeline_results.json')
    
    # Exit with appropriate code
    sys.exit(0 if results['pipeline_success'] else 1)


if __name__ == "__main__":
    main()