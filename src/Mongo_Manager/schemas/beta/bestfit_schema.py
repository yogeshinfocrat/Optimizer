from enum import Enum
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict
from datetime import datetime, date

# Models for the request and response


# Enum Location of HOME or OFFICE
class LocationType(str, Enum):
    """Home or Office"""

    HOME = "Home"
    OFFICE = "Office"
    FIRST_JOB = "FirstJob"
    LAST_JOB = "LastJob"


class Location(BaseModel):
    """The location of a vehicle or employee"""

    type: LocationType
    """The type of location"""
    lat: float = Field(..., description="Latitude. For example: 47.6062095")
    """The latitude of the location"""
    lon: float = Field(..., description="Longitude. For example: -122.3320708")
    """The longitude of the location"""


class DayOfTheWeek(str, Enum):
    """The day of the week like monday, tuesday, etc."""

    Monday = "monday"
    Tuesday = "tuesday"
    Wednesday = "wednesday"
    Thursday = "thursday"
    Friday = "friday"
    Saturday = "saturday"
    Sunday = "sunday"


class DaySchedule(BaseModel):
    """The schedule for a day"""

    day: DayOfTheWeek
    """The day of the week"""
    inTime: str = Field(description="""The time the employee starts their day, ie startTime. Format HH:MM""")
    """The time the employee starts their day, ie startTime. Format HH:MM"""
    lastStartTime: str | None = Field(
        default=None,
        description="""The last time the employee can start a job. Format HH:MM.
        IGNORED: This field is not used in the current implementation.""",
    )
    """The last time the employee can start a job. Format HH:MM.
        IGNORED: This field is not used in the current implementation."""
    lastEndTime: str = Field(
        description="""The last time the employee can end a job.
        Note, this field is actually used as endTime, which means the
        technician must end the day at the office or home by this time. 
        format HH:MM"""
    )
    """The last time the employee can end a job.
        Note, this field is actually used as endTime, which means the
        technician must end the day at the office or home by this time. 
        format HH:MM"""
    earliestLunchTime: str = Field(description="The earliest time the employee can take a lunch. Format HH:MM")
    """The earliest time the employee can take a lunch. Format HH:MM"""
    latestLunchTime: str | None = Field(
        default=None,
        description="The latest time the employee can end their lunch. Format HH:MM",
    )
    """The latest time the employee can end their lunch. Format HH:MM"""
    lunchDuration: str = Field(description="The duration of the employee's lunch. Format: minutes")
    """The duration of the employee's lunch. Format: minutes"""
    maxServiceDuration: str = Field(description="The maximum duration of service for the employee. Format: minutes")
    """The maximum duration of service for the employee. Format: minutes"""
    maxTotalDayDuration: str = Field(
        description="""The maximum total duration of the employee's day.
        This includes drive time, service duration, and break times.
        Format: minutes"""
    )
    """The maximum total duration of the employee's day. 
    This includes drive time, service duration, and break times.
    Format: minutes"""
    maxDriveTime: str = Field(description="The maximum drive time for the employee. Format: minutes")
    """The maximum drive time for the employee. Format: minutes"""
    maxProductionValue: float = Field(description="The maximum production value for the employee")
    """The maximum production value for the employee"""
    maxNoOfJobs: int = Field(description="The maximum number of jobs the employee can do")
    """The maximum number of jobs the employee can do"""
    minNoOfJobs: int = Field(
        default=0,
        description="""The minimum number of jobs the employee can do.
        NOT IMPLEMENTED: Low priority.
        Note, there is a desire to use this field to more fairly distribute jobs,
        but using this field may not have the desired effect. Look more into
        creating a new field that changes the objective function or transformer strategy.""",
    )
    """
    The minimum number of jobs the employee can do.
    NOT IMPLEMENTED: Low priority.
    Note, there is a desire to use this field to more fairly distribute jobs,
    but using this field may not have the desired effect. Look more into
    creating a new field that changes the objective function or transformer strategy.
    """
    dayStartLocation: Location = Field(description="The location the employee starts the day")
    """The location the employee starts the day"""


class Skill(BaseModel):
    """A skill"""
    skillName: Optional[str] = Field(description="The name of the skill")
    proficiency: Optional[int] = Field(description="The proficiency level of the skill in ascending order")
    serviceSysName: Optional[str] = Field(description="The name of the skill")


# Enum DistanceCalculationType of EUCLIDEAN, GOOGLE, or MAP_BOX
class DistanceCalculationType(int, Enum):
    """The type of distance calculation to use.
    1 = EUCLIDEAN, 2 = GOOGLE. If GOOGLE, the apiKey must be provided."""

    EUCLIDEAN = 1
    GOOGLE = 2


