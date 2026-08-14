from ortools.constraint_solver.pywrapcp import (
    RoutingIndexManager,
    RoutingModel,
)

from src.Mongo_Manager.schemas.beta.internal_schema import Data


class LimitConstraints(object):
    """Sets constraints that imposes some sort of limits on the routing model"""

    def __init__(
        self, routing: RoutingModel, manager: RoutingIndexManager, dataSchema: Data
    ) -> None:
        self.routing = routing
        self.manager = manager
        self.dataSchema = dataSchema

    def set_max_stops(self):
        # Create and register a demand callback for max number of stops.
        def max_number_of_stops_callback(from_index):
            """All nodes except starting indexes have a demand of 1, meaning 1 stop"""
            # Convert from routing variable Index to demands NodeIndex.
            from_node = self.manager.IndexToNode(from_index)
            if from_node in self.dataSchema.start_indexes:
                return 0
            return 1

        max_number_of_stops_callback_index = self.routing.RegisterUnaryTransitCallback(
            max_number_of_stops_callback
        )

        # Add max stops dimension constraints.
        max_number_of_stops = "MaxNumberOfStops"
        self.routing.AddDimensionWithVehicleCapacity(
            max_number_of_stops_callback_index,
            0,  # null capacity slack
            self.dataSchema.get_max_stops_for_vehicles(),  # vehicle maximum capacities
            True,  # start cumulative to zero
            max_number_of_stops,
        )

    def set_max_production_value(self):
        # Create and register a demand callback for max production values.
        def max_production_value_callback(from_index):
            """Set the production value for each node, except starting indexes"""
            # Convert from routing variable Index to demands NodeIndex.
            from_node: int = self.manager.IndexToNode(from_index)
            if from_node in self.dataSchema.start_indexes:
                return 0
            return self.dataSchema.nodes[from_node].production_value

        max_production_value_callback_index = self.routing.RegisterUnaryTransitCallback(
            max_production_value_callback
        )

        # Add max stops dimension constraints.
        max_production_value_label = "MaxProductionValue"
        self.routing.AddDimensionWithVehicleCapacity(
            max_production_value_callback_index,
            0,  # no capacity slack
            self.dataSchema.get_max_production_value_for_vehicles(),  # vehicle maximum capacities
            True,  # start cumulative to zero
            max_production_value_label,
        )

        production_value_dimension = self.routing.GetDimensionOrDie(max_production_value_label)
        for vehicle_id in self.dataSchema.start_indexes:
            max_prod_val = self.dataSchema.get_max_production_value_for_vehicles()[vehicle_id]
            min_prod_val = self.dataSchema.vehicles[vehicle_id].min_production_value
            index = self.routing.End(vehicle_id)
            production_value_dimension.CumulVar(index).SetRange(min_prod_val, max_prod_val)


