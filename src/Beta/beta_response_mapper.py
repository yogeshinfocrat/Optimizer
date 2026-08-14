import random
from typing import Dict
from src.Mongo_Manager.schemas.beta.bestfit_schema import (
    AssignedEvent,
    Event,
    EventRouteDistance,
    RoutingRequest,
    RoutingResponse,
    TechnicianInfo,
    TechnicianRoute,
    Constraints, TimeRange, DateRange
)
import pandas as pd
from src.Mongo_Manager.schemas.beta.internal_schema import (
    Break,
    Data,
    Node,
    NodeType,
    NodeVisit,
    RoutingResponse as OldRoutingResponse,
)
from src.Beta.beta_routing_utils import get_schedule
from src.Utils.date_utils import (
    get_date_and_time_from_minutes,
    get_minutes_from_string,
)


def create_id(prefix: str = "") -> str:
    """Creates a unique id"""
    return f"{prefix}{str(random.randint(100000, 999999))}"


def convert_assigned_work_order(
        visit: NodeVisit,
        wo_df_indexed,
        technician_id: str,
        previous_event_id: str,
        date_range
) -> AssignedEvent:
    """Converts the node to an assigned event"""
    node = visit.node
    node_id = int(node.id)
    try:
        event = wo_df_indexed.loc[node_id]
    except KeyError:
        raise ValueError(f"Event with id {node.id} not found")

    startDate = date_range[0]
    event_date, schedule_time, day = get_date_and_time_from_minutes(
        visit.start_time, startDate
    )
    # log_info(f"id: {event.eventId}, event_date: {event_date}, schedule_time: {schedule_time}")
    # log_info(f"visit start time: {visit.start_time}, start date: {request.optimizeDatesRange.startDate}")

    event_route_distance = {
        "id": create_id("rp"),
        "from": previous_event_id,
        "to": str(event.name),
        "fromLocation": previous_event_id,
        "toLocation": str(event.name),
        "driveTime": visit.travel_time,
        "distance": visit.distance,
    }

    assign_eve = AssignedEvent(
        route=str(event.get('routenotusing')),
        skills=[],
        eventId=str(event.name),
        eventName=event.get('name'),
        eventDate=event_date,
        scheduleTime=schedule_time,
        duration=str(node.minimum_duration),
        eventType=event.get('eventType'),
        productionValue=event.get('ProductionAmount'),
        eventDay=day,
        technicianId=technician_id,
        lat=node.latitude,
        lon=node.longitude,
        eventRouteDistance=EventRouteDistance(
            **event_route_distance,
        ),
        eventRoutDistance=EventRouteDistance(
            **event_route_distance,
        ),
    )
    return assign_eve


def convert_assigned_home_or_office(visit, tech_df, date_rang) -> AssignedEvent:
    """Converts the node to an assigned event"""
    node = visit.node
    # Find the technician in the request
    technician = next(
        (t for t in tech_df['EmployeeNo'].unique() if t == node.id),
        None,
    )
    if technician is None:
        raise ValueError(f"Technician with id {node.id} not found in request")

    event_date, schedule_time, day = get_date_and_time_from_minutes(
        visit.start_time, date_rang[0]
    )
    schedule, tech_details = get_schedule(tech_df[tech_df['EmployeeNo'] == technician], day)
    locationType = schedule.dayStartLocation.type

    # log_info(f"[response mapping] technician id: {technician.id} - {technician.name}")

    return AssignedEvent(
        route=None,
        skills=[],
        eventId=create_id("ev"),
        eventName=tech_details.get('name'),
        eventDate=event_date,
        scheduleTime=schedule_time,
        duration=str(node.minimum_duration),
        eventType=locationType._value_,
        productionValue=None,
        eventDay=day,
        technicianId= str(tech_details.get('EmployeeId')),
        lat=node.latitude,
        lon=node.longitude,
        eventRouteDistance=None,
        eventRoutDistance=None,
    )


