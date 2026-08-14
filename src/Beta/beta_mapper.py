"""Set of utilities to map a transformer request to vehicles and nodes"""
from src.Utils.config import GlobalConfig
from datetime import datetime, timedelta
from dateutil import parser
import calendar
from src.Mongo_Manager.schemas.beta.bestfit_schema import (
    DateTimeRange,
    DaySchedule,
    Event,
    LocationType,
    RoutingRequest,
    Skill,
    Technician,
)
import pandas as pd
from src.Mongo_Manager.schemas.beta.internal_schema import (
    MINUTES_PER_DAY,
    Break,
    Data,
    DateTimes,
    Node,
    NodeType,
    Vehicle,
)
from src.Beta.beta_routing_utils import get_schedule, duration_to_str
from src.Utils.date_utils import (
    get_day_of_week_string,
    get_minutes_from_string,
)
import googlemaps
from src.Beta.beta_validator import work_orders_validation
from src.Utils.log import logger
import math
from datetime import date
from calendar import monthrange
from src.Beta.beta_allowed_vehicles import find_allowed_vehicle_ids_flatten



def last_day_of_month(year, month):
    _, last_day = calendar.monthrange(year, month)
    return last_day


def find_dates_for_days_fast(start_date, end_date, days_of_week):
    # Map days of the week to their corresponding integer values
    days_map = {'su': 6, 'mo': 0, 'tu': 1, 'we': 2, 'thu': 3, 'fri': 4, 'sat': 5}
    days_of_week_int = sorted(days_map[day.lower()] for day in days_of_week)

    # Find the first valid start date
    result_dates = []
    for day_int in days_of_week_int:
        first_date = start_date + timedelta(days=(day_int - start_date.weekday() + 7) % 7)
        while first_date <= end_date:
            result_dates.append(first_date)
            first_date += timedelta(days=7)

    return sorted(result_dates)





def create_block_time_breaks(
        date: datetime,
        schedule: DaySchedule,
        blockTimes,
        index: int,
        start_time,
        end_time,
        tech_loc,
        api_key,
        not_consider
) -> list[Break]:
    block_intervals_nodes = 0
    block_intervals_nodes_duration = 0
    to_removed: list[Break] = []
    tech_address = [f"{tech_loc[0]}, {tech_loc[1]}"]
    """Creates a list of breaks from the blockTimes"""
    breaks: list[Break] = []
    start_time_blocktime_conflict = []
    end_time_blocktime_conflict = []
    for ind, blockTime in blockTimes.iterrows():
        if blockTime.startDateTime > blockTime.endDateTime:
            raise Exception(f"""blockTime start > blockTime end on date {date}""")
        block_start_time = int((blockTime.startDateTime - date).total_seconds() / 60) + (index * MINUTES_PER_DAY)
        block_end_time = int((blockTime.endDateTime - date).total_seconds() / 60) + (index * MINUTES_PER_DAY)
        if not blockTime['Latitude']:
            breaks.append(
                Break(start_time=block_start_time, end_time=block_end_time, duration=block_end_time - block_start_time))
        else:
            breaks.append(
                Break(start_time=block_start_time, end_time=block_end_time, duration=block_end_time - block_start_time))
            to_removed.append(
                Break(start_time=block_start_time, end_time=block_end_time, duration=block_end_time - block_start_time))
            block_intervals_nodes += 1
            new_start_time = get_minutes_from_string(str(blockTime['startDateTime'].time())) + (
                    index * MINUTES_PER_DAY)
            new_end_time = get_minutes_from_string(str(blockTime['endDateTime'].time())) + (
                    index * MINUTES_PER_DAY)
            blockTimeAddress = [f"{blockTime['Latitude']}, {blockTime['Longitude']}"]
            if GlobalConfig.UNIVERSAL_KEY:
                api_key = GlobalConfig.UNIVERSAL_KEY
            if GlobalConfig.DEBUG_FLAG:
                api_key = GlobalConfig.TEST_KEYS[0]
            if not_consider:
                required_duration = 0
            else:
                try:
                    g_maps = googlemaps.Client(key=api_key)
                    result = g_maps.distance_matrix(
                        origins=blockTimeAddress,
                        destinations=tech_address,
                        mode="driving",
                    )
                    status = result.get("status")
                    if status == "OK":
                        required_duration = int(result["rows"][0]["elements"][0]["duration"]["value"] / 60)
                except Exception as e:
                    logger.info(f'Error: {e}')

            if start_time + required_duration > new_start_time:
                start_time_blocktime_conflict.append(blockTime['startDateTime'].strftime('%b %d %Y'))

            if end_time - required_duration < new_end_time:
                end_time_blocktime_conflict.append(blockTime['startDateTime'].strftime('%b %d %Y'))

            block_intervals_nodes_duration += (new_end_time - new_start_time)

        # INCREASING TECH END TIME BECAUSE RO SENDING EVERYTHING TO UNASSIGNED IN CASE WHEN BLOCK TIME START BEFORE TECH IN TIME AND END AFTER TECH END TIME
        if block_end_time > end_time:
            end_time = block_end_time
    return breaks, start_time, end_time, block_intervals_nodes, block_intervals_nodes_duration, to_removed, start_time_blocktime_conflict, end_time_blocktime_conflict


