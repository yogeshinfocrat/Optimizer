from math import radians, sin, cos, sqrt, asin
from ortools.constraint_solver import pywrapcp
from src.Mongo_Manager.db_repos.travel_data import TravelData
from src.Mongo_Manager.schemas.beta.internal_schema import (
    Break,
    Data,
    Node,
    NodeVisit,
    Route,
    RoutingResponse,
)
from src.Mongo_Manager.schemas.beta.bestfit_schema import DayOfTheWeek, DaySchedule, Technician, Location, LocationType
from datetime import time
import pandas as pd
# from src.utils.logger import log_debug, log_info


def empty_routing_response(data: Data):
    """Create an empty transformer response"""
    routes = []
    for vehicle in data.vehicles:
        routes.append(Route(vehicle=vehicle, visits=[]))
    return RoutingResponse(routes=routes, missed_stops=data.stops)


def get_routing_response(
    data: Data,
    travel_matrix: list[list[TravelData]],
    manager: pywrapcp.RoutingIndexManager,
    routing: pywrapcp.RoutingModel,
    solution: pywrapcp.Assignment,
    break_intervals: list[list[pywrapcp.IntervalVar]] | None
):
    """Get the transformer response from the solution"""
    # log_info("get_routing_response")
    # # Print the travel matrix times
    # for row in travel_matrix:
    #     for travel_data in row:
    #         if travel_data is not None:
    #             log_debug(f"{travel_data.time}", end=" ")
    #         else:
    #             log_debug("None", end=" ")
    #     log_debug("")
    travel_dimension: pywrapcp.RoutingDimension = routing.GetDimensionOrDie("Travel")
    drive_time_dimension: pywrapcp.RoutingDimension = routing.GetDimensionOrDie("DriveTime")
    day_duration_dimension: pywrapcp.RoutingDimension = routing.GetDimensionOrDie("DayDuration")

    def create_node_visit(index: int, prev_index: int | None):
        node_index = manager.IndexToNode(index)
        node: Node = data.nodes[node_index]

        travel_var = travel_dimension.CumulVar(index)
        drive_var = drive_time_dimension.CumulVar(index)
        day_var = day_duration_dimension.CumulVar(index)

        start = solution.Min(travel_var)
        end = start + node.minimum_duration

        if prev_index is None:
            return NodeVisit(
                node=node,
                start_time=start,
                end_time=end,
                travel_time=0,
                distance=0,
                drive_time=0
            )
        else:
            prev_node_index = manager.IndexToNode(prev_index)

            # --- IMPORTANT PART ---
            # actual drive time for this specific vehicle
            prev_drive = solution.Min(drive_time_dimension.CumulVar(prev_index))
            curr_drive = solution.Min(drive_var)
            actual_drive_time = curr_drive - prev_drive

            # If using different travel matrices per vehicle
            travel_data = travel_matrix[prev_node_index][node_index]

            return NodeVisit(
                node=node,
                start_time=start,
                end_time=end,
                travel_time=actual_drive_time,
                distance=travel_data.distance,
                drive_time=actual_drive_time,
            )

    # print the name and index of all data.nodes
    # for node_idx, node in enumerate(data.nodes):
    #     log_info(f"{node.name}: {manager.NodeToIndex(node_idx)}")

    # create the routes
    routes = []
    node_indexes_visited = []
    for vehicle_id in range(len(data.vehicles)):
        prev_index = None
        index = routing.Start(vehicle_id)
        vehicle = data.vehicles[vehicle_id]
        visits = []
        while not routing.IsEnd(index):
            # add the node to the list of visited nodes
            node_indexes_visited.append(manager.IndexToNode(index))

            # add the node visit
            visits.append(create_node_visit(index, prev_index))
            prev_index = index
            index = solution.Value(routing.NextVar(index))

        # add the last node
        visits.append(create_node_visit(index, prev_index))

        # add the break intervals
        # log_info("Breaks")

        breaks: list[Break] = []

        if break_intervals and break_intervals.__len__() > 0:
            intervals = break_intervals[vehicle_id]
            for interval in intervals:
                if interval.Name().split()[-1] =='LunchBreak':
                    BreakType = 'lunchEvent'
                elif interval.Name().split()[-1] == 'BlockTimeBreak':
                    BreakType = 'BlockTime'
                elif interval.Name().split()[-1] == 'TimeToLeaveOpenPerDay':
                    BreakType = 'TimeToLeaveOpenPerDay'
                break_value = Break(
                    start_time=solution.StartValue(interval),
                    end_time=solution.EndValue(interval),
                    duration=solution.DurationValue(interval),
                    type = BreakType
                )
                # log_info(f"Break: {break_value}")
                breaks.append(break_value)

        # add the route
        routes.append(Route(vehicle=vehicle, visits=visits, breaks=breaks))

    # Get the missed nodes from the solution
    missed_nodes: list[Node] = []
    for node_idx, node in enumerate(data.nodes):
        if node_idx not in node_indexes_visited:
            missed_nodes.append(node)

    # return the transformer response
    return RoutingResponse(routes=routes, missed_stops=missed_nodes)