def preprocess_wo_df(wo_df: pd.DataFrame, date_range) -> pd.DataFrame:
    print("ProcessingDF")
    wo_df = wo_df.copy()

    # # -----------------------------
    # # Convert DATE columns
    # # -----------------------------
    # wo_df["eventDate"] = pd.to_datetime(wo_df["eventDate"], errors="coerce")
    # wo_df["EarliestServiceDate"] = pd.to_datetime(wo_df["EarliestServiceDate"], errors="coerce")
    # wo_df["LatestServiceDate"] = pd.to_datetime(wo_df["LatestServiceDate"], errors="coerce")
    #
    # # -----------------------------
    # # Convert TIME columns
    # # -----------------------------
    # # wo_df["ScheduleTime"] = pd.to_datetime(wo_df["ScheduleTime"], errors="coerce").dt.time
    # wo_df["ServiceStartStartTime"] = pd.to_datetime(wo_df["ServiceStartStartTime"], errors="coerce").dt.time
    # wo_df["ServiceStartEndTime"] = pd.to_datetime(wo_df["ServiceStartEndTime"], errors="coerce").dt.time

    # -----------------------------
    # Defaults (NO re-conversion)
    # -----------------------------
    default_start_time = pd.to_datetime("00:00").time()
    default_end_time = pd.to_datetime("23:59").time()

    default_start_date = date_range[0]  # already Timestamp
    default_end_date = date_range[-1]

    # -----------------------------
    # Fill missing values
    # -----------------------------
    wo_df["ServiceStartStartTime"] = wo_df["ServiceStartStartTime"].fillna(default_start_time)
    wo_df["ServiceStartEndTime"] = wo_df["ServiceStartEndTime"].fillna(default_end_time)

    wo_df["EarliestServiceDate"] = wo_df["EarliestServiceDate"].fillna(default_start_date)
    wo_df["LatestServiceDate"] = wo_df["LatestServiceDate"].fillna(default_end_date)

    # -----------------------------
    # Index for fast lookup
    # -----------------------------
    wo_df = wo_df.set_index("eventId")

    return wo_df


# ==============================
# HELPERS
# ==============================

def format_date(dt):
    if pd.isna(dt) or dt is None:
        return None
    return dt.strftime("%m/%d/%Y")


def format_time(t):
    if pd.isna(t) or t is None:
        return None
    try:
        return t.strftime("%H:%M")
    except:
        return None

# ==============================
# CONSTRAINT BUILDER
# ==============================
def build_constraints(row) -> Constraints:
    # TIME RANGE
    start_time = row.get("ServiceStartStartTime")
    end_time = row.get("ServiceStartEndTime")

    time_range = TimeRange(
        startTime=format_time(start_time) if start_time else "00:00",
        endTime=format_time(end_time) if end_time else "23:59",
    )

    # DATE RANGE
    event_date = row.get("eventDate")

    date_range = DateRange(
        startDate=format_date(event_date),
        endDate=format_date(event_date),
    )

    return Constraints(
        timeRange=time_range,
        dateRange=date_range,
        excludedDateTimes=[],  # Extend if needed
        userPreferredTechnicianId=row.get("userPreferredTechnicianId"),
        userNonPreferredTechnicianIds=row.get("nonPreferredTechs"),
        inBoundEmployeeNo=row.get("inBoundEmployeeNo"),
    )


# ==============================
# CORE FUNCTION
# ==============================