class TimeRange(BaseModel):
    """A time range"""

    startTime: str
    """The start time of the range. Format HH:MM"""
    endTime: str
    """The end time of the range. Format HH:MM"""


class DateRange(BaseModel):
    """A date range"""

    startDate: str
    """The start date of the range. Format MM/DD/YYYY"""
    endDate: str
    """The end date of the range. Format MM/DD/YYYY"""

class BlockLocation(BaseModel):
    lat: Optional[float] = None
    lon: Optional[float] = None

class DateTimeRange(BaseModel):
    """A date and time range. Format MM/DD/YYYY H:MM"""
    startDateTime: str
    """The start date and time of the range. Format MM/DD/YYYY H:MM"""
    endDateTime: str
    """The end date and time of the range. Format MM/DD/YYYY H:MM"""
    blockLocation: BlockLocation = BlockLocation()


class Technician(BaseModel):
    id: str
    """The technician's id"""
    name: str | None = None
    """The technician's name"""
    isEmployeeGeoFencing: Optional[bool] = False
    """Consider Geo Fencing"""
    driving_mode: Optional[str] = "average"
    """technician driving mode"""
    variation_percent: Optional[float] = 0.0
    "percent of variation in speed"
    schedule: list[DaySchedule] = []
    """The technician's schedule"""
    leaves: list[DateRange] = []
    """The technician's holidays, full and sick leaves.
    These are full day leaves. Format: List of DateRange"""
    blockTimes: list[DateTimeRange] = []
    """The technician's block times. Format: List of DateTimeRange"""
    skills: list[Skill] = []
    """The technician's skills"""
    zip_codes: list[int] = []
    branch_ids: list[int] = []
    attribute: list[str] = []
    property_type: list[str] = []


class Constraints(BaseModel):
    timeRange: TimeRange = Field(
        description="""The time range.
        If the time range is not specified, the default is 12:00 AM to 11:59 PM."""
    )
    """The time range. 
    If the time range is not specified, the default is 12:00 AM to 11:59 PM."""
    dateRange: DateRange = Field(
        description="""The date range.
        If the date range is not specified, the default is the start and end dates of the transformer request."""
    )
    """The date range.
    If the date range is not specified, the default is the start and end dates of the transformer request."""
    excludedDateTimes: list[DateTimeRange] = Field(
        default=[],
        description="""The excluded date and time ranges. List of DateTimeRange""",
    )
    """The excluded date and time ranges. List of DateTimeRange"""
    userPreferredTechnicianId: str | None = Field(default=None, description="""The preferred technician's id.""")
    """The preferred technician's id."""
    userNonPreferredTechnicianIds: list[str] | None = Field(
        default=None, description="""The non-preferred technician's id."""
    )
    """The non-preferred technician's id."""
    inBoundEmployeeNo: list[int] | None = Field(
        default=None, description="""The is inBoundEmployeeNo."""
    )


class EligibleDate(BaseModel):
    from_date:int
    to_date: int


class Event(BaseModel):
    """An event"""

    eventId: str
    """The event's id"""
    name: str | None = None
    """The event's name"""
    eventType: str
    """The event's type"""
    accountNumber: str | None
    eventDate: str | None
    """If the event is already scheduled, the event's date. Format MM/DD/YYYY.
    NEEDS IMPLEMENTATION: This field is not currently used in the current implementation."""
    scheduleTime: str | None
    """If the event is already scheduled, the event's schedule time. Format H:MM.
    NEEDS IMPLEMENTATION: This field is not currently used in the current implementation."""
    lat: float
    """The event's latitude"""
    lon: float
    """The event's longitude"""
    lockTime: bool = False
    """Whether the event's eventDate and scheduleTime is locked. 
    EventDate and scheduleTime must not be null or empty if this is true.
    NEEDS IMPLEMENTATION: This field is not currently used in the current implementation."""
    lockTech: bool = False
    """Whether the event's technician is locked.
    userPreferredTechnicianId must not be null or empty if this is true.
    NEEDS IMPLEMENTATION: This field is not currently used in the current implementation."""
    productionValue: float
    """The event's production value"""
    duration: str
    """The event's duration. Format: minutes"""
    route: str | None = None
    """The event's route. This is a pass-through field that is not used by the API."""
    skills: list[Skill] = Field(
        default=[],
        description="The event's required skills. If more than 1 skill is set, then a technician must possess all of "
        "the skills to be assigned to this event.",
    )
    constraints: Constraints
    """The event's constraints"""
    eligible_days: Optional[List] | None = Field(default=None, description="Days eligible for the event")
    eligible_months: Optional[EligibleDate] | None = Field(default=None, description="Months eligible for the event")
    keepWithin: int | None = None
    """Keep the event within this many minutes of the last service date.
    NOT IMPLEMENTED: Requires more clarification. Should this be logic in the API client?
    The client could send the dates in the date range."""
    daysToFloat: int | None = None
    """The number of days to float the event based on the keepWithin field.
    NOT IMPLEMENTED: Requires more clarification. Should this be logic in the API client?
    The client could send the dates in the date range."""
    zip_code: int | None = None
    branch_id: int | None = None
    property_type: str | None= None
    attribute: list[str] = []



