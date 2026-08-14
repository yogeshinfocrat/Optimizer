from datetime import datetime
from typing import Literal, Optional
from mongoengine import Document, DictField, DateTimeField, StringField, ListField
from pydantic import BaseModel
from mongoengine.errors import NotUniqueError
from src.Mongo_Manager.schemas.beta.bestfit_schema import RoutingRequest, RoutingResponse
from src.Utils.log import logger
from datetime import datetime, timezone


RoutingTaskStatus = Literal["PROCESSING", "COMPLETE", "FAILED","PARTIALLY COMPLETE"]


# A Routing Task encompasses both a request and response for transformer
class RoutingTask(BaseModel):
    """RoutingTask model"""

    requestId: str
    requestType: str
    request: RoutingRequest
    response: RoutingResponse | None = None
    timestamp: datetime
    status: RoutingTaskStatus = "PROCESSING"
    error: str | None = None
    unassigned_message: str | None = None
    completion_time: Optional[datetime] = None




# DB representation of RoutingTask
class RoutingTaskDb(Document):
    """RoutingTask model"""

    requestId = StringField(required=True)
    requestType = StringField(required=False)
    request = DictField(required=True)
    response = DictField(required=False)
    timestamp = DateTimeField(required=True)
    status = StringField(required=True)
    error = StringField(required=False)
    unreachable_eve = StringField(required=False)
    completion_time= DateTimeField(required=False)

    meta = {
        "collection": "routing_task",
        "indexes": [
            {
                "fields": ["requestId"],
                "unique": True,
            }
        ],
    }

    def __str__(self):
        """String representation of the transformer task"""
        return f"requestId: {self.requestId}, request: {self.request}, response: {self.response}, timestamp: {self.timestamp}"

    class Config:
        """Pydantic config"""

        orm_mode = True


class RoutingTaskRepository:
    """Repository class for the routing_task collection"""

    def get_routing_tasks_with_ids(self, requestIds: list[str]) -> list[RoutingTask]:
        """Gets the transformer tasks by requestIds"""
        routing_task_dbs = RoutingTaskDb.objects(requestId__in=requestIds)
        if routing_task_dbs is None:
            return []
        return [
            RoutingTask(
                requestId=routing_task_db.requestId,
                requestType=routing_task_db.requestType,
                request=RoutingRequest(**routing_task_db.request),
                response=RoutingResponse(**routing_task_db.response),
                timestamp=routing_task_db.timestamp,
                status=routing_task_db.status,
                unassigned_message=routing_task_db.unreachable_eve,
                completion_time = routing_task_db.completion_time

        )
            for routing_task_db in routing_task_dbs
        ]

    def get_routing_task_by_requestId(self, requestId: str) -> RoutingTask | None:
        """Gets the transformer task by requestId"""
        routing_task_db = RoutingTaskDb.objects(requestId=requestId).first()
        if routing_task_db is None:
            return None

        response = RoutingResponse(**routing_task_db.response) if routing_task_db.response else None
        return RoutingTask(
            requestId=routing_task_db.requestId,
            requestType=routing_task_db.requestType,
            request=RoutingRequest(**routing_task_db.request),
            response=response,
            error=routing_task_db.error,
            timestamp=routing_task_db.timestamp,
            status=routing_task_db.status,
            unassigned_message = routing_task_db.unreachable_eve,
            completion_time=routing_task_db.completion_time
        )

    def insert_routing_task(self, routing_task: RoutingTask) -> RoutingTask:
        """Inserts the transformer tasks into the database"""
        routing_task_db = RoutingTaskDb(
            requestId=routing_task.requestId,
            requestType=routing_task.requestType,
            request=routing_task.request.dict(),
            timestamp=routing_task.timestamp,
            status=routing_task.status,
            completion_time = routing_task.completion_time
        )
        return routing_task_db.save()


    def complete_routing_task(self, requestId: str, response: RoutingResponse, message):
        updated = RoutingTaskDb.objects(requestId=requestId).update_one(
            set__response=response.model_dump(exclude_none=False),
            set__status="COMPLETE",
            set__unreachable_eve=message,
            set__completion_time=datetime.now(timezone.utc)
        )
        if updated == 0:
            raise ValueError(f"Task not found: {requestId}")
        return updated

    def fail_routing_task(self, requestId: str, error: str):
        updated = RoutingTaskDb.objects(requestId=requestId).update_one(
            set__status="FAILED",
            set__error=error,
            set__completion_time=datetime.now(timezone.utc)
        )
        if updated == 0:
            raise ValueError(f"Task not found: {requestId}")
        return updated


    def partially_complete_routing_task(self, requestId: str, response: RoutingResponse, message):
        updated = RoutingTaskDb.objects(requestId=requestId).update_one(
            set__response=response.model_dump(exclude_none=False),
            set__status="PARTIALLY COMPLETE",
            set__unreachable_eve=message,
            set__completion_time=datetime.now(timezone.utc)
        )
        if updated == 0:
            raise ValueError(f"Task not found: {requestId}")
        return updated


class CacheResponseDb(Document):
    """RoutingTask model"""
    HashId = StringField(required=True)
    response = DictField(required=False)
    timestamp = DateTimeField(required=True, default=datetime.utcnow)
    error_list = ListField(StringField(), required=False)  # Adding a list field
    unassigned_message = StringField(required=False)

    meta = {
        "collection": "cache_response",
        "indexes": [
            {
                "fields": ["HashId"],
                "unique": True,
            }
        ],
    }

    def __str__(self):
        """String representation of the transformer task"""
        return f"HashId: {self.HashId}, response: {self.response}, timestamp: {self.timestamp}, error_list: {self.error_list}"

    class Config:
        """Pydantic config"""
        orm_mode = True


class CacheResponse:
    def insert_into_cache_table(self, hash_id, response, error_list,message):
        try:
            # Attempt to save the document
            cache_response = CacheResponseDb(
                HashId=hash_id,
                response=response,
                error_list=error_list if error_list else [],
                unassigned_message = message
            )
            cache_response.save()
            return {"status": "inserted", "document": cache_response}
        except NotUniqueError:
            # Fetch existing document if duplicate key
            logger.info('HashId already exists.')


    def get_cache_response_if_exist(self, hash_id):
        try:
            # Try to find the first document with the matching HashId in the CacheResponseDb collection
            existing_document = CacheResponseDb.objects(HashId=hash_id).first()
            if existing_document:
                return existing_document
            else:
                return None  # Or handle the case where no document is found
        except Exception as e:
            # Handle any exceptions that may occur
            return {"error": str(e)}


