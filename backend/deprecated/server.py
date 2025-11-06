from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from pathlib import Path

app = FastAPI()

# Allow CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

class InstructionFile(BaseModel):
    content: str
    project_directory: str | None = None

class DirectoryPath(BaseModel):
    path: str

class NewFolder(BaseModel):
    path: str
    folderName: str

# In a real app, you'd have a more robust way
# to map model names to file paths.
INSTRUCTION_FILES = {
    "Claude": "CLAUDE.md",
    "Codex": "AGENTS.md", # Assuming Codex uses the AGENTS.md file
    "Gemini": "GEMINI.md",
    "Qwen": "QWEN.md",
}

@app.get("/api/instructions/{model_name}")
async def get_instruction_file(model_name: str, project_directory: str | None = None):
    if model_name not in INSTRUCTION_FILES:
        raise HTTPException(status_code=404, detail="Model not found")

    base_path = project_directory if project_directory else os.path.join(os.path.dirname(__file__), "..")
    file_path = os.path.join(base_path, INSTRUCTION_FILES[model_name])

    try:
        with open(file_path, "r") as f:
            content = f.read()
        return {"content": content}
    except FileNotFoundError:
        return {"content": ""}

@app.post("/api/instructions/{model_name}")
async def save_instruction_file(model_name: str, instruction_file: InstructionFile):
    if model_name not in INSTRUCTION_FILES:
        raise HTTPException(status_code=404, detail="Model not found")

    base_path = instruction_file.project_directory if instruction_file.project_directory else os.path.join(os.path.dirname(__file__), "..")
    file_path = os.path.join(base_path, INSTRUCTION_FILES[model_name])

    try:
        with open(file_path, "w") as f:
            f.write(instruction_file.content)
        return {"message": "File saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/fs/browse")
async def browse_filesystem(directory_path: DirectoryPath):
    print(f"Browsing path: {directory_path.path}")
    try:
        base_path = Path(directory_path.path).resolve()
        if not base_path.is_dir():
            raise HTTPException(status_code=400, detail="Invalid directory path")

        contents = []
        for item in base_path.iterdir():
            contents.append({
                "name": item.name,
                "is_dir": item.is_dir(),
                "path": str(item)
            })
        return {"path": str(base_path), "contents": contents}
    except Exception as e:
        print(f"Error browsing path: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/fs/create-folder")
async def create_folder(new_folder: NewFolder):
    print(f"Creating folder: {new_folder.folderName} in {new_folder.path}")
    try:
        path = Path(new_folder.path).resolve()
        folder_name = new_folder.folderName
        new_folder_path = path / folder_name
        new_folder_path.mkdir()
        return {"message": f"Folder '{folder_name}' created successfully"}
    except FileExistsError as e:
        print(f"Error creating folder: {e}")
        raise HTTPException(status_code=400, detail="Folder with that name already exists")
    except Exception as e:
        print(f"Error creating folder: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