class DistanceCalculationSettings(BaseModel):
    """Settings for distance calculation"""

    distanceCalculationType: DistanceCalculationType = DistanceCalculationType.GOOGLE

    apiKey: Optional[str]  = Field(
        description="""The API key for the distance calculation service.
        Required if distanceCalculationType is not 1, ie EUCLIDEAN""",
    )


class RoutingRequest(BaseModel):
    techniciansList: list[Technician]
    """The list of technicians"""
    eventList: list[Event]
    """The list of events"""
    distanceCalculationType: DistanceCalculationType | None = Field(
        default=None,
        deprecated=True,
        description="Deprecated. Use distanceCalculationSettings instead.",
    )
    """The distance calculation type"""
    distanceCalculationSettings: DistanceCalculationSettings
    """The distance calculation settings"""
    optimizeDatesRange: DateRange
    """The date range to optimize"""
    considerSkill: bool = False
    """Whether to consider skills.
    NOT IMPLEMENTED: Low priority. Waiting on customer feedback."""
    considerDriveTime: bool = False
    """Whether to optimize drive time.
    NOT IMPLEMENTED: Low priority. Waiting on customer feedback.
    Note, the name of this field is not obvious. The input to change
    the transformer strategy should be thought out more."""
    timeToLeaveOpen: int = 0
    """The time to leave open. Format: minutes. This is the amount of time to add
    as a break for all technicians per day. It can be taken anytime during the technician's
    day. The purpose is to leave time for unspecified events.
    NEEDS IMPLEMENTATION: This field is not currently used in the current implementation."""
    allowStartDate: str | None = None
    """The date to allow start. Format MM/DD/YYYY.
    NOT IMPLEMENTED: Doesn't exist in the UI. Will be deprecated."""
    allowEndDate: str | None = None
    """The date to allow end. Format MM/DD/YYYY.
    NOT IMPLEMENTED: Doesn't exist in the UI. Will be deprecated."""
    keepWorkDate: bool = False
    keepWorkTech: bool = False
    minServiceDuration: str
    """The minimum service duration. Format: minutes"""
    minProductionValue: Optional[int] = 0
    forceRoutesToStartAtBeginning: bool = False
    """Whether to force routes to start at the beginning.
    NOT IMPLEMENTED: Low priority. Waiting on customer feedback."""
    clientID: str | None
    userID: str | None
    isBestFit: bool = False
    woValidationReq: bool=False
    isGeoFenced: bool = False


class EventRouteDistance(BaseModel):
    id: str
    """The id for the event route distance"""
    from_field: Optional[str] = None #= Field(alias="from")  # from is a reserved word
    """The from location"""
    to: str | None
    """The to location"""
    fromLocation: str
    """The from location"""
    toLocation: str
    """The to location"""
    driveTime: int
    """The drive time. Format: minutes"""
    distance: int
    """The distance. Format: meters"""


class AssignedEvent(BaseModel):
    """An assigned event"""

    route: str | None = Field(description="""The event's route id""")
    skills: list[Skill] = Field(default=[], description="""The skills required for the event""")
    eventId: str = Field(
        description="""The event's id. 
    If the event is a lunch event, starts with lt, 
    if this is an office event, starts with ev, 
    if this is a work order event, no prefix. 
    6 digit number following prefix if any"""
    )
    eventName: str | None = Field(description="The event's name")
    """The event's name"""
    eventDate: str = Field(description="The event's date. Format MM/DD/YYYY")
    """The event's date. Format MM/DD/YYYY"""
    scheduleTime: str = Field(description="The event's schedule time. Format HH:MM")
    """The event's schedule time. Format HH:MM"""
    duration: Optional[str] = None
    eventType: str = Field(description="The event's type")
    """The event's type."""
    productionValue: float | None = Field(description="The event's production value")
    """The event's production value"""
    eventRouteDistance: Optional[EventRouteDistance] = None # Field(description="The event's route distance")
    """The event's route distance"""
    eventRoutDistance: Optional[EventRouteDistance] = None #= Field(description="The event's route distance")
    """Same as eventRouteDistance, but spelled wrong."""
    eventDay: str | None = Field(description="The event's day")
    """The event's day"""
    technicianId: str | None = Field(description="The event's technician id")
    """The event's technician id"""
    lat: float | None = Field(description="The event's latitude")
    """The event's latitude"""
    lon: float | None = Field(description="The event's longitude")
    """The event's longitude"""


