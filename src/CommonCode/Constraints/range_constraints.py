from datetime import timedelta
from ortools.constraint_solver.pywrapcp import (
    RoutingDimension,
    RoutingIndexManager,
    RoutingModel,
)

from src.Mongo_Manager.schemas.beta.internal_schema import MINUTES_PER_DAY, Data
from src.Utils.date_utils import get_minutes_from_date_time, is_date_in_range


class RangeConstraints(object):
    """Sets constraints that imposes limits based on ranges on the routing model"""

    def __init__(self, routing: RoutingModel, manager: RoutingIndexManager, dataSchema: Data) -> None:
        self.routing = routing
        self.manager = manager
        self.dataSchema = dataSchema

    def set_vehicle_time_windows(self, travel_dimension: RoutingDimension):
        # Add start and end time constraints for each vehicle.
        for vehicle_index in range(len(self.dataSchema.vehicles)):
            # Extract time constraints for the vehicle
            start_time_minutes = self.dataSchema.vehicles[vehicle_index].start_time
            max_start_time_minutes = self.dataSchema.vehicles[vehicle_index].last_start_time
            end_time_minutes = self.dataSchema.vehicles[vehicle_index].end_time

            # Set time range for vehicle's start index
            start_index = self.routing.Start(vehicle_index)
            travel_dimension.CumulVar(start_index).SetRange(
                start_time_minutes, end_time_minutes
            )

            # Set time range for vehicle's end index
            end_index = self.routing.End(vehicle_index)
            travel_dimension.CumulVar(end_index).SetRange(
                start_time_minutes, end_time_minutes
            )

    def set_node_time_windows(self, travel_dimension: RoutingDimension):
        """Sets the time windows for each node except the start nodes."""
        number_of_days = len(self.dataSchema.date_range)

        for location_index, node in enumerate(self.dataSchema.nodes):
            if location_index in self.dataSchema.start_indexes:
                continue
            index: int = self.manager.NodeToIndex(location_index)

            # For each day, set the time window offset by the day
            # In order to do so, first, set the range as the start of the first day and end of the last day
            time_of_last_day = node.end_time + number_of_days * MINUTES_PER_DAY
            travel_dimension.CumulVar(index).SetRange(node.start_time, time_of_last_day)

            # Enumerate through the date range and remove the
            # interval before the start time window and after the end time window
            for i, date in enumerate(self.dataSchema.date_range):
                start_of_day = i * MINUTES_PER_DAY
                end_of_day = (i + 1) * MINUTES_PER_DAY

                # If this is not the last day, then minus one minute from the end of the day
                if i != number_of_days - 1:
                    end_of_day -= 1

                # If the node is not available on this day, remove the entire day
                if date not in node.allowed_dates:
                    travel_dimension.CumulVar(index).RemoveInterval(start_of_day, end_of_day - 1)
                else:
                    start_of_window = node.start_time + start_of_day
                    end_of_window = node.end_time + start_of_day
                    cumul_var = travel_dimension.CumulVar(index)
                    cumul_var.RemoveInterval(start_of_day, start_of_window - 1)
                    cumul_var.RemoveInterval(end_of_window + 1, end_of_day)

                    # Remove the excluded date times
                    for excluded_datetime in node.excluded_date_times:
                        if is_date_in_range(excluded_datetime, [date], [date + timedelta(days=1)]):
                            start_excluded_window = (
                                get_minutes_from_date_time(excluded_datetime.start_date_time) + start_of_day
                            )
                            end_excluded_window = (
                                get_minutes_from_date_time(excluded_datetime.end_date_time) + start_of_day
                            )
                            cumul_var.RemoveInterval(
                                start_excluded_window,
                                end_excluded_window,
                            )

            # Print out the intervals for each node
            # log_info(f"travel_dimension.CumulVar({index}).Intervals(): {travel_dimension.CumulVar(index)}")
