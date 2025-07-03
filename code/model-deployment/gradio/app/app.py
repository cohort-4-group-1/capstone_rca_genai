import gradio as gr
import requests

API_URL = "http://localhost:9000/analyze-log"

def call_logbert_api(file_path_str):
    try:
        with open(file_path_str, "rb") as f:
            response = requests.post(
                API_URL,
                files={"file": ("uploaded.log", f, "multipart/form-data")}
            )
            response.raise_for_status()
            result = response.json()

            anomalies = []
            normals = []

            for r in result:
                score = f"{r['anomaly_score']:.6f}"
                line = r["window_start_line"]
                is_anomaly = r["is_anomaly"]

                formatted = f"Score: {score}\nLine: {line}\n"

                if is_anomaly:
                    anomalies.append(formatted)
                else:
                    normals.append(formatted)

            normal_text = "\n---\n".join(normals) if normals else "✅ No anomalies detected."
            anomaly_text = "\n---\n".join(anomalies) if anomalies else "🎉 No anomalies found."

            return normal_text, anomaly_text

    except Exception as e:
        return f"Error: {str(e)}", ""

# UI layout
gr.Interface(
    fn=call_logbert_api,
    inputs=gr.File(label="Upload log file", type="filepath"),
    outputs=[
        gr.Textbox(label="✅ Normal Sequences"),
        gr.Textbox(label="❌ Anomalous Sequences")
    ],
    title="LogBERT Anomaly Analyzer",
    description="Upload a log file. This tool separates normal and anomalous log sequences based on Isolation Forest results."
).launch(server_port=7860)