def convert_node_to_event(node: Node, wo_df_indexed: pd.DataFrame) -> Event:
    try:
        if node.id =="0":
            try:
                row = wo_df_indexed.loc[
                    (
                            (wo_df_indexed['eventDate'] == pd.to_datetime(node.start_date_range))
                            &
                            (wo_df_indexed['userPreferredTechnicianId'] == node.allowed_vehicle_ids[0])
                    )
                ].loc[int(node.id)]
            except Exception as e:
                row = wo_df_indexed.loc[
                            wo_df_indexed['eventDate'] == pd.to_datetime(node.start_date_range)
                ].loc[int(node.id)]

        else:
            row = wo_df_indexed.loc[int(node.id)]
    except KeyError:
        raise ValueError(f"Event with id {node.id} not found")

    return Event(
        eventId=str(row.name),
        name=row.get("name"),
        eventType=row.get("eventType"),
        accountNumber=row.get("AccountNumber"),

        eventDate=format_date(row.get("eventDate")),
        scheduleTime=format_time(row.get("ScheduleTime")),

        lat=row.get("lat"),
        lon=row.get("lng"),

        lockTime=bool(row.get("lockTime", False)),
        lockTech=bool(row.get("lockTech", False)),

        productionValue=float(row.get("ProductionAmount", 0)),
        duration=str(int(row.get("TotalEstimationTime", 0))),

        route=row.get("route"),

        skills=[],  # Extend if needed

        constraints=build_constraints(row),

        eligible_days=row.get("eligible_days"),
        eligible_months=row.get("eligible_months"),

        keepWithin=row.get("keepWithin"),
        daysToFloat=row.get("daysToFloat"),
    )


def convert_assigned_breaks(the_break: Break, technicianId: str, break_type, date_range) -> AssignedEvent:
    """Converts the break to an assigned event"""
    # Find the technician in the request
    # technician = next(
    #     (t for t in request.techniciansList if t.id == technicianId),
    #     None,
    # )
    # if technician is None:
    #     raise ValueError(f"Technician with id {technicianId} not found in request")

    event_date, schedule_time, day = get_date_and_time_from_minutes(
        the_break.start_time, date_range[0]
    )
    if break_type == 'lunchEvent':
        return AssignedEvent(
            route=None,
            skills=[],
            eventId=create_id("lt"),
            eventName="Lunch",
            eventDate=event_date,
            scheduleTime=schedule_time,
            duration=str(the_break.duration),
            eventType="lunchEvent",
            productionValue=None,
            eventDay=day,
            technicianId=technicianId,
            lat=0.0,
            lon=0.0,
            eventRouteDistance=None,
            eventRoutDistance=None,
        )
    elif break_type == 'BlockTime':
        return AssignedEvent(
            route=None,
            skills=[],
            eventId=create_id("lt"),
            eventName="BlockTime-Meeting",
            eventDate=event_date,
            scheduleTime=schedule_time,
            duration=str(the_break.duration),
            eventType=break_type,
            productionValue=None,
            eventDay=day,
            technicianId=technicianId,
            lat=0.0,
            lon=0.0,
            eventRouteDistance=None,
            eventRoutDistance=None,
        )
    elif break_type == 'TimeToLeaveOpenPerDay':
        return AssignedEvent(
            route=None,
            skills=[],
            eventId=create_id("lt"),
            eventName="TimeToLeaveOpenPerDay",
            eventDate=event_date,
            scheduleTime=schedule_time,
            duration=str(the_break.duration),
            eventType=break_type,
            productionValue=None,
            eventDay=day,
            technicianId=technicianId,
            lat=0.0,
            lon=0.0,
            eventRouteDistance=None,
            eventRoutDistance=None,
        )


