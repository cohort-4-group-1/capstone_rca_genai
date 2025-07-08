import sys
import subprocess


def run_without_encoder_fastapi():
    try:
        subprocess.run([
            "uvicorn", "main_without_encoder:app", "--host", "0.0.0.0", "--port", "9000"
            ],check=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to launch: {e}")
        sys.exit(1)

def run_iforest():
    try:
        subprocess.run([
            "uvicorn", "main_isolation_forest:app", "--host", "0.0.0.0", "--port", "9000"
            ],check=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to launch: {e}")
        sys.exit(1)
def run_encoder_fastapi():
    try:
        subprocess.run([
            "uvicorn", "main_encoder:app", "--host", "0.0.0.0", "--port", "9000"
            ],check=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to launch: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if "--encoder" in sys.argv:
        run_encoder_fastapi()
    else:
        run_iforest()