def clean(val):
    return None if pd.isna(val) else val


# HH:MM format
def to_time_str(val):
    val = clean(val)
    if val is None:
        return None

    if isinstance(val, time):
        return f"{val.hour:02d}:{val.minute:02d}"

    val = str(val)
    return val[:5]  # handles '09:00:00' -> '09:00'


# duration → minutes → string
def duration_to_str(val):
    val = clean(val)
    if val is None:
        return "0"

    if isinstance(val, time):
        minutes = val.hour * 60 + val.minute
        return str(minutes)

    return str(int(val))


def to_int(val):
    val = clean(val)
    return int(val) if val is not None else 0


def to_float(val):
    val = clean(val)
    return float(val) if val is not None else 0.0


def get_schedule(emp_df, day) -> DaySchedule:
    """Returns the DaySchedule for the day of the week"""
    tech_details = emp_df[emp_df['WeekId'] == day].to_dict("records")[0]
    """
    Index(['EmployeeId', 'EmployeeNo', 'Latitude', 'Longitude', 'WeekId', 'InTime',
       'ArriveAtLastJobNoLaterThan', 'EarliestLunchTime', 'LatestLunchTime',
       'LunchDuration', 'MaxServiceDuration', 'MaxTotalDayDuration',
       'MaxDriveTime', 'MaxProductionValue', 'MaxNoOfJobs', 'MinNoOfJobs',
       'DayStartLocation', 'DayEndLocation', 'variation_percent',
       'driving_mode'],
      dtype='object')
      """
    sch = DaySchedule(
        day=DayOfTheWeek(day),

        inTime=to_time_str(tech_details.get('InTime')),
        lastStartTime=to_time_str(tech_details.get('ArriveAtLastJobNoLaterThan')),
        lastEndTime=to_time_str(tech_details.get('EndLastJobNoLaterThan')),

        earliestLunchTime=to_time_str(tech_details.get('EarliestLunchTime')),
        latestLunchTime=to_time_str(tech_details.get('LatestLunchTime')),

        lunchDuration=duration_to_str(tech_details.get('LunchDuration')),
        maxServiceDuration=duration_to_str(tech_details.get('MaxServiceDuration')),
        maxTotalDayDuration=duration_to_str(tech_details.get('MaxTotalDayDuration')),
        maxDriveTime=duration_to_str(tech_details.get('MaxDriveTime')),

        maxProductionValue=to_float(tech_details.get('MaxProductionValue')),
        maxNoOfJobs=to_int(tech_details.get('MaxNoOfJobs')),
        minNoOfJobs=to_int(tech_details.get('MinNoOfJobs')),

        dayStartLocation=Location(
            type=LocationType(tech_details.get('DayStartLocation')),
            lat=float(tech_details.get('Latitude')),
            lon=float(tech_details.get('Longitude'))
        )
    )
    return sch, tech_details