def create_lunch_break(schedule: DaySchedule, index: int) -> Break:
    """Creates a list of breaks from the day schedules"""
    lunch_start_time = get_minutes_from_string(schedule.earliestLunchTime) + (index * MINUTES_PER_DAY)
    # lunch_duration = int(schedule.lunchDuration)
    lunch_duration = int(schedule.lunchDuration or 0)

    lunch_end_time = lunch_start_time + lunch_duration
    if schedule.latestLunchTime:
        lunch_end_time = get_minutes_from_string(schedule.latestLunchTime) + (index * MINUTES_PER_DAY)

    # log_info(
    #     f"lunch_start_time: {lunch_start_time}, lunch_end_time: {lunch_end_time}, lunch_duration: {lunch_duration}"
    # )

    return Break(
        start_time=lunch_start_time,
        end_time=lunch_end_time,
        duration=lunch_duration,
    )


def overlap(ranges):
    for i in range(len(ranges) - 1):
        if pd.to_datetime(ranges[i].endDateTime) > pd.to_datetime(ranges[i + 1].startDateTime):
            return True
    return False


def get_speed_factor(variation=0, mode="average"):
    if mode == "slower":
        return 1 + (variation / 100)

    elif mode == "faster":
        if variation > 100:
            variation = 100
        return 1 - (variation / 100)

    else:  # average
        return 1.0


