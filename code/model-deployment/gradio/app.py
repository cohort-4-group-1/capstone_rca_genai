import gradio as gr
from shared.model_utils import download_and_load_model, predict_from_file

model = download_and_load_model()

def predict_ui(file_obj):
    return predict_from_file(model, file_obj.name)

gr.Interface(
    fn=predict_ui,
    inputs=gr.File(label="Upload raw log file"),
    outputs=gr.Textbox(label="Reconstructed vector"),
    title="LogBERT Gradio UI",
    description="Upload raw logs → parse → predict reconstruction"
).launch(server_name="0.0.0.0", server_port=7860)
