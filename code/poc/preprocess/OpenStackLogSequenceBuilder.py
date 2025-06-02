import re
from collections import Counter, defaultdict
import pickle
import json

class LogPreprocessor:
    def __init__(self):
        self.vocabulary = {}
        self.reverse_vocabulary = {}
        self.vocab_size = 0
        self.log_sequences = []
        
    def read_log_keys(self, file_path):
        """Read log keys from a text file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            log_keys = f.readlines()
        
        # Clean the log keys - remove newlines and strip whitespace
        log_keys = [key.strip() for key in log_keys if key.strip()]
        return log_keys
    
    def tokenize_log_key(self, log_key):
        """
        Tokenize a single log key into meaningful tokens
        Handles wildcards <*> and splits on common delimiters
        """
        # Replace common patterns and wildcards
        tokens = []
        
        # Split by common delimiters while preserving important tokens
        # Use regex to split on spaces, quotes, colons, brackets, etc.
        parts = re.split(r'[\s":\[\]()]+', log_key)
        
        for part in parts:
            if part:  # Skip empty strings
                if part == '<*>':
                    tokens.append('<WILDCARD>')
                elif part.isdigit():
                    tokens.append('<NUMBER>')
                elif re.match(r'^[0-9a-fA-F-]{36}$', part):  # UUID pattern
                    tokens.append('<UUID>')
                elif re.match(r'^\d+\.\d+$', part):  # Decimal number
                    tokens.append('<DECIMAL>')
                elif part.lower() in ['get', 'post', 'put', 'delete']:
                    tokens.append(f'<HTTP_{part.upper()}>')
                else:
                    tokens.append(part.lower())
        
        return tokens
    
    def build_vocabulary(self, log_keys):
        """Build vocabulary from all log keys"""
        all_tokens = []
        
        # Tokenize all log keys
        for log_key in log_keys:
            tokens = self.tokenize_log_key(log_key)
            all_tokens.extend(tokens)
        
        # Count token frequencies
        token_counts = Counter(all_tokens)
        
        # Build vocabulary (sorted by frequency for consistency)
        vocab_items = sorted(token_counts.items(), key=lambda x: (-x[1], x[0]))
        
        # Add special tokens
        self.vocabulary = {
            '<PAD>': 0,
            '<UNK>': 1,
            '<START>': 2,
            '<END>': 3
        }
        
        # Add tokens to vocabulary
        for token, count in vocab_items:
            if token not in self.vocabulary:
                self.vocabulary[token] = len(self.vocabulary)
        
        # Create reverse vocabulary
        self.reverse_vocabulary = {v: k for k, v in self.vocabulary.items()}
        self.vocab_size = len(self.vocabulary)
        
        print(f"Vocabulary built with {self.vocab_size} tokens")
        return self.vocabulary
    
    def log_key_to_sequence(self, log_key):
        """Convert a single log key to numeric sequence"""
        tokens = self.tokenize_log_key(log_key)
        
        # Convert tokens to numeric sequence
        sequence = [self.vocabulary.get('<START>', 2)]  # Start token
        
        for token in tokens:
            if token in self.vocabulary:
                sequence.append(self.vocabulary[token])
            else:
                sequence.append(self.vocabulary.get('<UNK>', 1))  # Unknown token
        
        sequence.append(self.vocabulary.get('<END>', 3))  # End token
        
        return sequence
    
    def convert_logs_to_sequences(self, log_keys):
        """Convert all log keys to numeric sequences"""
        self.log_sequences = []
        
        for log_key in log_keys:
            sequence = self.log_key_to_sequence(log_key)
            self.log_sequences.append(sequence)
        
        return self.log_sequences
    
    def get_sequence_statistics(self):
        """Get statistics about the sequences"""
        if not self.log_sequences:
            return {}
        
        lengths = [len(seq) for seq in self.log_sequences]
        
        stats = {
            'total_sequences': len(self.log_sequences),
            'avg_length': sum(lengths) / len(lengths),
            'min_length': min(lengths),
            'max_length': max(lengths),
            'vocab_size': self.vocab_size
        }
        
        return stats
    
    def save_vocabulary(self, file_path):
        """Save vocabulary to file"""
        with open(file_path, 'w') as f:
            json.dump(self.vocabulary, f, indent=2)
    
    def load_vocabulary(self, file_path):
        """Load vocabulary from file"""
        with open(file_path, 'r') as f:
            self.vocabulary = json.load(f)
        
        self.reverse_vocabulary = {v: k for k, v in self.vocabulary.items()}
        self.vocab_size = len(self.vocabulary)
    
    def save_sequences(self, file_path):
        """Save sequences to file"""
        with open(file_path, 'wb') as f:
            pickle.dump(self.log_sequences, f)
    
    def load_sequences(self, file_path):
        """Load sequences from file"""
        with open(file_path, 'rb') as f:
            self.log_sequences = pickle.load(f)
    
    def sequence_to_log_key(self, sequence):
        """Convert numeric sequence back to readable log key (for debugging)"""
        tokens = []
        for num in sequence:
            if num in self.reverse_vocabulary:
                tokens.append(self.reverse_vocabulary[num])
            else:
                tokens.append('<UNK>')
        
        return ' '.join(tokens)
    
    def display_sequence_details(self, sequence_idx):
        """Display detailed breakdown of a specific sequence"""
        if sequence_idx >= len(self.log_sequences):
            print(f"Sequence index {sequence_idx} out of range")
            return
        
        sequence = self.log_sequences[sequence_idx]
        print(f"\nDetailed breakdown of sequence {sequence_idx + 1}:")
        print("Token Number -> Token Text")
        print("-" * 30)
        
        for i, num in enumerate(sequence):
            token = self.reverse_vocabulary.get(num, '<UNK>')
            print(f"{i+1:2d}. {num:3d} -> {token}")
    
    def display_all_sequences_summary(self):
        """Display a summary of all sequences"""
        print("\nAll Log Sequences Summary:")
        print("=" * 100)
        print(f"{'#':<3} {'Length':<6} {'Sequence':<50} {'First 5 tokens'}")
        print("-" * 100)
        
        for i, seq in enumerate(self.log_sequences):
            first_5_tokens = [self.reverse_vocabulary.get(num, '<UNK>') for num in seq[:5]]
            first_5_str = ' '.join(first_5_tokens)
            if len(seq) > 5:
                first_5_str += "..."
            
            seq_str = str(seq)
            if len(seq_str) > 45:
                seq_str = seq_str[:42] + "...]"
            
            print(f"{i+1:<3} {len(seq):<6} {seq_str:<50} {first_5_str}")
    
    def export_sequences_to_file(self, filename='log_sequences_readable.txt'):
        """Export sequences in a readable format to a text file"""
        with open(filename, 'w') as f:
            f.write("Log Sequences - Detailed View\n")
            f.write("=" * 80 + "\n\n")
            
            for i, seq in enumerate(self.log_sequences):
                f.write(f"Log Entry {i+1}:\n")
                f.write(f"Sequence: {seq}\n")
                f.write("Token breakdown:\n")
                
                for j, num in enumerate(seq):
                    token = self.reverse_vocabulary.get(num, '<UNK>')
                    f.write(f"  {j+1:2d}. {num:3d} -> {token}\n")
                
                f.write(f"Decoded: {self.sequence_to_log_key(seq)}\n")
                f.write("-" * 40 + "\n\n")
        
        print(f"Detailed sequences exported to: {filename}")


def main():
    # Initialize preprocessor
    preprocessor = LogPreprocessor()
    
    # File paths
    log_keys_file = 'log_keys.txt'  # Your input file
    vocab_file = 'vocabulary.json'
    sequences_file = 'log_sequences.pkl'
    
    print("Starting log preprocessing pipeline...")
    
    # Step 1: Read log keys from file
    print("Step 1: Reading log keys from file...")
    try:
        log_keys = preprocessor.read_log_keys(log_keys_file)
        print(f"Read {len(log_keys)} log keys")
    except FileNotFoundError:
        print(f"File {log_keys_file} not found. Creating sample data...")
        # Create sample log keys based on your example
        sample_log_keys = [
            '<*> "GET <*>" status: <*> len: <*> time: <*>.<*>',
            '[instance: <*>] VM Started (Lifecycle Event)',
            '[instance: <*>] VM Paused (Lifecycle Event)',
            '[instance: <*>] During sync_power_state the instance has a pending task (spawning). Skip.',
            'image <*> at (<*>): checking image',
            'Active base files: <*>',
            'Creating event network-vif-plugged:<*>-<*>-<*>-<*>-<*> for instance <*>'
        ]
        
        # Save sample data to file
        with open(log_keys_file, 'w') as f:
            for key in sample_log_keys:
                f.write(key + '\n')
        
        log_keys = sample_log_keys
        print(f"Created {len(log_keys)} sample log keys")
    
    # Step 2: Build vocabulary
    print("\nStep 2: Building vocabulary...")
    vocabulary = preprocessor.build_vocabulary(log_keys)
    
    # Display some vocabulary items
    print("Sample vocabulary items:")
    for i, (token, idx) in enumerate(list(vocabulary.items())[:10]):
        print(f"  {token}: {idx}")
    if len(vocabulary) > 10:
        print(f"  ... and {len(vocabulary) - 10} more")
    
    # Step 3: Convert log keys to sequences
    print("\nStep 3: Converting log keys to numeric sequences...")
    sequences = preprocessor.convert_logs_to_sequences(log_keys)
    
    # Display all sequences
    print("All Log Sequences:")
    print("=" * 80)
    for i, seq in enumerate(sequences):
        original_log = log_keys[i]
        decoded_log = preprocessor.sequence_to_log_key(seq)
        
        print(f"\nLog Entry {i+1}:")
        print(f"Original:  {original_log}")
        print(f"Sequence:  {seq}")
        print(f"Decoded:   {decoded_log}")
        print(f"Length:    {len(seq)} tokens")
        print("-" * 40)
    
    # Step 4: Get statistics
    print("\nStep 4: Sequence statistics:")
    stats = preprocessor.get_sequence_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Step 5: Display all sequences in detail
    print("\nStep 5: Displaying all sequences...")
    preprocessor.display_all_sequences_summary()
    
    # Export detailed sequences to file
    preprocessor.export_sequences_to_file()
    
    # Show detailed breakdown of first few sequences
    print("\nDetailed breakdown of first 3 sequences:")
    for i in range(min(3, len(sequences))):
        preprocessor.display_sequence_details(i)
    
    # Step 6: Save results
    print(f"\nStep 6: Saving results...")
    preprocessor.save_vocabulary(vocab_file)
    preprocessor.save_sequences(sequences_file)
    print(f"Vocabulary saved to: {vocab_file}")
    print(f"Sequences saved to: {sequences_file}")
    
    print("\nLog preprocessing pipeline completed!")
    
    return preprocessor, vocabulary, sequences


if __name__ == "__main__":
    preprocessor, vocabulary, sequences = main()