from mongoengine import Document, DateTimeField, FloatField, StringField,IntField, ListField
from datetime import date, timedelta
from src.Utils.config import GlobalConfig
from src.Utils.log import logger

class ApiData(Document):
    """API Data model"""
    request_id = StringField(required=True)
    date = DateTimeField(required=True)
    estimated_cost = FloatField(required=True)
    key = StringField(required=True)
    elements = FloatField(required=True)
    company_id = StringField(required=True)
    user_id = StringField(required=True)
    all_elements = FloatField(required=True)
    work_orders = IntField(default=0)
    technicians = ListField(default=[])
    object_id = StringField(required=True)

    meta = {
        "collection": "api_data",
        "indexes": [
            {
                "fields": ["date", "key"],
                "unique": True,
            }
        ],
    }

    def __str__(self):
        """String representation of the API data"""
        return f"""request_id:{self.request_id}, date: {self.date}, cost: {self.estimated_cost}, key: {self.key}, 
        elements: {self.elements}, company_id: {self.company_id}, user_id: {self.user_id}, 
        all_elements:{self.all_elements}, work_orders: {self.work_orders}, technicians: {self.technicians}, 
        object_id: {self.object_id}"""

    class Config:
        """Pydantic config"""
        orm_mode = True


class ApiDataManager:
    @classmethod
    def insert_or_update_api_data(cls, api_data: ApiData):
        """Inserts or updates a single API data record in the database"""
        update = {
            "date": api_data.date,
            "key": api_data.key
        }
        new_values = {
            "$set": {
                "request_id": api_data.request_id,
                "estimated_cost": api_data.estimated_cost,
                "elements": api_data.elements,
                "company_id": api_data.company_id,
                "user_id": api_data.user_id,
                "all_elements": api_data.all_elements,
                "object_id": api_data.object_id
            }
        }
        result = ApiData._get_collection().update_one(update, new_values, upsert=True)
        return result

    @classmethod
    def fetch_curr_day_elements(cls, remaining_elements):
        """Each api we can call 2500 elements adding additional api's will increase
        the number all elements in one day and one go."""
        keys = GlobalConfig.TEST_KEYS
        if not len(keys):
            raise Exception("Debug mode detected. Test keys must be provided.")
        # Get today's date and the next day's date
        today = date.today()
        next_day = today + timedelta(days=1)

        for api_key in keys:
            # Filtering with today's date and the next day's date
            filtered_records = ApiData.objects.filter(key=api_key, date__gte=today, date__lt=next_day)
            elements = 0
            for record in filtered_records:
                elements += int(record.elements)

            available_calls = 2500 - elements
            if remaining_elements < available_calls:
                break
        else:
            raise Exception("You've hit the daily limit for Google-API calls.")

        return api_key

    @classmethod
    def logs_update(cls, object_id, request):
        """Current request results"""
        filtered_records = ApiData.objects.filter(object_id=object_id)
        elements = 0
        estimated_cost = 0
        all_elements_dict = {}
        for ind, record in enumerate(filtered_records):
            if ind == 0:
                details = record
            elements += int(record.elements)
            estimated_cost += record.estimated_cost
            if record.object_id not in all_elements_dict:
                all_elements_dict.update({record.object_id: int(record.all_elements)})

        all_elements = sum(all_elements_dict.values())

        if not len(filtered_records):
            logger.info("In correct request id in API DATA in deletion and updation")
            return "In correct request id in API DATA in deletion and updation"
            # raise Exception("In correct request id in API DATA in deletion and updation")

        """Deletes all records with the given request_id from the database"""
        ApiData.objects(object_id=object_id).delete()
        update = {
            "date": details.date,
            "key": details.key
        }
        new_values = {
            "$set": {
                "request_id": details.request_id,
                "estimated_cost": estimated_cost,
                "elements": elements,
                "company_id": details.company_id,
                "user_id": details.user_id,
                "all_elements": all_elements,
                "work_orders": len(request.eventList),
                "technicians": [i.name for i in request.techniciansList],
                "object_id": object_id
            }
        }
        ApiData._get_collection().update_one(update, new_values, upsert=True)

    @classmethod
    def print_logs__(cls,request_id, request):
        filtered_records = ApiData.objects.filter(request_id=request_id)
        elements = 0
        estimated_cost = 0
        all_elements_dict = {}
        for ind, record in enumerate(filtered_records):
            if ind == 0:
                details = record
            elements += int(record.elements)
            estimated_cost += record.estimated_cost
            if record.object_id not in all_elements_dict:
                all_elements_dict.update({record.object_id: int(record.all_elements)})

        all_elements = sum(all_elements_dict.values())

        if not len(filtered_records):
            logger.info("In correct request id in API DATA in deletion and updation")
            return "In correct request id in API DATA in deletion and updation"
        logger.info(f"""
        Request_id: {details.request_id}
        TimeStamp: {details.date}
        Total work orders: {len(request.eventList)} 
        Total technicians: {len(request.techniciansList)} 
        All elements: {all_elements}
        Catched elements from DB: {all_elements - elements}
        Distance Matrix API called for: {elements} elements
        Estimated cost: {estimated_cost}
        User: {details.user_id}
        Customer: {details.company_id}
        """)
