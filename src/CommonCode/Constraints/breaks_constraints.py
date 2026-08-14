from ortools.constraint_solver.pywrapcp import (
    IntervalVar,
    RoutingDimension,
    RoutingIndexManager,
    RoutingModel,
    Solver,
)

from  src.Mongo_Manager.schemas.beta.internal_schema import Data


class BreakConstraints(object):
    """Sets constraints that forces breaks on the routing model for each vehicle"""

    def __init__(self, routing: RoutingModel, manager: RoutingIndexManager, dataSchema: Data) -> None:
        self.routing = routing
        self.manager = manager
        self.dataSchema = dataSchema

    def set_breaks(self, travel_dimension: RoutingDimension) -> list[list[IntervalVar]]:
        break_intervals: list[list[IntervalVar]] = []
        for vehicle_id in range(len(self.dataSchema.vehicles)):
            vehicle = self.dataSchema.vehicles[vehicle_id]

            # Need a pre-travel array using the solver's index order.
            # https://groups.google.com/g/or-tools-discuss/c/rNILvzUT21U/m/206HwWWYBAAJ
            node_visit_transits = [0] * self.routing.Size()
            for index in range(self.routing.Size()):
                node_index: int = self.manager.IndexToNode(index)
                node_visit_transits[index] = self.dataSchema.nodes[node_index].minimum_duration

            solver: Solver = self.routing.solver()
            intervals = []
            for ind, brk in enumerate(vehicle.breaks):
                if ind == 0 and brk.duration == 0:
                    continue
                if ind == 0:
                    break_type = 'LunchBreak'
                    end = brk.end_time
                else:
                    break_type = 'BlockTimeBreak'
                    end = brk.start_time  # Block time end should be same as start for the certain amount of time.
                if brk.type == 'TimeToLeaveOpenPerDay':
                    break_type = 'TimeToLeaveOpenPerDay'
                    end = brk.end_time
                name = f"Break at {brk.start_time} for vehicle: {vehicle.name}, {ind}, Type: {break_type}"
                interval = solver.FixedDurationIntervalVar(
                    brk.start_time,
                    # this is actually the last time the break can "start", not when it ends
                    end,
                    brk.duration,
                    False,  # optional field. False makes the break not optional.
                    name,
                )
                # log_info(
                #     f"vehicle name: {vehicle.name}, brk.start_time: {brk.start_time}, brk.end_time: {brk.end_time}, brk.duration: {brk.duration}"
                # )
                intervals.append(interval)

            travel_dimension.SetBreakIntervalsOfVehicle(
                intervals,
                vehicle_id,
                node_visit_transits,
            )
            break_intervals.append(intervals)
        return break_intervals
