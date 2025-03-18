from fastapi import APIRouter

router = APIRouter()

# Example route (you can replace or extend this with your actual routes)
@router.get("/")
def root():
  return {"message": "Welcome to the index-o API!"}
