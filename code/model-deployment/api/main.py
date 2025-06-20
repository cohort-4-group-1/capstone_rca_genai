from fastapi import FastAPI
from pydantic import BaseModel
from shared.model_utils import download_and_load_model, predict_from_file

app = FastAPI()
model = download_and_load_model()

class LogFileRequest(BaseModel):
    file_path: str

@app.post("/predict")
def predict(request: LogFileRequest):
    result = predict_from_file(model, request.file_path)
    return {"reconstruction": result}
