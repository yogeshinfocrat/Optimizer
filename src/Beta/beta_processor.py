from src.ETL.beta_operations.fetch_tech_details import get_tech_details
from src.ETL.beta_operations.fetch_wo_details import get_wo_details
from src.SQL_Manger.db_operations.db_manager import build_connetion, fetch_data_from_db, close_connetion, \
    build_separate_db_connection
from src.Mongo_Manager.schemas.beta.bestfit_schema import ConfigDetails, RoutingResponse
from src.Beta.beta_mapper import create_route_data
from src.Beta.beta_validator import validate_event
from datetime import datetime
from src.Beta.beta_routing_utils import empty_routing_response
from src.Beta.beta_response_mapper import convert_response
from src.Utils.log import logger
from src.DistanceMatrix.matrix_builder import build_travel_matrix
import uuid, re
from collections import defaultdict
from src.Beta.beta_or_tool_operation import solve_routing
from src.Beta.beta_request_builder import create_routing_request
from src.Mongo_Manager.db_repos.routing_task import RoutingTask, CacheResponse
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from hashlib import sha256
import json, copy
from src.ETL.beta_operations.sql_injector import fill_optimization_masters


def find_invalid_coordinates(route_data):
    """
    Given a list of route dictionaries with 'origin', 'destination', and 'status',
    this function identifies coordinates that failed to connect with all other unique coordinates.

    Parameters:
        route_data (list of dict): Each dict has 'origin', 'destination', 'status'.

    Returns:
        List of likely invalid coordinates.
    """
    # Collect all unique coordinates
    coordinates = set()
    for r in route_data:
        coordinates.add(r['origin'])
        coordinates.add(r['destination'])

    # Build failure map: who failed with whom
    failure_map = defaultdict(set)
    for r in route_data:
        if r['status'] == 'ZERO_RESULTS':
            failure_map[r['origin']].add(r['destination'])
            failure_map[r['destination']].add(r['origin'])

    return failure_map, coordinates