def create_technician_route(technician_id: str, assigned_events: list[AssignedEvent]) -> TechnicianRoute | None:
    """Creates a technician route"""
    if len(assigned_events) == 0:
        return None

    # Sum up values if the event type is work order
    dailyDriveTime = 0
    dailyDistance = 0
    dailyNoOfJobs = 0
    dailyProductionValue = 0
    for assigned_event in assigned_events:
        if assigned_event.eventType not in ["Office", "Home", "lunchEvent", "LastJob", "FirstJob", "BlockTime",
                                            "TimeToLeaveOpenPerDay"]:
            dailyDriveTime += int(assigned_event.eventRouteDistance.driveTime)
            dailyDistance += int(assigned_event.eventRouteDistance.distance)
            dailyNoOfJobs += 1
            dailyProductionValue += int(assigned_event.productionValue)

    # Find the first occurring event based on schedule time
    assigned_events.sort(key=lambda x: x.scheduleTime)
    daily_service_duration = 0

    start_time = assigned_events[0].scheduleTime
    end_time = assigned_events[-1].scheduleTime
    daily_service_duration = get_minutes_from_string(end_time) - get_minutes_from_string(start_time)

    # What does list[-1] do?
    # https://stackoverflow.com/questions/509211/understanding-slice-notation

    return TechnicianRoute(
        technicianId=technician_id,
        assignedEventList=assigned_events,
        date=assigned_events[0].eventDate,
        dayOfTheWeek=assigned_events[0].eventDay,
        startTime=start_time,
        endTime=end_time,
        dailyDriveTime=dailyDriveTime,
        dailyDistance=dailyDistance,
        dailyNoOfJobs=dailyNoOfJobs,
        dailyProductionValue=dailyProductionValue,
        dailyServiceDuration=daily_service_duration,
    )


def create_technician_info(technician_id: str, technician_routes: list[TechnicianRoute]) -> TechnicianInfo:
    """Creates a technician info"""

    total_distance = 0
    total_drive_time = 0
    total_no_of_jobs = 0
    total_production_value = 0
    total_service_duration = 0
    for technician_route in technician_routes:
        total_distance += int(technician_route.dailyDistance)
        total_drive_time += int(technician_route.dailyDriveTime)
        total_no_of_jobs += technician_route.dailyNoOfJobs
        total_production_value += int(technician_route.dailyProductionValue)
        total_service_duration += int(technician_route.dailyServiceDuration)

    return TechnicianInfo(
        technicianId=technician_id,
        routes=technician_routes,
        totalDistance=total_distance,
        totalDriveTime=total_drive_time,
        totalNoOfJobs=total_no_of_jobs,
        totalProductionValue=total_production_value,
        totalServiceDuration=total_service_duration,
    )


def convert_response(temp_response, dataSchema, work_order_details, tech_df, skills_df,
                     block_time, date_range, req, config) -> RoutingResponse:
    """Converts the old transformer response to the new transformer response"""
    routes = temp_response.routes
    missed = temp_response.missed_stops
    wo_df_indexed = preprocess_wo_df(work_order_details, date_range)
    # convert the routes to assigned events
    assigned_events: list[AssignedEvent] = []
    technician_route_map: Dict[str, list[TechnicianRoute]] = {}
    previous_event_id = None
    for route in routes:
        technician_id = route.vehicle.id
        route_events: list[AssignedEvent] = []
        for visit in route.visits:
            if visit.node.node_type != NodeType.STOP:
                event = convert_assigned_home_or_office(visit, tech_df, date_range)
            else:
                event = convert_assigned_work_order(visit, wo_df_indexed, technician_id, previous_event_id, date_range)
            previous_event_id = event.eventId
            route_events.append(event)

        counter = 0
        for break_ in route.breaks:
            event = convert_assigned_breaks(break_, technician_id, break_.type,date_range)
            route_events.append(event)
            counter += 1

        assigned_events.extend(route_events)

        # Add the technician info
        technician_route = create_technician_route(technician_id, route_events)
        if technician_route is not None:
            if technician_id in technician_route_map:
                technician_route_map[technician_id].append(technician_route)
            else:
                technician_route_map[technician_id] = [technician_route]

    # convert the missed stops to unassigned events
    unassigned_events = [convert_node_to_event(node, wo_df_indexed) for node in missed]

    # Create list of technician info
    technician_info_list: list[TechnicianInfo] = []
    # For each technician in technician_route_map, create a technician info
    for technician_id, technician_routes in technician_route_map.items():
        technician_info = create_technician_info(technician_id, technician_routes)
        technician_info_list.append(technician_info)

    return RoutingResponse(
        assignedEventList=assigned_events,
        unassignedEventList=unassigned_events,
        technicianInfoList=technician_info_list
    )
