from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from src.Mongo_Manager.db_repos.travel_data import TravelData
from src.Beta.beta_routing_utils import empty_routing_response
from src.Mongo_Manager.schemas.beta.internal_schema import Data
from src.Mongo_Manager.schemas.beta.bestfit_schema import RoutingResponse
# from src.optimizer.processor import get_new_time_of_events
from src.Utils.log import logger
from src.CommonCode.Constraints.breaks_constraints import BreakConstraints
from src.CommonCode.Constraints.limit_constraints import LimitConstraints
from src.CommonCode.Constraints.assignment_constraints import AssignmentConstraints
from src.CommonCode.Constraints.range_constraints import RangeConstraints
from src.CommonCode.Constraints.dimension_manager import DimensionManager
from src.Beta.beta_routing_utils import get_routing_response
from ortools.constraint_solver.pywrapcp import (
    RoutingIndexManager,
    RoutingModel,
    RoutingDimension,
)


def ro_solver(travel_matrix, data_schema, consider_penalties=True, conflict_eve=[], all_lock=False):
    # Create the routing index manager.
    manager = RoutingIndexManager(
        len(travel_matrix),
        len(data_schema.vehicles),
        data_schema.start_indexes,
        data_schema.end_indexes,
    )

    # Create Routing Model.
    routing = RoutingModel(manager)

    # Initialize helpers
    dimension_manager = DimensionManager(routing, manager, data_schema)
    assignment_constraints = AssignmentConstraints(routing, manager, data_schema)
    range_constraints = RangeConstraints(routing, manager, data_schema)
    limit_constraints = LimitConstraints(routing, manager, data_schema)
    break_constraints = BreakConstraints(routing, manager, data_schema)

    # =======================
    # CREATE DIMENSIONS
    # =======================
    travel_dimension: RoutingDimension = dimension_manager.set_travel_dimension(travel_matrix)
    dimension_manager.set_drive_time_dimension(travel_matrix)
    dimension_manager.set_service_duration_dimension()
    dimension_manager.set_day_duration_dimension(travel_matrix)

    # =======================
    # SET CONSTRAINTS
    # =======================
    if all_lock:
        assignment_constraints.set_penalties(False, conflict_eve, True)
    else:
        if consider_penalties:
            assignment_constraints.set_penalties(False, conflict_eve, False)
        else:
            assignment_constraints.set_penalties(True, [], False)

    assignment_constraints.assign_vehicles_to_nodes()
    assignment_constraints.make_nodes_nonassignable()
    range_constraints.set_node_time_windows(travel_dimension)
    range_constraints.set_vehicle_time_windows(travel_dimension)
    break_intervals = break_constraints.set_breaks(travel_dimension)
    # break_intervals = []
    limit_constraints.set_max_stops()
    limit_constraints.set_max_production_value()

    # Instantiate route start and end times to produce feasible times.
    for i in range(manager.GetNumberOfVehicles()):
        routing.AddVariableMinimizedByFinalizer(travel_dimension.CumulVar(routing.Start(i)))
        routing.AddVariableMinimizedByFinalizer(travel_dimension.CumulVar(routing.End(i)))

    return routing, manager, break_intervals

def solve_routing(
        dataSchema: Data,
        travel_matrix: list[list[TravelData]],
        requestId,
        log_flag,
) -> RoutingResponse:
    # latest_or_tool(dataSchema, travel_matrix)
    # response = latest_or_tool(dataSchema, travel_matrix)
    # return response, False
    partially_optimized_flag = False
    conflict_wos = []
    solution_status = {
        0: "ROUTING_NOT_SOLVED: Problem not solved yet.",
        1: "ROUTING_SUCCESS: Problem solved successfully.",
        2: "ROUTING_PARTIAL_SUCCESS_LOCAL_OPTIMUM_NOT_REACHED: Problem solved successfully after calling RoutingModel.Solve(), except that a local optimum has not been reached. Leaving more time would allow improving the solution.",
        3: "ROUTING_FAIL: No solution found to the problem.",
        4: "ROUTING_FAIL_TIMEOUT: Time limit reached before finding a solution.",
        5: "ROUTING_INVALID: Model, model parameters, or flags are not valid.",
        6: "ROUTING_INFEASIBLE: Problem proven to be infeasible."
    }

    # not True == False
    # not False == True

    if len(dataSchema.date_range)==1:
        #single day
        model_name = 'PATH_CHEAPEST_ARC'
        routing, manager, break_intervals = ro_solver(travel_matrix, dataSchema)
        # Setting first solution heuristic.
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        # search_parameters.log_search = True
        search_parameters.time_limit.seconds = 30
        search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        solution = routing.SolveWithParameters(search_parameters)
        try:
            if log_flag:
                logger.info(f'Result of PATH_CHEAPEST_ARC for BestFitRequest({requestId}): {solution_status[routing.status()]}')
        except Exception as e:
            print('Bypass', e)
    if solution:
        response = get_routing_response(
            data=dataSchema,
            travel_matrix=travel_matrix,
            manager=manager,
            routing=routing,
            solution=solution,
            break_intervals=break_intervals)

        return response, partially_optimized_flag
    else:
        logger.info("No solution from OR-Tool")
        return empty_routing_response(dataSchema), partially_optimized_flag