class TechnicianRoute(BaseModel):
    technicianId: str
    """The technician's id"""
    date: str
    """The technician's date. Format MM/DD/YYYY"""
    dayOfTheWeek: DayOfTheWeek
    """The technician's day"""
    startTime: str
    """The technician's start time. Format HH:MM"""
    endTime: str
    """The technician's end time. Format HH:MM"""
    dailyDriveTime: int = 0
    """The technician's daily drive time. Format: minutes"""
    dailyDistance: int = 0
    """The technician's daily distance. Format: meters"""
    dailyProductionValue: float = 0
    """The technician's daily production value"""
    dailyNoOfJobs: int = 0
    """The technician's daily number of jobs"""
    dailyServiceDuration: int = 0
    """The technician's daily service duration. Format: minutes"""
    assignedEventList: list[AssignedEvent]
    """The list of assigned events"""


class TechnicianInfo(BaseModel):
    technicianId: str
    """The technician's id"""
    totalDriveTime: int = 0
    """The technician's total drive time. Format: minutes"""
    totalDistance: int = 0
    """The technician's total distance. Format: meters"""
    totalProductionValue: float = 0
    """The technician's total production value"""
    totalNoOfJobs: int = 0
    """The technician's total number of jobs"""
    totalServiceDuration: int = 0
    """The technician's total service duration. Format: minutes"""
    routes: list[TechnicianRoute]
    """The list of technician routes"""


class RoutingResponse(BaseModel):
    assignedEventList: list[AssignedEvent]
    """The list of assigned events"""
    unassignedEventList: list[Event]
    """The list of unassigned events"""
    technicianInfoList: list[TechnicianInfo]


class BestFitResponse(BaseModel):
    assignedEventList: list[AssignedEvent]
    """The list of assigned events"""
    unassignedEventList: list[Event]
    """The list of unassigned events"""
    technicianInfoList: list[TechnicianInfo]
    """
    The technician info. 
    This similar data to assignedEventList, but grouped by technician.
    """
    status: str
    """status contain the status or OR tool"""
    message: str
    """In case of fail what message should be displayed"""
    unassigned_message: Optional[str] = None



class BetaBestFitResponse(BaseModel):
    assignedEventList: list[AssignedEvent]
    """The list of assigned events"""
    unassignedEventList: list[Event]
    """The list of unassigned events"""
    status: str
    """status contain the status or OR tool"""
    message: str
    """In case of fail what message should be displayed"""
    unassigned_message: Optional[str] = None
    completion_time: Optional[int]= None

class HistoryItem(BaseModel):
    id: str
    """The id for the history item"""
    request: RoutingRequest
    """The transformer request"""
    response: RoutingResponse | None
    """The transformer response"""
    timestamp: str
    """The timestamp. Format: MM/DD/YYYY HH:MM:SS"""


class HistoryResponse(BaseModel):
    historyItems: list[HistoryItem]
    """The list of history items"""


class ConfigDetails(BaseModel):
    Common_CompId: int = 0
    CRM_CompId: int = 0
    HRMS_CompId: int = 0
    ConsiderSkillInRouteOptimization: Optional[bool] = False
    IsRouteOptimizationEnabled: Optional[bool] = True
    IsEnableRoGeofencing: Optional[bool] = False
    considerDriveTime: Optional[bool] = False
    api_key: str
    considerZipCode : Optional[bool] = False
    considerBranch: Optional[bool] = False
    IsPropertyTypeInRO: Optional[bool] = False


DATE_FORMAT = "%m/%d/%Y"


class BestFitRequest(BaseModel):
    EmployeeNos: Optional[List[str]] = Field(default_factory=list)
    BranchSysName: Optional[str] = ''
    DepartmentSysName: Optional[str] = ''
    DateRange: Optional[int] = 0
    StartDate: Optional[date] = Field(default_factory=date.today)
    WoDetail: Optional[Dict] = Field(default_factory=dict)
    CompanyKey: Optional[str] = 'Fortive'
    User:Optional[str] = 'Yogesh'
    EmployeeId:int

    @field_validator("StartDate", mode="before")
    def parse_start_date(cls, value):
        if isinstance(value, str):
            return datetime.strptime(value, DATE_FORMAT).date()
        return value