def create_vehicles(
        block_times, skills_df, tech_df, date_range, api_key
) -> Vehicle:
    min_production_value = 0
    # block_times = pd.DataFrame()
    vehicles: list[Vehicle] = []
    block_intervals = []
    start_block_time_conflicts = []
    end_block_time_conflicts = []
    for emp_no in tech_df['EmployeeNo'].unique():
        emp_df = tech_df[tech_df['EmployeeNo'] == emp_no]
        for index, date in enumerate(date_range):
            # get the day of the week of the date in lowercase
            day = get_day_of_week_string(date)

            # get the day schedule for the current date
            schedule, day_details = get_schedule(emp_df, day)

            maxNoOfJobs = schedule.maxNoOfJobs
            maxTotalDayDuration = int(schedule.maxTotalDayDuration)
            maxServiceDuration = schedule.maxServiceDuration

            # create the start and end time for the vehicle based on the schedule
            start_time = get_minutes_from_string(schedule.inTime) + (index * MINUTES_PER_DAY)
            end_time = get_minutes_from_string(schedule.lastEndTime) + (index * MINUTES_PER_DAY)
            last_start_time = get_minutes_from_string(schedule.lastStartTime) + (index * MINUTES_PER_DAY)

            def get_node_type(type):
                if type == LocationType.HOME:
                    return NodeType.HOME
                elif type == LocationType.OFFICE:
                    return NodeType.OFFICE
                elif type == LocationType.FIRST_JOB:
                    return NodeType.FIRST_JOB
                elif type == LocationType.LAST_JOB:
                    return NodeType.LAST_JOB

            # convert location_type to node_type
            node_type = get_node_type(schedule.dayStartLocation.type)

            if node_type == NodeType.FIRST_JOB or node_type == NodeType.LAST_JOB:
                not_consider = True
            else:
                not_consider = False

            to_removed = []
            # node_type = NodeType.HOME if schedule.dayStartLocation.type == LocationType.HOME else NodeType.OFFICE

            block_times.rename(columns={'FromDate': 'startDateTime', 'ToDate': 'endDateTime'}, inplace=True)
            block_times['startDateTime'] = pd.to_datetime(block_times['startDateTime'])
            block_times['endDateTime'] = pd.to_datetime(block_times['endDateTime'])

            # create the breaks for the vehicle
            if not block_times.empty:
                date = pd.to_datetime(date)
                next_day = date + timedelta(days=1)
                block_time = block_times[
                    (block_times['startDateTime'] >= date) & (block_times['startDateTime'] < next_day)]
                if not block_time.empty:
                    breaks, start_time, end_time, block_intervals_nodes, block_intervals_nodes_duration, to_removed, \
                        start_time_blocktime_conflict, end_time_blocktime_conflict = create_block_time_breaks(date,
                                                                                                              schedule,
                                                                                                              block_time,
                                                                                                              index,
                                                                                                              start_time,
                                                                                                              end_time,
                                                                                                              (
                                                                                                                  schedule.dayStartLocation.lat,
                                                                                                                  schedule.dayStartLocation.lon)
                                                                                                              ,api_key,
                                                                                                              not_consider)
                    block_intervals.extend(breaks)
                    start_block_time_conflicts.extend(start_time_blocktime_conflict)
                    end_block_time_conflicts.extend(end_time_blocktime_conflict)

                    if int(schedule.maxNoOfJobs) < block_intervals_nodes:
                        maxNoOfJobs = int(block_intervals_nodes)
                    if int(schedule.maxTotalDayDuration) < block_intervals_nodes_duration:
                        maxTotalDayDuration = int(block_intervals_nodes_duration)
                    if int(schedule.maxServiceDuration) < block_intervals_nodes_duration:
                        maxServiceDuration = int(block_intervals_nodes_duration)
                else:
                    breaks = []

            else:
                breaks = []

            lunch_break = create_lunch_break(schedule, index)
            """Merging all overlapped entries between Lunch-break and Block-Time"""
            for blk in breaks:
                if lunch_break.start_time >= blk.start_time and lunch_break.end_time <= blk.end_time:
                    if lunch_break.end_time + lunch_break.duration <= blk.end_time:
                        logger.info("Lunch break is within block time")
                        lunch_break.duration = 0
                    else:
                        lunch_break.duration = lunch_break.duration - (blk.end_time - lunch_break.end_time)
                        lunch_break.start_time = blk.end_time
                        lunch_break.end_time = blk.end_time
                elif lunch_break.start_time <= blk.start_time and lunch_break.end_time <= blk.end_time and lunch_break.end_time >= blk.start_time:
                    logger.info("Lunch started before block time ended in block time")
                    if lunch_break.end_time + lunch_break.duration <= blk.end_time:
                        lunch_break.end_time = blk.start_time
                        if lunch_break.duration > (lunch_break.end_time - lunch_break.start_time):
                            lunch_break.duration = (lunch_break.end_time - lunch_break.start_time)
                    else:
                        # This is for complex scenario where lunch break is starts few min before block time and end
                        # in between block time to optimize this we will consider break start either before and in
                        # between but the duration will be minimum of both the time
                        logger.info("""
                        This is for complex scenario where lunch break is start few min before block time and end
                        in between block time to optimize this we will consider lunch break start either before or in
                        between but the duration will be minimum of both the time
                        """)
                        lunch_break.duration = min(lunch_break.duration - (blk.end_time - lunch_break.end_time),
                                                   (blk.start_time - lunch_break.start_time))
                        lunch_break.end_time = blk.end_time

                elif lunch_break.start_time >= blk.start_time and lunch_break.end_time >= blk.end_time and lunch_break.start_time <= blk.end_time:
                    lunch_break.start_time = blk.end_time
                    logger.info("Lunch started in block time ended after block time")
                elif blk.start_time > lunch_break.start_time and blk.end_time < lunch_break.end_time:
                    logger.info("Block time with in lunch break")
            for brk_2_rm in to_removed:
                if brk_2_rm in breaks:
                    breaks.remove(brk_2_rm)
                    # block_intervals.remove(brk_2_rm)
            breaks.insert(0, lunch_break)
            # TODO Keep it inactive till further notification
            # Time to leave open breaks
            # print(breaks)
            # log_debug(f"appending vehicle: {technician.name} on date: {date}")

            try:
                vp = float(day_details.get("variation_percent"))

                if not math.isnan(vp) and vp >= 0:
                    tech_speed_factor = get_speed_factor(float(day_details.get('variation_percent')),
                                                         day_details.get('driving_mode'))
                else:
                    tech_speed_factor = 1

            except (TypeError, ValueError):
                tech_speed_factor = 1

            vehicles.append(
                Vehicle(
                    id=str(day_details.get('EmployeeNo')),
                    name=str(day_details.get('EmployeeId')),
                    start_time=start_time,
                    speed_factor=tech_speed_factor,
                    last_start_time=last_start_time,
                    end_time=end_time,
                    max_number_of_stops=maxNoOfJobs,
                    max_travel_time=0 if int(maxTotalDayDuration) < 0 else int(maxTotalDayDuration),
                    max_drive_time=int(schedule.maxDriveTime),
                    max_service_duration=int(maxServiceDuration),
                    max_production_value=int(schedule.maxProductionValue * 100),
                    min_production_value=int(min_production_value) * 100,
                    node_type=node_type,
                    latitude=schedule.dayStartLocation.lat,
                    longitude=schedule.dayStartLocation.lon,
                    address="",
                    breaks=breaks,
                )
            )

    if len(start_block_time_conflicts):
        raise Exception (f"{', '.join(start_block_time_conflicts)} block time conflict, "
                         f"Technician cannot reach block time location on time")

    if len(end_block_time_conflicts):
        raise Exception (f"{', '.join(end_block_time_conflicts)} block time conflict, "
                         f"Technician cannot reach home/office from block time location on time")
    return vehicles, block_intervals


