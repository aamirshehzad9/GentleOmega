from fastapi import FastAPI

app = FastAPI(title="GentleOmega Simple Test")

@app.get("/health")
def health():
    return {"status": "ok", "dim": 384, "blockchain": "enabled"}

@app.post("/items")
def create_item(content: str, user_id: str):
    return {"status": "success", "id": 123, "content": content, "user_id": user_id}