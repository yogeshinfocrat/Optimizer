from ortools.constraint_solver.pywrapcp import (
    RoutingIndexManager,
    RoutingModel,
)
from src.Mongo_Manager.schemas.beta.internal_schema import Data, NodeType


class AssignmentConstraints(object):
    """
    Constraints that heavily influences or outright assigns a vehicle to a node.
    Strategies used could be to assign a penalty to a node, or to assigning which vehicles
    can visit a node.
    By setting a penalty on each node, we can force the solver to prioritize
    nodes that have a higher penalty if dropped. Also, setting penalties automatically
    allows the solver to drop nodes if it can't find a solution that meets the constraints.
    """

    def __init__(self, routing: RoutingModel, manager: RoutingIndexManager, dataSchema: Data) -> None:
        self.routing = routing
        self.manager = manager
        self.dataSchema = dataSchema

    def set_penalties(self,is_default=False,conflict_eve =[], all_lock = False):
        """
        A positive disjunction means the node is optional.
        The higher the penalty, less likely the node will be dropped.
        A negative disjunction means the node is required.
        """
        for index, node in enumerate(self.dataSchema.nodes):
            # log_info(f"Node: {node.name} Penalty: {node.penalty}")
            if all_lock:
                self.routing.AddDisjunction([self.manager.NodeToIndex(index)], -1)
            else:
                if is_default:
                    if node.name[1:10] == 'WorkOrder':
                        self.routing.AddDisjunction([self.manager.NodeToIndex(index)], 1000)
                    else:
                        self.routing.AddDisjunction([self.manager.NodeToIndex(index)], node.penalty)
                else:
                    if node.id in conflict_eve:
                        penalty = 1000
                    else:
                        penalty = node.penalty
                    self.routing.AddDisjunction([self.manager.NodeToIndex(index)], penalty)

    def assign_vehicles_to_nodes(self):
        """
        Assign vehicles to STOP nodes.
        - Hard constraint: Only vehicles in allowed_vehicle_ids can serve a node.
        - Soft preference: Preferred vehicles (from preferred_vehicle_ids) are encouraged via fixed cost penalty on non-preferred vehicles.
        """
        vehicle_id_to_index = {str(v.id): i for i, v in enumerate(self.dataSchema.vehicles)}

        for node_index, node in enumerate(self.dataSchema.nodes):
            if node.node_type != NodeType.STOP:
                continue

            # Skip if no allowed vehicles specified
            if not node.allowed_vehicle_ids:
                continue

            if not node.preferred_vehicle_ids:
                if len(node.allowed_vehicle_ids) > 0:
                    allowed_vehicle_indexes = []
                    for vehicle_id in node.allowed_vehicle_ids:
                        for i, vehicle in enumerate(self.dataSchema.vehicles):
                            if vehicle.id == vehicle_id:
                                allowed_vehicle_indexes.append(i)

                allowed_vehicles = [self.manager.NodeToIndex(i) for i in allowed_vehicle_indexes]
                self.routing.SetAllowedVehiclesForIndex(allowed_vehicles, self.manager.NodeToIndex(node_index))
                continue


            # Resolve allowed and preferred vehicle indexes
            allowed_vehicle_indexes = []
            preferred_indexes = []

            # Normalize preferred_vehicle_ids to a set
            preferred_ids_set = set()
            if hasattr(node, 'preferred_vehicle_ids'):
                preferred_ids_set = set(str(v) for v in node.preferred_vehicle_ids)
            elif hasattr(node, 'preferred_vehicle_id'):
                preferred_ids_set = {str(node.preferred_vehicle_id)}

            for vehicle_id in node.allowed_vehicle_ids:
                vehicle_id_str = str(vehicle_id)
                if vehicle_id_str not in vehicle_id_to_index:
                    print('\nSkipping vehicle_id_str\n')
                    continue  # skip unknown vehicle

                vehicle_index = vehicle_id_to_index[vehicle_id_str]
                allowed_vehicle_indexes.append(vehicle_index)

                if vehicle_id_str in preferred_ids_set:
                    preferred_indexes.append(vehicle_index)

            if not allowed_vehicle_indexes:
                print("skip if no valid vehicles found")
                continue  # skip if no valid vehicles found

            # Restrict node to allowed vehicles
            routing_node_index = self.manager.NodeToIndex(node_index)
            self.routing.SetAllowedVehiclesForIndex(allowed_vehicle_indexes, routing_node_index)

            # Apply soft penalty for non-preferred vehicles
            if preferred_indexes and len(preferred_indexes) < len(allowed_vehicle_indexes):
                # Add fixed cost penalty to each non-preferred vehicle
                for vehicle_index in allowed_vehicle_indexes:
                    if vehicle_index not in preferred_indexes:
                        # Add fixed cost to vehicle — this influences solver to prefer preferred vehicles
                        self.routing.SetFixedCostOfVehicle(10000, vehicle_index)

            # Debug (optional)
            # print(f"Node {node.id} allowed: {allowed_vehicle_indexes}, preferred: {preferred_indexes}")


    def make_nodes_nonassignable(self):
        """
        Makes a node nonassignable by making a new constraint.
        """
        # log_info("Starting to make nodes nonassignable")

        # Create and register a demand callback for max number of stops.
        def nonassignable_node_callback(from_index):
            """All nodes except starting indexes have a demand of 1, meaning 1 stop"""
            # Convert from routing variable Index to demands NodeIndex.
            from_node: int = self.manager.IndexToNode(from_index)
            # Find the node and if it's allowed vehicles is empty, return 1
            node = self.dataSchema.nodes[from_node]
            if node.node_type == NodeType.STOP and len(node.allowed_vehicle_ids) == 0:
                # log_info(f"Making node id: {node.id}, name: {node.name} nonassignable")
                return 1
            return 0

        nonassignable_node_callback_index = self.routing.RegisterUnaryTransitCallback(nonassignable_node_callback)

        # Add max stops dimension constraints.
        # All vehicles have zero capacity, meaning even taking on a single node
        # with a 1 capacity will make the vehicle exceed its capacity, so the
        # solver will not assign that node to any vehicle.
        nonassignable_node = "NonassignableNode"
        self.routing.AddDimension(
            nonassignable_node_callback_index,
            0,  # null capacity slack
            0,  # all vehicles have zero capacity
            True,  # start cumulative to zero
            nonassignable_node,
        )