def get_event_start_end_range(
        event,
        date_range
) -> tuple[datetime, datetime, int, int, bool]:
    """Gets the start and end dates and times for an event"""
    # log_info("\n========== get_start_end_range ==========")
    # TODO - If lockTime is true, use the eventDate and scheduleTime regardless of whether
    # constraints are null or not.
    is_time_locked = False
    if event.get('lockTime') and event.get('eventDate') and event.get('ScheduleTime'):
        event_start_date = pd.to_datetime(event.get('eventDate'))
        event_end_date = pd.to_datetime(event.get('eventDate'))
        event_start_time = event.get('ScheduleTime')
        event_end_time = event.get('ScheduleTime')
        is_time_locked = True

    elif event.get('lockTime'):
        logger.info(
            "Skipping: lockTime is true, but eventDate or scheduleTime is null or empty or consider_lock_time flag is False.")

    if not is_time_locked:
        # If startDate and endDate are null or empty, then use the event's eventDate and scheduleTime.
        # The eventDate and scheduleTime could be thought of an assigned event's date and scheduled time,
        # but for cases where the event is not assigned, the eventDate and scheduleTime becomes a "specific time"
        # range. The client could also send the specific time as the same start date and end date and same
        # start time and end time, which would better conform to the schema, but the first client
        # system was not designed to do this, so this is a workaround.
        event_start_date = pd.to_datetime(event.get('EarliestServiceDate')) or date_range[0]
        event_end_date = pd.to_datetime(event.get('LatestServiceDate')) or date_range[-1]
        event_start_time = event.get('ServiceStartStartTime') or datetime.strptime("00:00", "%H:%M").time()
        event_end_time = event.get('ServiceStartEndTime') or datetime.strptime("23:59", "%H:%M").time()

    start_date = event_start_date.to_pydatetime()
    end_date = event_end_date.to_pydatetime()
    start_time = event_start_time.hour * 60 + event_start_time.minute
    end_time = event_end_time.hour * 60 + event_end_time.minute #get_minutes_from_string(event_end_time)

    return start_date, end_date, start_time, end_time, is_time_locked


