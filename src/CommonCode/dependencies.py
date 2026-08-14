from fastapi import Request
from src.Mongo_Manager.db_repos.travel_data import TravelDataRepository
from src.Mongo_Manager.db_repos.routing_task import RoutingTaskRepository


def get_travel_data_repository(request: Request) -> TravelDataRepository:
    """Gets the travel data repository"""
    return TravelDataRepository()


def get_routing_task_repository(request: Request) -> RoutingTaskRepository:
    """Gets the transformer task repository"""
    return RoutingTaskRepository()
