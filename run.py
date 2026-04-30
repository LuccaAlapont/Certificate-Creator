"""Entrypoint: python run.py"""
import uvicorn

if __name__ == "__main__":
    print("Acesse: http://localhost:8001")
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8001, reload=True)