def find_allowed_vehicle_ids(event,
                tech_df,  skills_df, skill_flag) -> list[str]:
    """Finds the allowed vehicle ids. If lockTech is true, then only the lockTechId is allowed.
    If lockTech is false, then all technicians with all of the required skills are allowed
    """
    allowed_vehicle_ids: list[str] = []
    lockTech = event.get('lockTech')
    lockTechId = event.get('userPreferredTechnicianId')
    skills = event.get('categorySysName').split(', ')
    excludedTechIds = event.get('userNonPreferredTechnicianIds')

    # log_debug("\n==========================================")
    # log_info(f"Finding allowed vehicle ids for event: {event.eventId}")

    if lockTech and lockTechId:
        # If lockTechId is not null or empty and lockTechId exists in the list of technicians,
        # then append the lockTechId to the allowed vehicle ids.
        logger.info(f"lockTech is True and lockTechId: {lockTechId}")
        if [t for t in tech_df['EmployeeNo'].unique() if t == lockTechId]:
            allowed_vehicle_ids.append(lockTechId)
        else:
            logger.info(f"lockTechId: {lockTechId} does not exist in the list of technicians")
    else:
        for techId in tech_df['EmployeeNo'].unique():
            if excludedTechIds and techId in excludedTechIds:
                logger.info(f"technician: {techId} - is in excludedTechIds")
                continue
            if skill_flag:
                has_all_skills = True
                for event_skill in skills:
                    try:
                        tech_skills_list = skills_df[skills_df['EmployeeNo'] == techId][''].iloc[0].split(', ')
                    except:
                        has_all_skills = False
                        break
                    tech_skills = [s for s in tech_skills_list if s == event_skill]
                    if tech_skills.__len__() == 0:
                        has_all_skills = False
                        break
                    # elif tech_skills[0].proficiency < event_skill.proficiency:
                    #     has_all_skills = False
                    #     break
                if has_all_skills:
                    allowed_vehicle_ids.append(techId)
            else:
                allowed_vehicle_ids.append(techId)

    # log_info(f"event: {event.eventId} - allowed_vehicle_ids: {allowed_vehicle_ids}")
    # log_debug("==========================================\n")
    return allowed_vehicle_ids


# todo add constraint to filter the routes based on the need for each event.
def find_allowed_vehicle_ids_geo(event, tech_df,  skills_df, skill_flag,config) -> list[str]:
    """Finds the allowed vehicle ids. If lockTech is true, then only the lockTechId is allowed.
    If lockTech is false, then all technicians with all of the required skills are allowed
    """
    allowed_vehicle_ids: list[str] = []
    lockTech = event.get('lockTech')
    lockTechId = event.get('userPreferredTechnicianId')
    skills = event.get('categorySysName').split(',')
    excludedTechIds = event.get('userNonPreferredTechnicianIds')

    # log_debug("\n==========================================")
    # log_info(f"Finding allowed vehicle ids for event: {event.eventId}")

    if lockTech and lockTechId:
        # If lockTechId is not null or empty and lockTechId exists in the list of technicians,
        # then append the lockTechId to the allowed vehicle ids.
        logger.info(f"lockTech is True and lockTechId: {lockTechId}")

        tech = next((id for id in tech_df['EmployeeNo'].unique() if id == lockTechId), None)
        if tech:
            if lockTechId in event.get('inBoundEmployeeNo') or not config.IsEnableRoGeofencing:
                allowed_vehicle_ids.append(lockTechId)
        else:
            logger.info(f"lockTechId: {lockTechId} does not exist in the list of technicians")
    else:
        for technician_id in tech_df['EmployeeNo'].unique() :
            if excludedTechIds and technician_id in excludedTechIds:
                logger.info(f"technician: {technician_id} -  is in excludedTechIds")
                continue

            if skill_flag:
                has_all_skills = True
                for event_skill in skills:
                    try:
                        tech_skills_list = skills_df[skills_df['EmployeeNo'] == technician_id][''].iloc[0].split(',')
                    except:
                        has_all_skills = False
                        break
                    tech_skills = [s for s in tech_skills_list if s == event_skill]
                    if tech_skills.__len__() == 0:
                        has_all_skills = False
                        break
                    # elif tech_skills[0].proficiency < event_skill.proficiency:
                    #     has_all_skills = False
                    #     break

                if has_all_skills:
                    if technician_id in event.get('inBoundEmployeeNo') or not config.IsEnableRoGeofencing:
                        allowed_vehicle_ids.append(technician_id)
            else:
                if technician_id in event.get('inBoundEmployeeNo') or not config.IsEnableRoGeofencing:
                    allowed_vehicle_ids.append(technician_id)

    # log_info(f"event: {event.eventId} - allowed_vehicle_ids: {allowed_vehicle_ids}")
    # log_debug("==========================================\n")
    return allowed_vehicle_ids


