from fastapi import FastAPI, HTTPException
from src.controllers import router as api_router
from pydantic import BaseModel
from typing import List, Dict
import os
from collections import defaultdict
import hashlib
import logging
from src.utils.image_classification import is_meme, is_screenshot, is_document  # Importar nueva función
from datetime import datetime

logging.basicConfig(level=logging.INFO)

app = FastAPI()

app.include_router(api_router)

@app.get("/health")
def health_check():
    return {"status": "ok"}

class FolderPath(BaseModel):
    path: str

class DeleteDuplicatesRequest(BaseModel):
    path: str
    duplicates: Dict[int, List[str]]

class MoveFilesRequest(BaseModel):
    path: str
    memes: List[Dict[str, str]]
    screenshots: List[Dict[str, str]]
    videos: List[Dict[str, str]] = []  # Field for videos, with default empty list

class OrganizeMediaRequest(BaseModel):
    path: str
    photos: List[Dict[str, str]] = []
    videos: List[Dict[str, str]] = []

# Keep OrganizePhotosRequest for backward compatibility
class OrganizePhotosRequest(BaseModel):
    path: str
    photos: List[Dict[str, str]]

@app.post("/list-files")
def list_files(folder: FolderPath) -> Dict[str, List[Dict[str, str]] | Dict[int, List[str]] | Dict[str, List[Dict[str, str]]]]:
    try:
        # Verificar si la ruta proporcionada es válida
        if not os.path.isdir(folder.path):
            raise HTTPException(status_code=400, detail="Invalid folder path")
        
        # Listar todos los archivos en la carpeta
        image_extensions = {".jpg", ".jpeg", ".png", ".gif"}
        video_extensions = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v"}
        
        files = [
            f for f in os.listdir(folder.path)
            if os.path.isfile(os.path.join(folder.path, f)) and 
            (os.path.splitext(f)[1].lower() in image_extensions or 
             os.path.splitext(f)[1].lower() in video_extensions)
        ]
        
        # Clasificar archivos
        memes = []
        screenshots = []
        documents = []
        photos = []
        videos = []  # Lista para videos
        
        for file in files:
            file_path = os.path.join(folder.path, file)
            file_ext = os.path.splitext(file)[1].lower()
            logging.info(f"Processing file: {file}")  # Log del archivo que se está procesando
            
            # Verificar si es un video
            if file_ext in video_extensions:
                videos.append({"file": file, "path": file_path})
                continue
                
            # Procesar imágenes
            if is_meme(file_path):
                memes.append({"file": file, "path": file_path})
            elif is_screenshot(file_path):
                screenshots.append({"file": file, "path": file_path})
            elif is_document(file_path):
                documents.append({"file": file, "path": file_path})
            else:
                photos.append({"file": file, "path": file_path})
        
        logging.info(f"Total documents found: {len(documents)}")
        logging.info(f"Total screenshots found: {len(screenshots)}")
        logging.info(f"Total photos found: {len(photos)}")
        logging.info(f"Total videos found: {len(videos)}")  # Log del total de videos encontrados
        
        # Calcular el hash de cada archivo y buscar duplicados (solo para fotos)
        file_hashes = defaultdict(list)
        for file_info in photos:
            file_path = file_info["path"]
            logging.info(f"Calculating hash for file: {file_info['file']}")  # Log del archivo al calcular el hash
            with open(file_path, "rb") as f:
                file_hash = hashlib.md5(f.read()).hexdigest()  # Calcula el hash MD5 del archivo
            file_hashes[file_hash].append(file_info["file"])
        
        duplicates = {idx: names for idx, names in enumerate(file_hashes.values(), start=1) if len(names) > 1}
        
        return {
            "photos": photos,
            "videos": videos,  # Incluir videos en la respuesta
            "duplicates": duplicates,
            "memes": memes,
            "screenshots": screenshots,
            "documents": documents  # Incluir documentos en la respuesta
        }
    except Exception as e:
        logging.error(f"Error processing files: {str(e)}")  # Log del error
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/delete-duplicates")
def delete_duplicates(request: DeleteDuplicatesRequest) -> Dict[str, List[str]]:
    try:
        # Verificar si la ruta proporcionada es válida
        if not os.path.isdir(request.path):
            raise HTTPException(status_code=400, detail="Invalid folder path")
        
        deleted_files = []
        for group_id, duplicate_files in request.duplicates.items():
            # Mantener el primer archivo y eliminar los demás
            for file in duplicate_files[1:]:
                file_path = os.path.join(request.path, file)
                if os.path.exists(file_path):
                    logging.info(f"Deleting duplicate file: {file_path}")
                    os.remove(file_path)
                    deleted_files.append(file_path)
        
        return {"deleted_files": deleted_files}
    except Exception as e:
        logging.error(f"Error deleting duplicates: {str(e)}")  # Log del error
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/move-files")
def move_files(request: MoveFilesRequest) -> Dict[str, List[str]]:
    try:
        # Verificar si la ruta proporcionada es válida
        if not os.path.isdir(request.path):
            raise HTTPException(status_code=400, detail="Invalid folder path")
        
        # Crear carpetas para memes, screenshots y videos si no existen
        memes_folder = os.path.join(request.path, "memes")
        screenshots_folder = os.path.join(request.path, "screenshots")
        videos_folder = os.path.join(request.path, "videos")
        os.makedirs(memes_folder, exist_ok=True)
        os.makedirs(screenshots_folder, exist_ok=True)
        os.makedirs(videos_folder, exist_ok=True)

        moved_memes = []
        moved_screenshots = []
        moved_videos = []

        # Mover memes
        for meme in request.memes:
            source_path = meme["path"]
            destination_path = os.path.join(memes_folder, meme["file"])
            if os.path.exists(source_path):
                logging.info(f"Moving meme: {source_path} -> {destination_path}")
                os.rename(source_path, destination_path)
                moved_memes.append(destination_path)

        # Mover screenshots
        for screenshot in request.screenshots:
            source_path = screenshot["path"]
            destination_path = os.path.join(screenshots_folder, screenshot["file"])
            if os.path.exists(source_path):
                logging.info(f"Moving screenshot: {source_path} -> {destination_path}")
                os.rename(source_path, destination_path)
                moved_screenshots.append(destination_path)

        # Mover videos
        for video in request.videos:
            source_path = video["path"]
            destination_path = os.path.join(videos_folder, video["file"])
            if os.path.exists(source_path):
                logging.info(f"Moving video: {source_path} -> {destination_path}")
                os.rename(source_path, destination_path)
                moved_videos.append(destination_path)

        return {
            "moved_memes": moved_memes,
            "moved_screenshots": moved_screenshots,
            "moved_videos": moved_videos
        }
    except Exception as e:
        logging.error(f"Error moving files: {str(e)}")  # Log del error
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/organize-media")
def organize_media(request: OrganizeMediaRequest) -> Dict[str, List[str]]:
    try:
        # Verificar si la ruta proporcionada es válida
        if not os.path.isdir(request.path):
            raise HTTPException(status_code=400, detail="Invalid folder path")
        
        # Crear la carpeta base "media-to-nas" si no existe
        base_folder = os.path.join(request.path, "media-to-nas")
        os.makedirs(base_folder, exist_ok=True)

        organized_photos = []
        organized_videos = []

        # Organizar las fotos por año y mes
        for photo in request.photos:
            source_path = photo["path"]
            if not os.path.exists(source_path):
                logging.warning(f"Photo not found: {source_path}")
                continue

            # Obtener la fecha de modificación del archivo
            modification_time = os.path.getmtime(source_path)
            date = datetime.fromtimestamp(modification_time)
            year = date.strftime("%Y")
            month = date.strftime("%m")

            # Crear carpetas por año y mes
            year_folder = os.path.join(base_folder, "photos", year)
            month_folder = os.path.join(year_folder, month)
            os.makedirs(month_folder, exist_ok=True)

            # Mover la foto a la carpeta correspondiente
            destination_path = os.path.join(month_folder, photo["file"])
            logging.info(f"Moving photo: {source_path} -> {destination_path}")
            os.rename(source_path, destination_path)
            organized_photos.append(destination_path)

        # Organizar los videos por año y mes
        for video in request.videos:
            source_path = video["path"]
            if not os.path.exists(source_path):
                logging.warning(f"Video not found: {source_path}")
                continue

            # Obtener la fecha de modificación del archivo
            modification_time = os.path.getmtime(source_path)
            date = datetime.fromtimestamp(modification_time)
            year = date.strftime("%Y")
            month = date.strftime("%m")

            # Crear carpetas por año y mes
            year_folder = os.path.join(base_folder, "videos", year)
            month_folder = os.path.join(year_folder, month)
            os.makedirs(month_folder, exist_ok=True)

            # Mover el video a la carpeta correspondiente
            destination_path = os.path.join(month_folder, video["file"])
            logging.info(f"Moving video: {source_path} -> {destination_path}")
            os.rename(source_path, destination_path)
            organized_videos.append(destination_path)

        return {
            "organized_photos": organized_photos,
            "organized_videos": organized_videos
        }
    except Exception as e:
        logging.error(f"Error organizing media: {str(e)}")  # Log del error
        raise HTTPException(status_code=500, detail=str(e))