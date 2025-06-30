import gradio as gr
import requests

# Replace with actual FastAPI server URL
API_URL = "http://localhost:9000/analyze-log"

def call_logbert_api(file_obj):
    try:
        response = requests.post(
            API_URL,
            files={"file": (file_obj.name, file_obj, "text/plain")},
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        return result
    except Exception as e:
        return {"error": str(e)}

gr.Interface(
    fn=call_logbert_api,
    inputs=gr.File(label="Upload log file"),
    outputs="json",
    title="LogBERT API Client",
    description="This UI sends your uploaded log file to the running LogBERT FastAPI server for anomaly analysis."
).launch(server_port=7860)