def get_date_range(event, date_range):
    from_day = int(event.get('EligibleDaysFrom'))
    from_month = date_range[0].month
    from_year = date_range[0].year
    if len(date_range) == 1:
        to_day = int(event.get('EligibleDaysTo'))
        to_month = date_range[0].month
        to_year = date_range[0].year
    else:
        to_day = int(event.get('EligibleDaysTo'))
        to_month = date_range[0].month
        to_year = date_range[0].year

    lst_day_of_month = last_day_of_month(to_year, to_month)
    if to_day > lst_day_of_month:
        to_day = lst_day_of_month
    if from_day > lst_day_of_month:
        from_day = lst_day_of_month
    if from_day > to_day:
        from_day = to_day
    #TODO
    start_date = pd.Timestamp(year=from_year, month=from_month, day=from_day)
    end_date = pd.Timestamp(year=to_year, month=to_month, day=to_day)

    # Generate the date range
    date_range = pd.date_range(start=start_date, end=end_date)

    # Convert to list if needed
    date_list = date_range.to_list()
    return date_list


def create_stops(work_order_details, config, vehicles, blk_intervals,
                                                     error_message_list, req, date_range
                 ,tech_df,  skills_df):
    # startDate = pd.to_datetime(req.StartDate)
    # first_day = date(startDate.year, startDate.month, 1)
    #
    # last_day = date(
    #     startDate.year,
    #     startDate.month,
    #     monthrange(startDate.year, startDate.month)[1]
    # )
    #
    # work_order_details['EarliestServiceDate'] = work_order_details['EarliestServiceDate'].fillna(first_day)
    # work_order_details['LatestServiceDate'] = work_order_details['LatestServiceDate'].fillna(last_day)


    """Creates a list of stops from the request"""
    stops: list[Node] = []
    # single day work_orders list for validation
    single_day_work_orders = []
    # wo_flag_details = get_flags_details('new_work_orders_time')
    # new_node_date_time = wo_flag_details['Flag']

    # new_start_time = get_minutes_from_string(wo_flag_details['Value']['InTime'])
    # new_end_time = get_minutes_from_string(wo_flag_details['Value']['OutTime'])

    # same_as_optimizeDatesRange = get_flags_details('workorders_daterange_is_optimization_daterange')

    # new_start_date = parser.parse(startDate_str)
    # new_end_date = parser.parse(endDate_str)

    # lockTimeFlag = get_flags_details('consider_lock_time')
    # default_duration_detail = get_flags_details('default_duration')
    # default_duration = default_duration_detail['Flag']

    tech_not_available = []
    for event in work_order_details.to_dict("records"):
        try:
            eventDate_ = event.get('eventDate')
            year = eventDate_.year
            month = eventDate_.month
            first_day_of_month = date(year, month, 1)
            last_day_of_month_ = date(year, month, monthrange(year, month)[1])
        except:
            year = date_range[0].year
            month = date_range[0].month
            first_day_of_month = date(year, month, 1)
            last_day_of_month_ = date(year, month, monthrange(year, month)[1])

        if pd.isna(event.get('EarliestServiceDate')):
            event['EarliestServiceDate']=first_day_of_month
        if pd.isna(event.get('LatestServiceDate')):
            event['LatestServiceDate'] = last_day_of_month_
        if pd.isna(event.get('ServiceStartStartTime')):
            event['ServiceStartStartTime'] = datetime.strptime("00:00", "%H:%M").time()
        if pd.isna(event.get('ServiceStartEndTime')):
            event['ServiceStartEndTime'] = datetime.strptime("23:59", "%H:%M").time()
        (
            start_date,
            end_date,
            start_time,
            end_time,
            is_time_locked,
        ) = get_event_start_end_range(event, date_range)

        # if new_node_date_time and not is_time_locked:
        #     start_time = new_start_time
        #     end_time = new_end_time
        # if same_as_optimizeDatesRange:
        #     start_date = new_start_date
        #     end_date = new_end_date

        # event.constraints.inBoundEmployeeNo = [str(i) for i in event.constraints.inBoundEmployeeNo]
        # If time is locked, this means the event is not optional.
        # Setting penalty to -1 to ensure the event is always scheduled.
        # See http://google.github.io/or-tools/python/ortools/constraint_solver/pywrapcp.html#RoutingModel.AddDisjunction
        penalty = -1 if is_time_locked else 1000
        if penalty == -1 and event.get('eventType') != 'BlockTime':
            single_day_work_orders.append([event.get('name'), event.get('eventType'),
                                           event.get('ScheduleTime'), event.get('ScheduleTime'),
                                           event.get('eventDate'), event.get('eventDate')])
        elif penalty != -1:
            if timedelta.total_seconds(end_date - start_date) / 60 / 60 / 24 < 1:
                if event.get('eventId') != 0 :
                    # logger.info(f"""{event.name}, {event.eventType}, {event.constraints.timeRange.startTime},
                    #       {event.constraints.timeRange.endTime}, {event.constraints.dateRange.startDate},
                    #       {event.constraints.dateRange.endDate}"""
                    #             )
                    single_day_work_orders.append([event.get('name'), event.get('eventType'),
                                                   event.get('ServiceStartStartTime'), event.get('ServiceStartEndTime'),
                                                   start_date,
                                                   end_date])
                    penalty = -1

        # Determine allowed vehicles.
        if config.IsEnableRoGeofencing:
            allowed_vehicle_ids = find_allowed_vehicle_ids_flatten(event, tech_df, skills_df, config)
            preferred_vehicle_ids = event.get('inBoundEmployeeNo')
        else:
            allowed_vehicle_ids = find_allowed_vehicle_ids_flatten(event, tech_df, skills_df, config)
            preferred_vehicle_ids = []
        if not len(allowed_vehicle_ids):
            tech_not_available.append(str(event.get('eventId')))
        excluded_date_times: list[DateTimes] = []
        # for excluded_date_time in event.constraints.excludedDateTimes:
        #     excluded_date_times.append(
        #         DateTimes(
        #             start_date_time=parser.parse(excluded_date_time.startDateTime),
        #             end_date_time=parser.parse(excluded_date_time.endDateTime),
        #         )
        #     )

        # if default_duration:
        #     event.duration = default_duration_detail['Value']
        # print(start_date, end_date , start_time, end_time, event.eventId)

        # Eligible days of month and week constraints
        """
           Example use case if any work order has eligible days of week is ['Monday', 'Tuesday'] and eligible days of 
           eligible days of Month is ['12/01/2024','12/02/2024','12/04/2024','12/05/2024'] and date range is 
           est: '12/01/2024', and lst: '12/31/2024' then this work order will only schedule on ('12/02/2024' - Tuesday)
        """
        if not len(event.get('EligibleDaysOfWeek')):
            event['EligibleDaysOfWeek'] = [
                "su",
                "mo",
                "tu",
                "we",
                "thu",
                "fri",
                "sat"
            ]
        if pd.isna(event.get('EligibleDaysFrom')):
            eligible_days_of_month = find_dates_for_days_fast(start_date, end_date, [
                "su",
                "mo",
                "tu",
                "we",
                "thu",
                "fri",
                "sat"
            ])
        else:
            eligible_days_of_month = get_date_range(event, date_range)

        eligible_days_of_week = find_dates_for_days_fast(start_date, end_date, event.get('EligibleDaysOfWeek'))
        allowed_dates = [e_date for e_date in eligible_days_of_month if e_date in eligible_days_of_week]
        min_duration = event.get('duration')
        try:
            min_duration = duration_to_str(event.get('duration'))
        except:
            min_duration = event.get('duration')

        stops.append(
            Node(
                id=str(event.get('eventId')),
                node_type=NodeType.STOP,
                accountNumber=event.get('AccountNumber'),
                name=f"${event.get('eventType')} - {event.get('name')}",
                start_date_range=start_date,
                end_date_range=end_date,
                start_time=start_time,
                end_time=end_time,
                penalty=penalty,
                production_value=int(event.get('ProductionAmount') * 100),
                latitude=event.get('lat'),
                longitude=event.get('lng'),
                address="",
                minimum_duration=min_duration,
                allowed_vehicle_ids=allowed_vehicle_ids,
                preferred_vehicle_ids=preferred_vehicle_ids,
                excluded_date_times=excluded_date_times,
                allowed_dates=allowed_dates,
            )
        )
    error_eve_list, error_message_list = work_orders_validation(single_day_work_orders, blk_intervals, vehicles,
                                                                date_range, error_message_list)
    # single_day_df = pd.DataFrame(single_day_work_orders).sort_values(by=[4, 3])
    error_eve_list.extend(tech_not_available)

    return stops, error_eve_list, error_message_list,  tech_not_available