def get_routing_response(work_order_details, tech_df, skills_df, block_time, date_range, req, config,
                         travel_data_repository, requestId, rr):
    logger.info(
        "Inside routing response"
    )
    logger.info(f"Length of wo_details, {work_order_details.shape[0]}")
    errors_event_ids, list_of_error_message = validate_event(work_order_details, tech_df, block_time, config, req,
                                                             date_range)

    if len(list_of_error_message):
        logger.info(list_of_error_message)
        raise Exception(','.join(list_of_error_message))

    dataSchema, list_error_events, error_message_ = create_route_data(work_order_details, date_range, block_time,
                                                                      skills_df, tech_df, req, config)
    logger.info(
        "Data Schema Prepared"
    )
    # distance_calculation_settings = request.distanceCalculationSettings
    # dataSchema, list_error_events, error_message_ = create_route_data(request, distance_calculation_settings.apiKey)
    conflict_events_ids_ = set(list_error_events + errors_event_ids)
    """Removing conflict work orders from data and will add them in unassigned section later"""
    conflict_events_nodes_ = []
    new_nodes_ = []
    new_stops_ = []
    for wo in dataSchema.nodes:
        if wo.id in conflict_events_ids_ or wo.name[13:] in conflict_events_ids_ or wo.name[
                                                                                    16:] in conflict_events_ids_:
            conflict_events_nodes_.append(wo)
        else:
            new_nodes_.append(wo)
            if wo.node_type.value == 'STOP':
                new_stops_.append(wo)

    dataSchema.nodes = new_nodes_
    dataSchema.stops = new_stops_

    if not len(new_stops_):
        routing_response = empty_routing_response(dataSchema)
        routing_response.missed_stops.extend(conflict_events_nodes_)
        routing_response_converted = convert_response(routing_response, dataSchema, work_order_details, tech_df,
                                                      skills_df,
                                                      block_time, date_range, req, config)
        return routing_response_converted, False, [], list_of_error_message

    try:
        user_details = {"clientID": req.CompanyKey, "userID": req.User}
    except:
        logger.info("Logged in user details missing")
        user_details = {"clientID": "None", "userID": "None"}

    object_id = str(uuid.uuid4())
    log_flag = False
    isBestFitReq = True
    travel_matrix, failed_coordinates = build_travel_matrix(
        object_id,
        requestId,
        user_details,
        dataSchema,
        travel_data_repository,
        api_key=config.api_key,
        log_flag=log_flag
    )
    unreachable_events = set()
    if len(failed_coordinates):
        failure_map, coordinates = find_invalid_coordinates(failed_coordinates)
        failure_threshold = sorted({len(v) for v in failure_map.values()}, reverse=True)
        for threshold in failure_threshold:
            repeated_coordinates = []
            for coord in coordinates:
                if len(failure_map[coord]) >= threshold:
                    repeated_coordinates.append(coord)

            logger.info("Likely invalid coordinates:")
            for coord in repeated_coordinates:
                logger.info(f"❌ {coord}")

            # Removing those work orders from nodes and stops
            new_nodes_ = []
            new_stops_ = []
            for wo in dataSchema.nodes:
                if str(wo.latitude) + ',' + str(wo.longitude) in repeated_coordinates:
                    unreachable_events.add(wo.name[13:])
                    conflict_events_nodes_.append(wo)
                else:
                    new_nodes_.append(wo)
                if wo.node_type.value == 'STOP':
                    new_stops_.append(wo)
            dataSchema.nodes = new_nodes_
            dataSchema.stops = new_stops_
            if not len(new_nodes_):
                lst_ur_eve = [i for i in unreachable_events if i[-9:] != 'FIRST_JOB']
                raise Exception(f"Unreachable services {','.join(lst_ur_eve)}")

            travel_matrix, failed_coordinates = build_travel_matrix(
                object_id,
                requestId,
                user_details,
                dataSchema,
                travel_data_repository,
                api_key=config.api_key,
                log_flag=log_flag
            )
            if not failed_coordinates:
                break  # Exit the loop if no failed coordinates

    list_of_error_message = list_of_error_message + error_message_

    if len(failed_coordinates):
        raise Exception("Unreachable location of unidentified service")

    logger.info(
        "Got the matrix"
    )

    if len(list_of_error_message):
        logger.info(f'list_of_error_message: {list_of_error_message}')
        raise Exception(','.join(list_of_error_message))

    temp_response, partially_optimized_flag = solve_routing(dataSchema, travel_matrix,
                                                            isBestFitReq, requestId, log_flag,
                                                            work_order_details, tech_df, skills_df,
                                                            block_time, date_range, req, config, rr
                                                            )
    temp_response.missed_stops.extend(conflict_events_nodes_)
    routing_response = convert_response(temp_response, dataSchema, work_order_details, tech_df, skills_df,
                                        block_time, date_range, req, config)

    # for i in routing_response.assignedEventList:
    #     logger.info(i)
    return routing_response, partially_optimized_flag, unreachable_events, list_of_error_message


def custom_serializer(obj):
    # Handle non-serializable objects here
    if hasattr(obj, '__dict__'):  # For custom objects
        return obj.__dict__
    # Add other custom types if necessary
    raise TypeError(f"Type {type(obj)} not serializable")


def hash_request_body(body: dict) -> str:
    return sha256(json.dumps(body, sort_keys=True, default=custom_serializer).encode()).hexdigest()


