from collections import defaultdict
import pandas as pd
from src.Mongo_Manager.schemas.beta.bestfit_schema import *
from datetime import time, timedelta
from datetime import date
from calendar import monthrange
from src.Utils.config import GlobalConfig

# ==========================================
# FAST FORMATTERS
# ==========================================

DATE_FMT = "%m/%d/%Y"
DATETIME_FMT = "%m/%d/%Y %H:%M"


def normalize_number(value):
    value = float(f"{value:g}")
    return int(value) if value.is_integer() else value


def time_to_minutes(t):
    if pd.isna(t):
        return "00"

    if isinstance(t, str):
        h, m, s = map(int, t.split(":"))

        return '00' if str(h * 60 + m) == '0' else str(h * 60 + m)

    if isinstance(t, time):
        return '00' if str(t.hour * 60 + t.minute) == '0' else str(t.hour * 60 + t.minute)

    return "00"


def duration_to_minutes(value):
    if pd.isna(value):
        return "00"

    # timedelta
    if isinstance(value, timedelta):
        return str(int(value.total_seconds() // 60))

    # datetime.time
    if isinstance(value, time):
        return str(value.hour * 60 + value.minute)

    # string like "00:30" or "01:30:00"
    if isinstance(value, str):

        parts = value.split(":")

        if len(parts) >= 2:
            hours = int(parts[0])
            minutes = int(parts[1])

            return str(hours * 60 + minutes)

    # numeric
    return str(int(value))


def fmt_date(v):
    if pd.isna(v):
        return None
    return pd.Timestamp(v).strftime(DATE_FMT)


def fmt_datetime(v):
    if pd.isna(v):
        return None
    return pd.Timestamp(v).strftime(DATETIME_FMT)


def fmt_time(v):
    if pd.isna(v):
        return "00:00"

    if isinstance(v, str):
        return v[:5]

    return v.strftime("%H:%M")


# ==========================================
# SKILL MAP
# ==========================================

def create_skill_map(skills_df):
    skill_map = defaultdict(list)
    if skills_df.empty:
        return skill_map

    for row in skills_df.to_dict("records"):
        employee_no = str(row["EmployeeNo"])

        categories = [
            cat.strip()
            for cat in str(row.get("serviceSysName")).split(",")
            if cat.strip()
        ]

        for category in categories:
            skill_map[employee_no].append(
                Skill(
                    skillName=row.get("skillName"),
                    proficiency=int(row.get("proficiency", 0) or 0),
                    serviceSysName=category
                )
            )
    return skill_map

    #


# ==========================================
# BLOCK MAP
# ==========================================

def create_block_map(block_time_df):
    block_map = defaultdict(list)
    if block_time_df.empty:
        return block_map
    for row in block_time_df.to_dict("records"):
        employee_no = str(row["EmployeeNo"])

        block_map[employee_no].append(
            DateTimeRange(
                startDateTime=fmt_datetime(row["FromDate"]),
                endDateTime=fmt_datetime(row["ToDate"]),
                blockLocation=BlockLocation(
                    lat=row.get("Latitude"),
                    lon=row.get("Longitude")
                )
            )
        )
    return block_map

    #
    # for row in block_time_df.to_dict("records"):
    #
    #     employee_no = str(row["EmployeeNo"])
    #
    #     block_map[employee_no].append(
    #         DateTimeRange(
    #             startDateTime=fmt_datetime(row["startDateTime"]),
    #             endDateTime=fmt_datetime(row["endDateTime"]),
    #             blockLocation=BlockLocation(
    #                 lat=row.get("lat"),
    #                 lon=row.get("lon")
    #             )
    #         )
    #     )


# ==========================================
# TIME FORMATTER
# ==========================================

def fmt_time(v):
    if pd.isna(v):
        return "00:00"

    if isinstance(v, str):
        return v[:5]

    return v.strftime("%H:%M")


# ==========================================
# WEEKDAY MAP
# ==========================================

DAY_MAP = {
    "monday": DayOfTheWeek.Monday,
    "tuesday": DayOfTheWeek.Tuesday,
    "wednesday": DayOfTheWeek.Wednesday,
    "thursday": DayOfTheWeek.Thursday,
    "friday": DayOfTheWeek.Friday,
    "saturday": DayOfTheWeek.Saturday,
    "sunday": DayOfTheWeek.Sunday,
}


# ==========================================
# CREATE TECHNICIANS
# ==========================================

def create_technicians(
        tech_df,
        skill_map,
        block_map,
        req,
        config
):
    technicians = []
    # FASTEST GROUPING
    grouped = tech_df.groupby("EmployeeNo")
    for employee_no, group in grouped:
        rows = group.to_dict("records")
        schedules = []
        # CREATE ALL WEEKDAY SCHEDULES
        weekday_order = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        rows.sort(key=lambda x: weekday_order.index(x['WeekId']))

        for row in rows:
            if row.get('DayStartLocation') == 'Home':
                type_ = LocationType.HOME
            elif row.get('DayStartLocation') == 'FirstJob':
                type_ = LocationType.FIRST_JOB
            elif row.get('DayStartLocation') == 'LastJob':
                type_ = LocationType.LAST_JOB
            elif row.get('DayStartLocation') == 'Office':
                type_ = LocationType.OFFICE

            schedule = DaySchedule(
                day=DAY_MAP[
                    row["WeekId"].lower()
                ],
                inTime=fmt_time(
                    row["InTime"]
                ),
                lastStartTime=fmt_time(
                    row["ArriveAtLastJobNoLaterThan"]
                ),
                lastEndTime=fmt_time(
                    row["EndLastJobNoLaterThan"]
                ),
                earliestLunchTime=fmt_time(
                    row["EarliestLunchTime"]
                ),
                latestLunchTime=fmt_time(
                    row["LatestLunchTime"]
                ),
                lunchDuration=time_to_minutes(
                    row["LunchDuration"]
                ),

                maxServiceDuration=time_to_minutes(
                    row["MaxServiceDuration"]
                ),

                maxTotalDayDuration=time_to_minutes(
                    row["MaxTotalDayDuration"]
                ),

                maxDriveTime=time_to_minutes(
                    row["MaxDriveTime"]
                ),
                maxProductionValue=normalize_number(
                    row.get(
                        "MaxProductionValue",
                        999999
                    )
                ),
                maxNoOfJobs=int(
                    row.get(
                        "MaxNoOfJobs",
                        100
                    )
                ),
                dayStartLocation=Location(
                    type=type_,
                    lat=float(row["Latitude"]),
                    lon=float(row["Longitude"])
                )
            )
            schedules.append(schedule)
        # FIRST ROW FOR STATIC TECH DATA
        first_row = rows[0]
        if first_row.get("driving_mode").lower() == 'average':
            driving_mode = ''
        else:
            driving_mode = first_row.get("driving_mode").lower()

        if first_row.get('attributes_id'):
            attributes = first_row.get('attributes_id').split(',')
        else:
            attributes = []

        if first_row.get('PropertyType'):
            PropertyType = first_row.get('PropertyType').split(',')
        else:
            PropertyType = []

        # zip_codes = first_row.get('ZipCodes') or []
        #
        # print("========== BEFORE TECHNICIAN ==========")
        # print("Employee:", employee_no)
        # print("zip_codes VALUE:", zip_codes)
        # print("zip_codes TYPE:", type(zip_codes))
        #
        # zip_codes = first_row.get('ZipCodes')
        #
        # if zip_codes is None:
        #     zip_codes = []
        # elif isinstance(zip_codes, str):
        #     zip_codes = [
        #         int(x.strip())
        #         for x in zip_codes.split(',')
        #         if x.strip()
        #     ]

        zip_codes_value = first_row.get('ZipCodes')

        if pd.isna(zip_codes_value):
            zip_codes = []
        elif isinstance(zip_codes_value, list):
            zip_codes = zip_codes_value
        else:
            zip_codes = [z.strip() for z in str(zip_codes_value).split(',')]

        technician = Technician(
            id=str(employee_no),
            isEmployeeGeoFencing=config.IsEnableRoGeofencing,
            variation_percent=first_row.get("variation_percent"),
            driving_mode=driving_mode,
            name=str(row['FullName']),
            schedule=schedules,
            skills=skill_map.get(
                str(employee_no),
                []
            ),
            blockTimes=block_map.get(
                str(employee_no),
                []
            ),
            attribute = attributes,
            branch_ids= first_row.get('BranchMasterId'),
            zip_codes = zip_codes,
            property_type = PropertyType

        )
        technicians.append(technician)
    return technicians


# ==========================================
# EVENTS
# ==========================================

def create_events(work_order_details, date_range, req,
                  config, tech_df):
    year = date_range[0].year
    month = date_range[0].month

    first_day_of_month = date(year, month, 1)
    last_day_of_month = date(year, month, monthrange(year, month)[1])

    events = []

    wo_records = work_order_details.to_dict("records")

    for row in wo_records:
        if row["eventType"] == 'BlockTime':
            continue

        try:
            eventDate_ = row.get('eventDate')
            year = eventDate_.year
            month = eventDate_.month
            first_day_of_month = date(year, month, 1)
            last_day_of_month = date(year, month, monthrange(year, month)[1])
        except:
            year = date_range[0].year
            month = date_range[0].month
            first_day_of_month = date(year, month, 1)
            last_day_of_month = date(year, month, monthrange(year, month)[1])

        eligible_from = row.get("EligibleDaysFrom")
        eligible_to = row.get("EligibleDaysTo")

        if pd.notna(eligible_from) and pd.notna(eligible_to):
            ed = EligibleDate(
                from_date=int(eligible_from),
                to_date=int(eligible_to)
            )
        else:
            ed = None

        inbound_emp = row.get("inBoundEmployeeNo")

        if inbound_emp is None or (not isinstance(inbound_emp, list) and pd.isna(inbound_emp)):
            inbound_emp = []

        elif isinstance(inbound_emp, str):
            inbound_emp = [
                x.strip()
                for x in inbound_emp.split(",")
                if x.strip()
            ]

        if row["eventType"] == "ServiceOrder":
            e_type = "WorkOrder"
        else:
            e_type = row["eventType"]

        if not pd.isna(row.get('ServicesAttribute')):
            ServicesAttribute = row.get('ServicesAttribute').split(', ')
        else:
            ServicesAttribute = []

        if not pd.isna(row.get('PropertyType')):
            PropertyType = row.get('PropertyType')
        else:
            PropertyType = None



        event = Event(

            eventId=str(row["eventId"]),

            name=row.get("name"),

            eventType=e_type,

            accountNumber=None if str(row["eventId"]) == '0' else str(
                row.get("AccountNumber", "")
            ),

            eventDate=fmt_date(
                eventDate_
            ),

            scheduleTime=fmt_time(
                row.get("ScheduleTime")
            ),

            lat=float(row["lat"]),

            lon=float(row["lng"]),

            productionValue=normalize_number(
                row.get("ProductionAmount", 0)
            ),

            duration=duration_to_minutes(
                row.get("duration", 0)
            ),

            lockTime=bool(
                row.get("lockTime", False)
            ),

            lockTech=bool(
                row.get("lockTech", False)
            ),

            route=row.get('InitialRouteNo'),

            zip_code = row.get('Zipcode'),

            branch_id = int(row.get('branchId')) if row.get('branchId') else None ,

            property_type = PropertyType,

            attribute = ServicesAttribute,

            skills=[Skill(
                skillName=row.get("skillName"),
                proficiency=int(row.get("proficiency", 0) or 0),
                serviceSysName=i
            ) for i in row.get("serviceSysName").split(', ')]
            ,

            constraints=Constraints(

                timeRange=TimeRange(
                    startTime=fmt_time(
                        row.get("ServiceStartStartTime")
                    ) or "00:00",
                    endTime=fmt_time(
                        row.get("ServiceStartEndTime")
                    ) or "23:59"
                ),

                dateRange=DateRange(
                    startDate=fmt_date(
                        row.get("EarliestServiceDate")
                        if pd.notna(row.get("EarliestServiceDate"))
                        else first_day_of_month
                    ),
                    endDate=fmt_date(
                        row.get("LatestServiceDate")
                        if pd.notna(row.get("LatestServiceDate"))
                        else last_day_of_month
                    )
                ),

                userPreferredTechnicianId=str(
                    row.get(
                        "userPreferredTechnicianId",
                        ""
                    )
                )
                ,
                inBoundEmployeeNo=inbound_emp
            ),
            eligible_days=row.get("EligibleDaysOfWeek") if len(row.get("EligibleDaysOfWeek")) else None,
            eligible_months=ed
        )

        events.append(event)

    return events


# ==========================================
# FINAL ROUTING REQUEST
# ==========================================

def create_routing_request(
        work_order_details,
        tech_df,
        skills_df,
        block_time_df,
        req,
        start_date,
        end_date, config, date_range
):
    # PREBUILD LOOKUP MAPS
    skill_map = create_skill_map(skills_df)

    block_map = create_block_map(block_time_df)

    # BUILD OBJECTS
    technicians = create_technicians(
        tech_df,
        skill_map,
        block_map,
        req,
        config
    )

    events = create_events(
        work_order_details, date_range, req,
        config, tech_df
    )
    # FINAL OBJECT
    return RoutingRequest(
        techniciansList=technicians,
        eventList=events,
        distanceCalculationSettings=DistanceCalculationSettings(
            distanceCalculationType=1,
            apiKey=GlobalConfig.UNIVERSAL_KEY
        ),
        optimizeDatesRange=DateRange(
            startDate=date_range[0].date().strftime("%m/%d/%Y"),
            endDate=date_range[-1].date().strftime("%m/%d/%Y")
        ),
        considerSkill=config.ConsiderSkillInRouteOptimization,
        considerDriveTime=config.considerDriveTime,
        minServiceDuration="0",
        keepWorkDate=True,
        keepWorkTech=True,
        clientID="",  # req.CompanyKey,
        userID=req.User,
        allowStartDate="",
        allowEndDate="",
        isGeoFenced = config.IsEnableRoGeofencing,
        considerZipCode = config.considerZipCode,
        considerBranch = config.considerBranch,
        IsPropertyTypeInRO = config.IsPropertyTypeInRO
    )