def convert_vehicles_to_nodes(vehicles: list[Vehicle]) -> list[Node]:
    """Converts a list of vehicles to a list of nodes"""
    nodes: list[Node] = []
    for vehicle in vehicles:
        # log_debug(f"vehicle: {vehicle.name}")
        nodes.append(
            Node(
                id=vehicle.id,
                node_type=vehicle.node_type,
                name=f"{vehicle.name}'s ${vehicle.node_type}",
                start_time=vehicle.start_time,
                end_time=vehicle.end_time,
                penalty=0,
                production_value=0,
                latitude=vehicle.latitude,
                longitude=vehicle.longitude,
                address=vehicle.address,
            )
        )
    return nodes


def create_route_data(work_order_details, date_range, block_time, skills_df, tech_df, req, config):
    """Creates a Data object from the RoutingRequest object"""
    vehicles, blk_intervals = create_vehicles(block_time, skills_df, tech_df, date_range, config.api_key)

    error_eve_list = []
    error_message_list = []
    # Exception : If user trying to schedule anything in block time raise exception.
    for brk in blk_intervals:
        for event in work_order_details.to_dict("records"):

            if not event.get('lockTime'):
                continue

            schedule_time = event.get('ScheduleTime')
            event_date = event.get('eventDate')

            if schedule_time is None or event_date is None:
                continue

            # combine date + time safely
            lock_dt = pd.Timestamp(event_date).replace(
                hour=schedule_time.hour,
                minute=schedule_time.minute,
                second=0
            )

            lock_date_time_in_min = (
                                            lock_dt - date_range[0]
                                    ).total_seconds() / 60

            if int(brk.start_time) <= lock_date_time_in_min < int(brk.end_time):

                if event.get('name') == 'BlockTime-Meeting':
                    continue

                eve_name = event.get('name') or event.get('eventId')

                logger.info(f"Locked event conflicts with break: {eve_name}")

                error_eve_list.append(event.get('eventId'))

    # calculate the number of days
    number_of_days = len(date_range)
    logger.info(f"number_of_days: {number_of_days}")

    stops, errors, error_message_list, tech_not_available = create_stops(work_order_details, config, vehicles, blk_intervals,
                                                     error_message_list, req, date_range,
                                                     tech_df,  skills_df)

    # create nodes by converting vehicles to nodes and appending stops
    nodes: list[Node] = convert_vehicles_to_nodes(vehicles)
    nodes.extend(stops)

    # add the index of each vehicle as a start and end index
    start_indexes = []
    end_indexes = []
    for i in range(len(vehicles)):
        start_indexes.append(i)
        end_indexes.append(i)

    return Data(
        date_range=date_range,
        number_of_days=number_of_days,
        vehicles=vehicles,
        stops=stops,
        nodes=nodes,
        start_indexes=start_indexes,
        end_indexes=end_indexes,
    ), error_eve_list + errors, error_message_list