def allocate_routes_for_beta(req, travel_data_repository, routing_task_repository, company_key):
    build_connetion()
    conn_string = fetch_data_from_db(f"""SELECT ConnectionStringName FROM Common.CompanyTenantMaster WHERE 
        CompanyKey  = '{company_key}'""")
    if not conn_string.empty:
        close_connetion()
        build_separate_db_connection(conn_string['ConnectionStringName'].iloc[0], company_key)
    else:
        logger.info("Connection string not found connecting to common DB")
    comp_ids = fetch_data_from_db(f"""SELECT  cm1.CompanyId as common_comp_id ,cm2.CompanyId as hrms_comp_id, 
    cm.CompanyId as crm_comp_id FROM crm.CompanyMaster cm join COMMON.CompanyMaster cm1 on cm.CompanyKey = cm1.CompanyKey 
    join HRMS.CompanyMaster cm2 on cm2.CompanyKey = cm.CompanyKey  WHERE cm.CompanyKey = '{req.CompanyKey}';""")

    company_config = fetch_data_from_db(f"""SELECT IsEmployeeBranchMappingInRO, RouteOptimizationMappingType , 
    IsPropertyTypeInRO,
    ConsiderSkillinRouteOptimization,
    IsRouteOptimizationEnabled,
     OptimizeParameter FROM Common.companyconfiguration cc WHERE CompanyId = {int(comp_ids['common_comp_id'].iloc[0])};""")

    if not pd.isna(company_config['RouteOptimizationMappingType'].iloc[0]):
        if company_config['RouteOptimizationMappingType'].iloc[0] == 'Geofencing':
            considerZipCode = False
            IsEnableRoGeofencing = True
        elif company_config['RouteOptimizationMappingType'].iloc[0] == 'ZipCodeMapping':
            considerZipCode = True
            IsEnableRoGeofencing = False
    else:
        considerZipCode = False
        IsEnableRoGeofencing = False

    config = ConfigDetails(
        CRM_CompId=comp_ids['crm_comp_id'].iloc[0],
        HRMS_CompId=comp_ids['hrms_comp_id'].iloc[0],
        Common_CompId=comp_ids['common_comp_id'].iloc[0],
        IsRouteOptimizationEnabled=company_config['IsRouteOptimizationEnabled'].iloc[0],
        ConsiderSkillInRouteOptimization=company_config['ConsiderSkillinRouteOptimization'].iloc[0],
        considerDriveTime=True if company_config['OptimizeParameter'].iloc[0] else False,
        api_key='Yogeshpandiya',
        considerZipCode=considerZipCode,
        considerBranch=company_config['IsEmployeeBranchMappingInRO'].iloc[0],
        IsEnableRoGeofencing=False,  # IsEnableRoGeofencing,  # company_config['IsEnableRoGeofencing'].iloc[0],
        IsPropertyTypeInRO=company_config['IsPropertyTypeInRO'].iloc[0]

    )
    skills_df, tech_df = get_tech_details(req, config)

    work_order_details, q1, startDate_str, endDate_str, date_range, block_time, original_block_time_df = get_wo_details(
        req, config, tech_df)

    requestId = str(uuid.uuid4())

    request = create_routing_request(work_order_details,
                                     tech_df,
                                     skills_df,
                                     original_block_time_df,
                                     req,
                                     startDate_str,
                                     endDate_str, config, date_range)
    routing_task = RoutingTask(
        requestId=requestId,
        requestType="SYNC",
        request=request,
        timestamp=datetime.now(),
    )
    routing_task_repository.insert_routing_task(routing_task)

    logger.info(f"In Background routing task started for: {requestId}")
    request.eventList.sort(
        key=lambda x: (
            int(x.eventId),
            datetime.strptime(x.eventDate, "%m/%d/%Y"),
            x.route
        )
    )
    # Sorting blockTimes inside each technician based on lat and lon
    for technician in request.techniciansList:
        technician.blockTimes.sort(
            key=lambda x: (
                datetime.strptime(x.startDateTime, "%m/%d/%Y %H:%M"),
                x.blockLocation.lat if x.blockLocation and x.blockLocation.lat is not None else float('-inf'),
                x.blockLocation.lon if x.blockLocation and x.blockLocation.lon is not None else float('-inf')
            )
        )

    # tech list sorting
    request.techniciansList.sort(key=lambda x: int(x.id))
    for technician in request.techniciansList:
        # tech name handle
        technician.name = re.sub(r'\s+', ' ', technician.name).strip().lower()
        for schedule in technician.schedule:
            # duration handle
            if schedule.lunchDuration in ('0', '00'):
                schedule.lunchDuration = '0'
            # location handle
            location = schedule.dayStartLocation
            location.lat = round(location.lat, 7)
            location.lon = round(location.lon, 7)
        for blocktime_ in technician.blockTimes:
            if blocktime_.blockLocation.lat and blocktime_.blockLocation.lon:
                blocktime_.blockLocation.lat = round(blocktime_.blockLocation.lat, 7)
                blocktime_.blockLocation.lon = round(blocktime_.blockLocation.lon, 7)

    for event in request.eventList:
        event.lat = round(event.lat, 7)
        event.lon = round(event.lon, 7)
        if not event.lockTime:
            event.scheduleTime = '09:00'

    cache_request_copy = copy.deepcopy(request)

    for event in cache_request_copy.eventList:
        # category order handle
        event.skills.sort(key=lambda s: s.serviceSysName)
        event.eventId = 0
        # if event.name[:10] == 'RO-TempGWO':
        #     event.name = 'RO-TempGWO-AC-8443' + str(event.eventId)[-3:]

    cache_service = CacheResponse()
    hash_id = hash_request_body(dict(cache_request_copy))
    cache_response = cache_service.get_cache_response_if_exist(hash_id)

    request.woValidationReq = False

    if cache_response:
        logger.info(f"Found in cache HashId: {hash_id}")
        routingResponse = RoutingResponse(
            assignedEventList=cache_response.response['assignedEventList'],
            unassignedEventList=cache_response.response['unassignedEventList'],
            technicianInfoList=cache_response.response['technicianInfoList'],
        )
        list_of_errors = cache_response.error_list
        return (
        work_order_details, q1, startDate_str, endDate_str, date_range, block_time, skills_df, tech_df, requestId,
        routingResponse, False, list_of_errors, [], config, request, original_block_time_df)
    else:
        logger.info(f"Not Found in cache HashId: {hash_id}")

    routingResponse, partially_optimized, list_of_errors, unr_eve_lst_ = main_routing(
        work_order_details,
        tech_df,
        skills_df,
        block_time,
        date_range,
        req,
        config,
        travel_data_repository,
        requestId,
        routing_task_repository,
        request
    )
    dict_response_for_cache = routingResponse.dict()

    # dummy executionInfo
    executionInfo = {
        "executionTimes": {
            "matrixStartTime": 1776517140860,
            "matrixEndTime": 1776517141057,
            "executionStartTime": 1776517141058,
            "executionEndTime": 1776517141127,
            "executionTime": 69,
            "matrixExecutionTime": 197
        },
        "executionConfigs": {
            "distanceCalculationType": "API",
            "firstSolutionStrategy": "SEQUENTIAL_CHEAPEST_INSERTION"
        },
        "notes": {}
    }
    dict_response_for_cache['executionInfo'] = executionInfo
    cache_service.insert_into_cache_table(hash_id, dict_response_for_cache, list_of_errors, "")

    final_response = fill_optimization_masters(work_order_details, startDate_str, endDate_str,
                                               block_time, skills_df,
                                               tech_df, requestId, routingResponse,
                                               list_of_errors, req, request,
                                               original_block_time_df)

    close_connetion()
    return final_response


