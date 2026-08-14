from datetime import datetime, timedelta
from src.Utils.log import logger
import pandas as pd


def validate_event(work_order_details, tech_df, block_time, config, req, date_range):
    date_range = pd.to_datetime(date_range)
    loc_list = []
    time_err = []
    # date_error = []
    lock_time_error = []
    # constraint_error = []
    lock_time_error_or = []
    # missing_information = []

    # Fill empty/null names with corresponding eventId
    work_order_details['name'] = (
        work_order_details['name']
        .replace(r'^\s*$', pd.NA, regex=True)
        .fillna(work_order_details['eventId'])
        .astype(str)
    )

    # Invalid lat/lng validation
    invalid_values = ['', '0', '0.0', '00.00']

    loc_mask = (
            work_order_details['lat'].isna() |
            work_order_details['lng'].isna() |
            work_order_details['lat'].astype(str).str.strip().isin(invalid_values) |
            work_order_details['lng'].astype(str).str.strip().isin(invalid_values)
    )

    loc_list.extend(
        work_order_details.loc[loc_mask, 'name'].unique()
    )

    # Invalid service time range
    time_mask = (
            work_order_details['ServiceStartStartTime'].notna() &
            work_order_details['ServiceStartEndTime'].notna() &
            (
                    work_order_details['ServiceStartStartTime'] >
                    work_order_details['ServiceStartEndTime']
            )
    )

    time_err.extend(
        work_order_details.loc[time_mask, 'name'].unique()
    )

    # Locked events outside allowed date range
    lock_time_mask = (
            work_order_details['lockTime'] &
            (
                    (work_order_details['eventDate'] > date_range[-1]) |
                    (work_order_details['eventDate'] < date_range[0])
            )
    )

    lock_time_error_or.extend(
        work_order_details.loc[lock_time_mask, 'name'].unique()
    )

    try:
        # -------------------------------
        # STEP 0: Helper (VERY IMPORTANT)
        # -------------------------------
        def normalize_time(col):
            return pd.to_datetime(
                '1970-01-01 ' + col.astype(str).str.strip(),
                errors='coerce',
                format='mixed'  # pandas >= 2.0
            )

        # -------------------------------
        # STEP 1: Normalize work order data
        # -------------------------------

        # Convert schedule time safely
        work_order_details['start_dt'] = normalize_time(work_order_details['ServiceStartStartTime'])

        work_order_details['schedule_time_dt'] = normalize_time(work_order_details['ScheduleTime'])

        # Duration → numeric (safe)
        work_order_details['duration'] = pd.to_numeric(
            work_order_details['duration'], errors='coerce'
        ).fillna(0)

        # Compute end time
        work_order_details['end_dt'] = normalize_time(work_order_details['ServiceStartEndTime'])

        # Event day
        work_order_details['event_day'] = (
            pd.to_datetime(work_order_details['eventDate'], errors='coerce')
            .dt.day_name()
            .str.lower()
        )

        # -------------------------------
        # STEP 2: Normalize technician data
        # -------------------------------

        tech_df['WeekId'] = tech_df['WeekId'].astype(str).str.lower()

        tech_df['in_dt'] = normalize_time(tech_df['InTime'])
        tech_df['out_dt'] = normalize_time(tech_df['ArriveAtLastJobNoLaterThan'])

        # -------------------------------
        # STEP 3: Merge on day
        # -------------------------------

        merged = work_order_details.merge(
            tech_df,
            left_on='event_day',
            right_on='WeekId',
            how='left'
        )

        [[
            'lockTime',
            'lockTech',
            'in_dt',
            'out_dt',
            'schedule_time_dt',
            'userPreferredTechnicianId',
            'EmployeeId',
            'start_dt',
            'end_dt',
            'name'
        ]]

        # -------------------------------
        # STEP 4: Feasibility condition
        # -------------------------------

        # LockTime + LockTech
        mask1 = (
                merged['lockTime'] &
                merged['lockTech'] &
                (merged['in_dt'] <= merged['schedule_time_dt']) &
                (merged['schedule_time_dt'] <= merged['out_dt']) &
                (merged['userPreferredTechnicianId'] == merged['EmployeeNo']) &
                (merged['start_dt'] <= merged['schedule_time_dt']) &
                (merged['schedule_time_dt'] <= merged['end_dt'])
        )

        # LockTime + NOT LockTech
        mask2 = (
                merged['lockTime'] &
                ~merged['lockTech'] &
                (merged['in_dt'] <= merged['schedule_time_dt']) &
                (merged['schedule_time_dt'] <= merged['out_dt']) &
                (merged['start_dt'] <= merged['schedule_time_dt']) &
                (merged['schedule_time_dt'] <= merged['end_dt'])
        )

        # NOT LockTime + LockTech
        mask3 = (
                ~merged['lockTime'] &
                merged['lockTech'] &
                (merged['userPreferredTechnicianId'] == merged['EmployeeNo']) &
                (merged['start_dt'] < merged['out_dt']) &
                (merged['end_dt'] > merged['in_dt'])
        )

        # NOT LockTime + NOT LockTech
        mask4 = (
                ~merged['lockTime'] &
                ~merged['lockTech'] &
                (merged['start_dt'] < merged['out_dt']) &
                (merged['end_dt'] > merged['in_dt'])

        )

        valid_mask = mask1 | mask2 | mask3 | mask4

        valid_events = (
            merged.loc[valid_mask, 'name']
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        lock_time_error.extend(
            merged[~merged['name'].isin(valid_events)]
            ['name']
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        # merged['is_valid'] = (
        #         merged['in_dt'].notna() &
        #         merged['out_dt'].notna() &
        #         merged['start_dt'].notna() &
        #         merged['end_dt'].notna() &
        #         (merged['in_dt'] <= merged['start_dt']) &
        #         (merged['out_dt'] >= merged['end_dt'])
        # )
        #
        # # -------------------------------
        # # STEP 5: Preferred technician logic
        # # -------------------------------
        #
        # preferred_valid = merged[
        #     (merged['lockTech'] == True) &
        #     (merged['EmployeeId'] == merged['userPreferredTechnicianId']) &
        #     (merged['is_valid'])
        #     ]
        #
        # any_valid = merged[merged['is_valid']]
        #
        # # -------------------------------
        # # STEP 6: LOCK TIME ERRORS
        # # -------------------------------
        #
        # lock_events = work_order_details[work_order_details['lockTime'] == True]
        #
        # valid_pref = set(preferred_valid['name'])
        # valid_any = set(any_valid['name'])
        #
        # valid_events = valid_pref | valid_any
        #
        # lock_time_error = (
        #     lock_events[~lock_events['name'].isin(valid_events)]
        #     ['name']
        #     .dropna()
        #     .astype(str)
        #     .unique()
        #     .tolist()
        # )
        #
        # # -------------------------------
        # # STEP 7: NON-LOCK CONSTRAINT ERRORS
        # # -------------------------------
        #
        # non_lock_events = work_order_details[work_order_details['lockTime'] == False]
        #
        # valid_all = set(any_valid['name'])
        #
        # constraint_error = (
        #     non_lock_events[~non_lock_events['name'].isin(valid_all)]
        #     ['name']
        #     .dropna()
        #     .astype(str)
        #     .unique()
        #     .tolist()
        # )
        #
        # # -------------------------------
        # # STEP 8: (Optional but recommended)
        # # Deduplicate
        # # -------------------------------
        # lock_time_error = list(set(lock_time_error))
        # constraint_error = list(set(constraint_error))

    except Exception as e:
        print("ERROR:", e)

    error_message_list = []
    if len(lock_time_error_or):
        error_message_list.append(f"""Event is locked outside the optimization range: {','.join(lock_time_error_or)}""")

    if len(lock_time_error):
        error_message_list.append(f"""Technicians is unavailable for event: {','.join(lock_time_error)}""")

    if len(loc_list):
        error_message_list.append(f"""Invalid location for event: {','.join(loc_list)}""")

    if len(time_err):
        error_message_list.append(f"""Invalid timeRange constraints for Event: {','.join(time_err)}""")

    # if len(date_error):
    #     error_message_list.append(f"""Invalid dateRange constraints for Event: {','.join(date_error)}""")
    #
    # if len(constraint_error):
    #     error_message_list.append(f"""Technicians is unavailable for Event: {','.join(constraint_error)}""")
    #
    # if len(missing_information):
    #     error_message_list.append(f"""Incomplete information in work order: {','.join(missing_information)} """)

    error_id_lst = loc_list + time_err + lock_time_error + lock_time_error_or
    return error_id_lst, error_message_list


def work_orders_validation(single_day_work_orders, blk_intervals, vehicles, date_range, error_message_list):
    list_of_conflicts_with_tech_time = set()
    list_of_conflicts_with_tech_stops = set()
    list_of_conflicts_with_block_time = set()

    for single_day_work_order in single_day_work_orders:
        # Parse start and end lock times
        start_lock_date_time = f"{single_day_work_order[-2]} {single_day_work_order[2]}"
        end_lock_date_time = f"{single_day_work_order[-1]} {single_day_work_order[3]}"

        start_lock_date_time_in_min = (pd.to_datetime(start_lock_date_time) - date_range[0]).total_seconds() / 60
        end_lock_date_time_in_min = (pd.to_datetime(end_lock_date_time) - date_range[0]).total_seconds() / 60

        vech_index = (pd.to_datetime(end_lock_date_time) - date_range[0]).days

        # Check for time range conflicts
        if start_lock_date_time_in_min < 1 and end_lock_date_time_in_min < 1:
            list_of_conflicts_with_tech_time.add(single_day_work_order[0])
            continue  # Skip further checks for this work order

        try:
            vehicle = vehicles[vech_index]
        except IndexError:
            list_of_conflicts_with_tech_time.add(single_day_work_order[0])
            continue

        # Check technician availability and constraints
        if (
                start_lock_date_time_in_min < vehicle.start_time
                and end_lock_date_time_in_min < vehicle.start_time
        ) or (
                start_lock_date_time_in_min > vehicle.end_time
                and end_lock_date_time_in_min > vehicle.end_time
        ):
            list_of_conflicts_with_tech_time.add(single_day_work_order[0])

        if vehicle.max_number_of_stops < 1:
            list_of_conflicts_with_tech_stops.add(single_day_work_order[0])
        if vehicle.max_travel_time < 1:
            list_of_conflicts_with_tech_stops.add(single_day_work_order[0])
        if vehicle.max_drive_time < 1:
            list_of_conflicts_with_tech_stops.add(single_day_work_order[0])
        if vehicle.max_service_duration < 1:
            list_of_conflicts_with_tech_stops.add(single_day_work_order[0])
        if vehicle.max_production_value < 1:
            list_of_conflicts_with_tech_stops.add(single_day_work_order[0])

        # Check for block time conflicts
        for brk in blk_intervals:
            if (
                    int(start_lock_date_time_in_min) in range(brk.start_time - 1, brk.end_time + 1)
                    and int(end_lock_date_time_in_min) in range(brk.start_time - 1, brk.end_time + 1)
            ):
                list_of_conflicts_with_block_time.add(single_day_work_order[0])

    # Raise exceptions for conflicts
    errors = []
    if list_of_conflicts_with_tech_time:
        errors.append(f"Technician is not available for work orders: {', '.join(list_of_conflicts_with_tech_time)}")
    if list_of_conflicts_with_tech_stops:
        errors.append(
            f"Technician constraints violated for work orders: {', '.join(list_of_conflicts_with_tech_stops)}")
    if list_of_conflicts_with_block_time:
        errors.append(f"Work orders conflict with block times: {', '.join(list_of_conflicts_with_block_time)}")

    if errors:
        print("\n".join(errors))
        error_message_list.extend(errors)

    return list(list_of_conflicts_with_tech_time) + list(list_of_conflicts_with_tech_stops) + list(
        list_of_conflicts_with_block_time), error_message_list
