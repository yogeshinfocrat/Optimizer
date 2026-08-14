from ortools.constraint_solver.pywrapcp import (
    RoutingIndexManager,
    RoutingModel,
    RoutingDimension,
)
from src.Mongo_Manager.db_repos.travel_data import TravelData
from src.Mongo_Manager.schemas.beta.internal_schema import MINUTES_PER_DAY, Data


class DimensionManager(object):
    """Class which sets dimensions onto a routing model"""

    def __init__(self, routing: RoutingModel, manager: RoutingIndexManager, dataSchema: Data):
        self.routing = routing
        self.manager = manager
        self.dataSchema = dataSchema

    # ----------------------------------------------------------
    # INTERNAL: Create per-vehicle transit callbacks safely
    # ----------------------------------------------------------
    def _register_vehicle_transit_callbacks(self, callback_factory):
        """
        Creates and registers ONE callback per vehicle.
        callback_factory(vehicle_id) -> actual callback
        Returns list of callback indices.
        """
        num_vehicles = self.routing.vehicles()
        callback_indices = []

        for v in range(num_vehicles):
            cb = callback_factory(v)
            cb_idx = self.routing.RegisterTransitCallback(cb)
            callback_indices.append(cb_idx)

            # VERY IMPORTANT: different vehicle = different cost function
            self.routing.SetArcCostEvaluatorOfVehicle(cb_idx, v)

        return callback_indices

    # ----------------------------------------------------------
    # TRAVEL DIMENSION (service time + drive time)
    # ----------------------------------------------------------
    def set_travel_dimension(self, travel_matrix: list[list[TravelData]]) -> RoutingDimension:
        """
        Sets dimension: travel_time + service_duration
        Supports per-vehicle speed.
        """

        def callback_factory(vehicle_id):
            speed_factor = self.dataSchema.vehicles[vehicle_id].speed_factor  # e.g. 1.0, 1.5 etc.
            def cb(from_index, to_index):
                f = self.manager.IndexToNode(from_index)
                t = self.manager.IndexToNode(to_index)

                service = self.dataSchema.nodes[f].minimum_duration
                drive = travel_matrix[f][t].time * speed_factor
                # print("before",travel_matrix[f][t].time ,"after",drive, "speed_factor",speed_factor)
                return int(service + drive)

            return cb

        cb_list = self._register_vehicle_transit_callbacks(callback_factory)

        travel_dim_name = "Travel"

        # Add single dimension but callback is per-vehicle
        self.routing.AddDimension(
            evaluator_index=cb_list[0],   # OR-Tools uses correct one internally
            slack_max=self.dataSchema.number_of_days * MINUTES_PER_DAY,
            capacity=self.dataSchema.number_of_days * MINUTES_PER_DAY,
            fix_start_cumul_to_zero=False,
            name=travel_dim_name,
        )

        return self.routing.GetDimensionOrDie(travel_dim_name)

    # ----------------------------------------------------------
    # DRIVE TIME DIMENSION (pure driving time only)
    # ----------------------------------------------------------
    def set_drive_time_dimension(self, travel_matrix: list[list[TravelData]]) -> RoutingDimension:

        def callback_factory(vehicle_id):
            speed_factor = self.dataSchema.vehicles[vehicle_id].speed_factor

            def cb(from_index, to_index):
                f = self.manager.IndexToNode(from_index)
                t = self.manager.IndexToNode(to_index)
                return int(travel_matrix[f][t].time * speed_factor)

            return cb

        cb_list = self._register_vehicle_transit_callbacks(callback_factory)

        dim_name = "DriveTime"

        self.routing.AddDimensionWithVehicleCapacity(
            evaluator_index=cb_list[0],
            slack_max=self.dataSchema.number_of_days * MINUTES_PER_DAY,
            vehicle_capacities=self.dataSchema.get_max_drive_time_for_vehicles(),
            fix_start_cumul_to_zero=True,
            name=dim_name,
        )

        return self.routing.GetDimensionOrDie(dim_name)

    # ----------------------------------------------------------
    # SERVICE DURATION DIMENSION (time spent at stops)
    # ----------------------------------------------------------
    def set_service_duration_dimension(self) -> RoutingDimension:

        def callback_factory(vehicle_id):
            def cb(from_index, to_index):
                f = self.manager.IndexToNode(from_index)
                return int(self.dataSchema.nodes[f].minimum_duration)
            return cb

        cb_list = self._register_vehicle_transit_callbacks(callback_factory)

        dim_name = "ServiceDuration"

        self.routing.AddDimensionWithVehicleCapacity(
            evaluator_index=cb_list[0],
            slack_max=self.dataSchema.number_of_days * MINUTES_PER_DAY,
            vehicle_capacities=self.dataSchema.get_max_service_duration_for_vehicles(),
            fix_start_cumul_to_zero=True,
            name=dim_name,
        )

        return self.routing.GetDimensionOrDie(dim_name)

    # ----------------------------------------------------------
    # DAY DURATION DIMENSION (full work-day length)
    # ----------------------------------------------------------
    def set_day_duration_dimension(self, travel_matrix: list[list[TravelData]]) -> RoutingDimension:

        def callback_factory(vehicle_id):
            speed_factor = self.dataSchema.vehicles[vehicle_id].speed_factor

            def cb(from_index, to_index):
                f = self.manager.IndexToNode(from_index)
                t = self.manager.IndexToNode(to_index)
                service = self.dataSchema.nodes[f].minimum_duration
                drive = travel_matrix[f][t].time * speed_factor
                return int(service + drive)

            return cb

        cb_list = self._register_vehicle_transit_callbacks(callback_factory)

        dim_name = "DayDuration"

        self.routing.AddDimensionWithVehicleCapacity(
            evaluator_index=cb_list[0],
            slack_max=self.dataSchema.number_of_days * MINUTES_PER_DAY,
            vehicle_capacities=self.dataSchema.get_max_travel_time_for_vehicles(),
            fix_start_cumul_to_zero=True,
            name=dim_name,
        )

        return self.routing.GetDimensionOrDie(dim_name)