def process_single_route(args):
    (
        dt,
        emp,
        wo_df,
        tech_df_single,
        skill_df_single,
        block_df,
        req,
        config,
        travel_data_repository,
        requestId,
        rr
    ) = args

    date = pd.to_datetime([dt])

    routing_response = RoutingResponse(
        assignedEventList=[],
        unassignedEventList=[],
        technicianInfoList=[],
    )
    # print(emp)
    # print(block_df)

    try:
        return (
            dt,
            get_routing_response(
                wo_df,
                tech_df_single,
                skill_df_single,
                block_df,
                date,
                req,
                config,
                travel_data_repository,
                requestId,
                rr
            )
        )
    except Exception as e:
        logger.info(f"error in processing for date {dt} and emp {emp} Error:{e}")
        routing_response.assignedEventList = []
        routing_response.unassignedEventList = [i for i in rr.eventList
                                                if i.eventDate == dt.strftime('%m/%d/%Y')
                                                and i.constraints.userPreferredTechnicianId == emp]
        unreachable_events = []
        partially_optimized_flag = False
        list_of_error_message = [e]
        return dt, (routing_response,
                    partially_optimized_flag,
                    unreachable_events,
                    list_of_error_message)


def main_routing(
        work_order_details,
        tech_df,
        skills_df,
        block_time,
        date_range,
        req,
        config,
        travel_data_repository,
        requestId,
        routing_task_repository,
        rr
):
    routing_response = RoutingResponse(
        assignedEventList=[],
        unassignedEventList=[],
        technicianInfoList=[],
    )

    list_of_errors = []

    # --------------------------------------
    # PREPROCESS / GROUP ONLY ONCE
    # --------------------------------------

    work_order_details['eventDate'] = pd.to_datetime(
        work_order_details['eventDate']
    )

    if not block_time.empty:
        block_time['blockDate'] = pd.to_datetime(
            block_time['blockDate']
        )

    # date_range = pd.to_datetime(date_range)

    # Group work orders
    wo_grouped = {
        k: v
        for k, v in work_order_details.groupby(
            ['eventDate', 'userPreferredTechnicianId'],
            sort=False
        )
    }

    # Group technicians
    tech_grouped = {
        k: v
        for k, v in tech_df.groupby('EmployeeNo', sort=False)
    }

    # Group skills
    if skills_df.empty:
        skill_grouped = {}
    else:
        skill_grouped = {
            k: v
            for k, v in skills_df.groupby('EmployeeNo', sort=False)
        }

    # Group block times
    if block_time.empty:
        block_grouped = {}
    else:
        block_grouped = {
            k: v
            for k, v in block_time.groupby('blockDate', sort=False)
        }

    employees = tech_df['EmployeeNo'].unique()

    # --------------------------------------
    # BUILD TASKS
    # --------------------------------------

    tasks = []

    empty_skill_df = pd.DataFrame(columns=skills_df.columns)

    for dt in date_range:
        block_df = block_grouped.get(dt, block_time.iloc[0:0])
        for emp in employees:
            new_block_df = block_df[block_df['EmployeeNo'] == emp]
            wo_df = wo_grouped.get(
                (dt, emp),
                work_order_details.iloc[0:0]
            )

            if wo_df.empty:
                continue

            tasks.append(
                (
                    dt,
                    emp,
                    wo_df,
                    tech_grouped.get(emp, tech_df.iloc[0:0]),
                    skill_grouped.get(emp, empty_skill_df),
                    new_block_df,
                    req,
                    config,
                    travel_data_repository,
                    requestId,
                    rr
                )
            )

    # --------------------------------------
    # PARALLEL EXECUTION
    # --------------------------------------

    with ThreadPoolExecutor() as executor:

        futures = [
            executor.submit(process_single_route, task)
            for task in tasks
        ]

        for future in as_completed(futures):
            dt, result = future.result()

            a, b, c, d = result
            routing_response.assignedEventList.extend(
                a.assignedEventList
            )

            routing_response.unassignedEventList.extend(
                a.unassignedEventList
            )

            routing_response.technicianInfoList.extend(
                a.technicianInfoList
            )

            list_of_errors.extend(
                [f"Date: {dt.date()} {x}" for x in d]
            )

            list_of_errors.extend(
                [f"Date: {dt.date()} Unreachable services {x}" for x in c]
            )

    routing_task_repository.complete_routing_task(
        requestId,
        routing_response,
        None
    )

    return routing_response, b, list_of_errors, d
