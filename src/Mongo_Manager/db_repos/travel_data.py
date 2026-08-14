from pymongo import UpdateOne
from pymongo.errors import BulkWriteError
from mongoengine import Document, StringField, IntField, Q, DictField, BooleanField
from src.Utils.log import logger


# Normalized Travel Data Model
class TravelData(Document):
    """Travel Data model for normalized_travel_data"""

    origin = StringField(required=True)
    dest = StringField(required=True)
    distance = IntField(required=True)  # Distance in meters
    time = IntField(required=True)      # Time in minutes

    meta = {
        "collection": "norm_travel_data",
        "indexes": [
            {
                "fields": ["origin", "dest"],
                "unique": True,
            }
        ],
    }

    def __str__(self):
        """String representation of the travel data"""
        return f"origin: {self.origin}, dest: {self.dest}, distance: {self.distance}, time: {self.time}"


# Normalized Travel Data Repository
class TravelDataRepository:
    """Repository class for the normalized_travel_data collection"""

    def get_all_travel_data(self) -> list[TravelData]:
        """Gets all travel data using mongoengine"""
        return list(TravelData.objects)

    def insert_travel_data(self, travel_data: TravelData) -> TravelData:
        """Inserts the travel data into the database"""
        return travel_data.save()

    def batch_insert_travel_data(self, travel_data_list: list[TravelData]) -> dict | None:
        """Inserts the travel data into the database in bulk"""
        if not travel_data_list:
            return {"inserted_count": 0, "upserted_count": 0}

        try:
            updates = [
                UpdateOne(
                    {"origin": data.origin, "dest": data.dest},
                    {"$set": data.to_mongo()},
                    upsert=True,
                )
                for data in travel_data_list
            ]
            result = TravelData._get_collection().bulk_write(updates)
            return result.bulk_api_result
        except BulkWriteError as bwe:
            logger.error(f"Bulk write error: {bwe.details}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred during batch insert: {e}")

        return None

    def get_matching_travel_data(self, location_pairs: list[tuple[str, str]]) -> list[TravelData]:
        """Gets the travel data for the given location pairs"""
        query = Q()
        for origin, destination in location_pairs:
            query |= Q(origin=origin, dest=destination)

        return list(TravelData.objects(query))


# Flags Configuration Model
class Flags(Document):
    new_tech_time = DictField()
    new_work_orders_time = DictField()
    consider_lock_time = BooleanField()
    default_duration = DictField()
    consider_start_from_first_WO = BooleanField()
    workorders_daterange_is_optimization_daterange = BooleanField()
    consider_block_time = BooleanField()
    meta = {'collection': 'flags'}


def get_flags_details(field_name: str):
    """Retrieves a specific field value from the first Flags document"""
    flag_document = Flags.objects.first()
    if not flag_document:
        raise ValueError("No flag document found in the collection.")
    if field_name not in flag_document:
        raise KeyError(f"Field '{field_name}' not found in Flags document.")
    return flag_document[field_name]
