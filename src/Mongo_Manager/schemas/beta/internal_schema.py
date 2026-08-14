from datetime import datetime
from enum import Enum
from pydantic import BaseModel
from typing import Optional

MINUTES_PER_DAY = 1440


# Enum NodeType of HOME, OFFICE, or STOP
class NodeType(Enum):
    HOME = "HOME"
    OFFICE = "OFFICE"
    STOP = "STOP"
    FIRST_JOB = "FIRST_JOB"
    LAST_JOB = "LAST_JOB"

class Break(BaseModel):
    """The break for a vehicle"""
    start_time: int
    """The break's start time in minutes from midnight"""
    end_time: int
    """The break's end time in minutes from midnight"""
    duration: int
    """The break's duration in minutes"""
    type: Optional[str] = None
    """The type of break (optional)"""


class Vehicle(BaseModel):
    id: str
    name: str | None = None
    isEmployeeGeoFencing: Optional[bool] = False
    start_time: int
    """The vehicle's start time in minutes from midnight"""
    last_start_time:int
    "The vehicle's should start max by this time in minutes from midnight"
    speed_factor: float
    end_time: int
    """The vehicle's end time in minutes from midnight"""
    max_number_of_stops: int
    """The maximum number of stops the vehicle can make"""
    max_travel_time: int
    """The maximum travel time the vehicle can make"""
    max_drive_time: int
    """The maximum drive time the vehicle can make"""
    max_service_duration: int
    """The maximum service duration the vehicle can make"""
    max_production_value: int
    """The maximum production value the vehicle can make"""
    min_production_value: int
    """The minimum production value the vehicle can make"""
    node_type: NodeType
    """The vehicle's node type"""
    latitude: float
    """The vehicle's latitude"""
    longitude: float
    """The vehicle's longitude"""
    address: str
    """The vehicle's address"""
    breaks: list[Break] = []
    """The vehicle's breaks"""


class DateTimes(BaseModel):
    """Time range with datetime objects"""
    start_date_time: datetime
    """The start date time"""
    end_date_time: datetime
    """The end date time"""


class Node(BaseModel):
    id: str
    """The node's id"""
    node_type: NodeType
    """The node's type"""
    accountNumber: Optional[str] = None
    name: str
    """The node's name"""
    start_date_range: Optional[datetime] = None
    """The start date of the range available for the visit"""
    end_date_range: Optional[datetime] = None
    """The end date of the range available for the visit"""
    start_time: int
    """The node's start time window in minutes from midnight"""
    end_time: int
    """The node's end time window in minutes from midnight"""
    penalty: int
    """The node's penalty if dropped"""
    production_value: int
    """The node's production value"""
    latitude: float
    """The node's latitude"""
    longitude: float
    """The node's longitude"""
    address: str
    """The node's address"""
    minimum_duration: int = 0
    """The minimum duration of the node in minutes"""
    allowed_vehicle_ids: list[str] = []
    """The allowed vehicle ids for the node"""
    excluded_date_times: list[DateTimes] = []
    """The excluded date times for the node"""
    allowed_dates: Optional[list] = None
    """Preferred vehicle indexes"""
    preferred_vehicle_ids: Optional[list] = None


class RoutingOptions(BaseModel):
    """The options for the transformer endpoint"""


class RoutingRequest(BaseModel):
    """The request body for the transformer endpoint"""

    start_date: str
    """The start date of the route as a string in the ISO 8601 format"""
    end_date: str
    """The end date of the route as a string in the ISO 8601 format"""
    vehicles: list[Vehicle]
    """The vehicles or employees"""
    stops: list[Node]
    """The stops or jobs"""
    options: RoutingOptions = RoutingOptions()
    """The options for the transformer"""


class NodeVisit(BaseModel):
    """The visit of a node"""
    node: Node
    """The node being visited"""
    start_time: int
    """The start time of the visit"""
    end_time: int
    """The end time of the visit"""
    distance: int = 0
    """The distance in meters from the previous node"""
    travel_time: int = 0
    """The travel time in minutes from the previous node"""


class Route(BaseModel):
    """The route for a vehicle"""
    vehicle: Vehicle
    visits: list[NodeVisit]
    breaks: list[Break] = []


class ExecutionTimeKey(str, Enum):
    START = "executionStartTime"
    END = "executionEndTime"
    EXECUTION_TIME = "executionTime"
    MATRIX_START = "matrixStartTime"
    MATRIX_END = "matrixEndTime"
    MATRIX_EXECUTION_TIME = "matrixExecutionTime"


class ExecutionInfo(BaseModel):
    """The execution info"""
    executionTimes: dict[ExecutionTimeKey, int] = {}
    """The execution times in milliseconds for each step"""
    executionConfigs: dict[str, str] = {}
    """The execution configs from the execution"""
    notes: dict[str, str] = {}
    """The notes from the execution"""


class RoutingResponse(BaseModel):
    """The response body for the transformer endpoint"""

    routes: list[Route]
    missed_stops: list[Node]


class Data(BaseModel):
    date_range: list[datetime]
    """List of dates to optimize over"""
    number_of_days: int
    """The number of days in the route"""
    vehicles: list[Vehicle]
    """The vehicles or technicians"""
    stops: list[Node]
    """The stops or jobs"""
    nodes: list[Node]
    """Each vehicle and stop as a node"""
    start_indexes: list[int]
    """The node index where each vehicle starts"""
    end_indexes: list[int]
    """The node index where each vehicle ends"""
    depot: int = 0
    """The depot node index"""

    def get_time_windows_for_nodes(self):
        """Returns the time windows for all nodes"""
        return [[node.start_time, node.end_time] for node in self.nodes]

    def get_end_times_for_vehicles(self):
        """Returns the end times for all vehicles"""
        return [vehicle.end_time for vehicle in self.vehicles]

    def get_max_stops_for_vehicles(self):
        """Returns the maximum number of stops for all vehicles"""
        return [vehicle.max_number_of_stops for vehicle in self.vehicles]

    def get_max_travel_time_for_vehicles(self):
        """Returns the maximum travel time for all vehicles, which includes drive time and service time"""
        return [vehicle.max_travel_time for vehicle in self.vehicles]

    def get_max_drive_time_for_vehicles(self):
        """Returns the maximum drive time for all vehicles"""
        return [vehicle.max_drive_time for vehicle in self.vehicles]

    def get_max_service_duration_for_vehicles(self):
        """Returns the maximum service duration for all vehicles"""
        return [vehicle.max_service_duration for vehicle in self.vehicles]

    def get_max_production_value_for_vehicles(self):
        """Returns the maximum production value for all vehicles"""
        return [vehicle.max_production_value for vehicle in self.vehicles]
