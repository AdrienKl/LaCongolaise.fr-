from fastapi import FastAPI, APIRouter, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
from enum import Enum


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class SortOrder(str, Enum):
    DATE_DESC = "date_desc"
    DATE_ASC = "date_asc"
    RATING_DESC = "rating_desc"
    RATING_ASC = "rating_asc"


class Review(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReviewCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=500)


class ReviewStats(BaseModel):
    average_rating: float
    total_reviews: int


class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StatusCheckCreate(BaseModel):
    client_name: str


# Routes
@api_router.get("/")
async def root():
    return {"message": "La Congolaise API"}


# Review routes
@api_router.post("/reviews", response_model=Review)
async def create_review(review_input: ReviewCreate):
    """Create a new review"""
    review = Review(
        name=review_input.name,
        rating=review_input.rating,
        comment=review_input.comment
    )
    
    doc = review.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    
    await db.reviews.insert_one(doc)
    return review


@api_router.get("/reviews", response_model=List[Review])
async def get_reviews(sort: SortOrder = Query(default=SortOrder.DATE_DESC)):
    """Get all reviews with optional sorting"""
    sort_options = {
        SortOrder.DATE_DESC: [("created_at", -1)],
        SortOrder.DATE_ASC: [("created_at", 1)],
        SortOrder.RATING_DESC: [("rating", -1), ("created_at", -1)],
        SortOrder.RATING_ASC: [("rating", 1), ("created_at", -1)],
    }
    
    reviews = await db.reviews.find({}, {"_id": 0}).sort(sort_options[sort]).to_list(1000)
    
    for review in reviews:
        if isinstance(review.get('created_at'), str):
            review['created_at'] = datetime.fromisoformat(review['created_at'])
    
    return reviews


@api_router.get("/reviews/stats", response_model=ReviewStats)
async def get_review_stats():
    """Get review statistics (average rating and total count)"""
    pipeline = [
        {
            "$group": {
                "_id": None,
                "average_rating": {"$avg": "$rating"},
                "total_reviews": {"$sum": 1}
            }
        }
    ]
    
    result = await db.reviews.aggregate(pipeline).to_list(1)
    
    if result:
        return ReviewStats(
            average_rating=round(result[0]["average_rating"], 1),
            total_reviews=result[0]["total_reviews"]
        )
    
    return ReviewStats(average_rating=0, total_reviews=0)


# Status routes
@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    
    await db.status_checks.insert_one(doc)
    return status_obj


@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    
    return status_checks


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
