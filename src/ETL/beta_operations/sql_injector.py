import random
import numpy as np
from src.SQL_Manger.db_operations.db_manager import (
    insert_into_db,
    fetch_data_from_db
)
import pandas as pd
import json
from datetime import datetime
from src.Mongo_Manager.schemas.beta.bestfit_schema  import (
    BetaBestFitResponse
)


def ensure_columns(df, columns):

    """
    Ensure dataframe always has required columns.
    """

    if df is None or df.empty:
        return pd.DataFrame(columns=columns)

    for col in columns:
        if col not in df.columns:
            df[col] = None

    return df


def fill_optimization_masters(
        work_order_details,
        startDate_str,
        endDate_str,
        block_time,
        skills_df,
        tech_df,
        requestId,
        routingResponse,
        list_of_errors,
        req,
        rr,
        original_block_time_df
):

    # =========================================================
    # SAFE INPUT DATAFRAMES
    # =========================================================

    work_order_columns = [
        'Services',
        'StatusSysName',
        'Address1',
        'Address2',
        'CityName',
        'Zipcode',
        'Statename',
        'CountryName',
        'InitialRouteNo',
        'ParentEntityId',
        'eventId',
        'name',
        'eventDate',
        'ScheduleTime',
        'duration',
        'ServiceStartStartTime',
        'ServiceStartEndTime',
        'EarliestServiceDate',
        'LatestServiceDate',
        'userPreferredTechnicianId',
        'lat',
        'lng',
        'DriveTime',
        'eventType',
        'routenotusing',
        'RouteName'
    ]

    tech_columns = [
        'EmployeeNo',
        'WeekId',
        'EarliestLunchTime',
        'FirstName',
        'MiddleName',
        'LastName',
        'FullName',
        'EmployeeId'
    ]

    work_order_details = ensure_columns(
        work_order_details,
        work_order_columns
    )

    tech_df = ensure_columns(
        tech_df,
        tech_columns
    )

    block_time = ensure_columns(
        block_time,
        ['EmployeeNo']
    )

    skills_df = ensure_columns(
        skills_df,
        []
    )

    # =========================================================
    # ASSIGNED EVENTS
    # =========================================================

    assigned_columns = [
        "EntityId",
        "EntityNo",
        "SuggestedScheduleDate",
        "SuggestedScheduleTime",
        "EstimationDurationInMin",
        "EntityType",
        "initialTechnicianNo",
        "SuggestedTechnicianNo",
        "eventDay",
        "SuggestedDriveTime",
    ]

    assigned_df = pd.DataFrame.from_records(
        (
            {
                "EntityId": e.eventId,
                "EntityNo": e.eventName,
                "SuggestedScheduleDate": e.eventDate,
                "SuggestedScheduleTime": e.scheduleTime,
                "EstimationDurationInMin": e.duration,
                "EntityType": e.eventType,
                "initialTechnicianNo": e.technicianId,
                "SuggestedTechnicianNo": e.technicianId,
                "eventDay": e.eventDay,
                "SuggestedDriveTime": (
                    e.eventRouteDistance.driveTime
                    if e.eventRouteDistance
                    else None
                ),
            }
            for e in routingResponse.assignedEventList
        )
    )

    if assigned_df.empty:
        assigned_df = pd.DataFrame(columns=assigned_columns)

    assigned_ro_detail = assigned_df.loc[
        assigned_df["EntityType"].isin(
            ["WorkOrder", "BlockTime", "lunchEvent","CallBack","SubWorkOrder"]
        )
    ].copy()

    if not assigned_ro_detail.empty:

        assigned_ro_detail.loc[
            assigned_ro_detail["EntityType"] == "lunchEvent",
            "EntityType",
        ] = "LunchEvent"

    assigned_ro_detail["IsAssigned"] = 1

    # =========================================================
    # UNASSIGNED EVENTS
    # =========================================================

    unassigned_columns = [
        "EntityId",
        "EntityNo",
        "SuggestedScheduleDate",
        "SuggestedScheduleTime",
        "EstimationDurationInMin",
        "EntityType",
        "initialTechnicianNo",
        "SuggestedTechnicianNo",
    ]

    unassigned_ro_detail = pd.DataFrame.from_records(
        (
            {
                "EntityId": e.eventId,
                "EntityNo": e.name,
                "SuggestedScheduleDate": e.eventDate,
                "SuggestedScheduleTime": None,
                "EstimationDurationInMin": 0,
                "EntityType": e.eventType,
                "initialTechnicianNo": (
                    e.constraints.userPreferredTechnicianId
                    if e.constraints
                    else None
                ),
                "SuggestedTechnicianNo": (
                    e.constraints.userPreferredTechnicianId
                    if e.constraints
                    else None
                ),
            }
            for e in routingResponse.unassignedEventList
        )
    )

    if unassigned_ro_detail.empty:
        unassigned_ro_detail = pd.DataFrame(
            columns=unassigned_columns
        )

    unassigned_ro_detail["IsAssigned"] = 0
    unassigned_ro_detail["eventDay"] = None
    unassigned_ro_detail["SuggestedDriveTime"] = None

    # =========================================================
    # COMBINE
    # =========================================================

    dfs_to_concat = [
        df for df in [
            assigned_ro_detail,
            unassigned_ro_detail
        ]
        if df is not None
    ]

    if dfs_to_concat:
        ro_details = pd.concat(
            dfs_to_concat,
            ignore_index=True,
        )
    else:
        ro_details = pd.DataFrame()

    ro_details = ro_details[~(ro_details['EntityType']=='BlockTime')]
    if not original_block_time_df.empty:
        #ADDING MISSED OVERLAPPED BLOCKTime
        original_block_time_df['blockDate'] = pd.to_datetime(original_block_time_df['blockDate'])
        original_block_time_df['EntityId'] = str('lt') + np.random.choice(
            np.arange(10000, 99999),
            size=original_block_time_df.shape[0],
            replace=False
        ).astype(str)

        remaining_blk_to_be_inserted_df = original_block_time_df.copy()

        remaining_blk_to_be_inserted_df = remaining_blk_to_be_inserted_df.assign(
            EntityId=remaining_blk_to_be_inserted_df['EntityId'],
            EntityNo='BlockTime-Meeting',
            SuggestedScheduleDate=remaining_blk_to_be_inserted_df['blockDate'],
            SuggestedScheduleTime=remaining_blk_to_be_inserted_df['FromDate'].dt.time,
            EstimationDurationInMin=(
                (
                        remaining_blk_to_be_inserted_df['ToDate']
                        - remaining_blk_to_be_inserted_df['FromDate']
                )
                .dt.total_seconds()
                .floordiv(60)
                .astype(int)
            ),
            EntityType='BlockTime',
            initialTechnicianNo=remaining_blk_to_be_inserted_df['EmployeeNo'],
            SuggestedTechnicianNo=remaining_blk_to_be_inserted_df['EmployeeNo'],
            eventDay=remaining_blk_to_be_inserted_df['blockDate']
            .dt.day_name()
            .str.lower(),
            SuggestedDriveTime=None,
            IsAssigned=1
        )
        missing_cols = set(ro_details.columns) - set(remaining_blk_to_be_inserted_df.columns)

        for col in missing_cols:
            remaining_blk_to_be_inserted_df[col] = None

        remaining_blk_to_be_inserted_df = remaining_blk_to_be_inserted_df[
            ro_details.columns
        ]

        ro_details = pd.concat(
            [ro_details, remaining_blk_to_be_inserted_df],
            ignore_index=True
        )

    # =========================================================
    # WORK ORDER DATA
    # =========================================================

    wo_ds = work_order_details[
        [
            'Services',
            'StatusSysName',
            'Address1',
            'Address2',
            'CityName',
            'Zipcode',
            'Statename',
            'CountryName',
            'InitialRouteNo',
            'ParentEntityId',
            'eventId',
            'name',
            'eventDate',
            'ScheduleTime',
            'duration',
            'ServiceStartStartTime',
            'ServiceStartEndTime',
            'EarliestServiceDate',
            'LatestServiceDate',
            'userPreferredTechnicianId',
            'lat',
            'lng',
            'DriveTime'
        ]
    ].copy()

    # =========================================================
    # TYPE FIXES
    # =========================================================

    if not ro_details.empty:

        ro_details['EntityId'] = (
            ro_details['EntityId']
            .astype(str)
        )

    if not wo_ds.empty:

        wo_ds['eventId'] = (
            wo_ds['eventId']
            .astype(str)
        )

    ro_details['SuggestedScheduleDate'] = pd.to_datetime(
        ro_details['SuggestedScheduleDate'],
        errors='coerce'
    ).dt.normalize()

    wo_ds['eventDate'] = pd.to_datetime(
        wo_ds['eventDate'],
        errors='coerce'
    ).dt.normalize()

    # =========================================================
    # MERGE
    # =========================================================

    merged_df = (
        ro_details.merge(
            wo_ds,
            left_on=[
                'EntityId',
                'EntityNo',
                'SuggestedScheduleDate',
                'initialTechnicianNo'
            ],
            right_on=[
                'eventId',
                'name',
                'eventDate',
                'userPreferredTechnicianId'
            ],
            how='left'
        )
        .drop(
            columns=[
                'eventId',
                'name',
                'userPreferredTechnicianId'
            ],
            errors='ignore'
        )
    )

    # =========================================================
    # RENAME
    # =========================================================

    merged_df.rename(
        columns={
            "ScheduleTime": "InitialScheduleTime",
            "ServiceStartStartTime": "EarliestStartTime",
            "ServiceStartEndTime": "LastStartTime",
            "lat": "Latitude",
            "lng": "Longitude",
            "eventDate": "InitialScheduleDate"
        },
        inplace=True
    )

    # =========================================================
    # SUB WORK ORDER HANDLING
    # =========================================================


    # =========================================================
    # UNASSIGNED DURATION
    # =========================================================

    mask_unassigned = merged_df['IsAssigned'].eq(0)

    merged_df.loc[
        mask_unassigned,
        'EstimationDurationInMin'
    ] = (
        pd.to_numeric(
            merged_df.loc[
                mask_unassigned,
                'duration'
            ],
            errors='coerce'
        )
        .fillna(0)
        .astype(int)
    )

    merged_df['IsActive'] = 1

    RouteOptimizationDetail = merged_df

    # =========================================================
    # LUNCH EVENT HANDLING
    # =========================================================

    mask_block = RouteOptimizationDetail['EntityType'].eq('BlockTime')
    if not original_block_time_df.empty:
        cols_to_fill = [
            'Address1',
            'Address2',
            'CityName',
            'Zipcode',
            'Statename',
            'Latitude',
            'Longitude'
        ]

        RouteOptimizationDetail.loc[mask_block, cols_to_fill] = (
            RouteOptimizationDetail.loc[mask_block, ['EntityId']]
            .merge(
                original_block_time_df[['EntityId'] + cols_to_fill],
                on='EntityId',
                how='left'
            )[cols_to_fill]
            .values
        )

    mask_lunch = RouteOptimizationDetail[
        'EntityType'
    ].eq('LunchEvent')

    RouteOptimizationDetail.loc[
        mask_lunch,
        'EntityNo'
    ] = RouteOptimizationDetail.loc[
        mask_lunch,
        'EntityId'
    ]

    if not tech_df.empty:

        lunch_map = tech_df.set_index(
            ['EmployeeNo', 'WeekId']
        )['EarliestLunchTime']

    else:

        lunch_map = pd.Series(dtype='object')

    RouteOptimizationDetail.loc[
        mask_lunch,
        'InitialScheduleTime'
    ] = (
        RouteOptimizationDetail.loc[mask_lunch]
        .set_index(
            ['initialTechnicianNo', 'eventDay']
        )
        .index
        .map(lunch_map)
    )

    mask_lunch_block = RouteOptimizationDetail[
        'EntityType'
    ].isin(['LunchEvent', 'BlockTime'])


    RouteOptimizationDetail.loc[
        mask_block, 'EntityNo'
    ] = np.random.choice(
        np.arange(10000, 99999),
        size=mask_block.sum(),
        replace=False
    ).astype(str)


    RouteOptimizationDetail.loc[
        mask_block,
        ['EarliestServiceDate','LatestServiceDate','EarliestStartTime','LastStartTime']
    ]= None

    RouteOptimizationDetail.loc[
        mask_block,
        'InitialScheduleTime'
    ] = RouteOptimizationDetail.loc[
        mask_block,
        'SuggestedScheduleTime'
    ]

    RouteOptimizationDetail.loc[
        mask_lunch_block,
        'InitialScheduleDate'
    ] = RouteOptimizationDetail.loc[
        mask_lunch_block,
        'SuggestedScheduleDate'
    ]

    mask_block_wo = RouteOptimizationDetail[
        'EntityType'
    ].isin(['BlockTime', 'WorkOrder','SubWorkOrder'])

    RouteOptimizationDetail.loc[
        mask_block_wo,
        'UserUpdatedScheduleDate'
    ] = RouteOptimizationDetail.loc[
        mask_block_wo,
        'InitialScheduleDate'
    ]

    RouteOptimizationDetail.loc[
        mask_block_wo,
        'UserUpdatedScheduleTime'
    ] = RouteOptimizationDetail.loc[
        mask_block_wo,
        'InitialScheduleTime'
    ]

    RouteOptimizationDetail.loc[
        mask_block_wo,
        'UserUpdatedTechnicianNo'
    ] = RouteOptimizationDetail.loc[
        mask_block_wo,
        'initialTechnicianNo'
    ]

    RouteOptimizationDetail['EntityId'] = (
        RouteOptimizationDetail['EntityId']
        .astype(str)
        .str.replace(
            r'^[A-Za-z]+',
            '',
            regex=True
        )
    )

    RouteOptimizationDetail['EntityId'] = pd.to_numeric(
        RouteOptimizationDetail['EntityId'],
        errors='coerce'
    )

    RouteOptimizationDetail = RouteOptimizationDetail[
        RouteOptimizationDetail['EntityId'].notna()
    ]

    RouteOptimizationDetail['EntityId'] = (
        RouteOptimizationDetail['EntityId']
        .astype(int)
    )

    wo_mask = RouteOptimizationDetail['EntityType'].eq('WorkOrder','SubWorkOrder')

    time_cols = [
        'DriveTime',
        'SuggestedDriveTime'
    ]

    for col in time_cols:
        # Replace blanks with NaN
        RouteOptimizationDetail[col] = (
            RouteOptimizationDetail[col]
            .replace(r'^\s*$', np.nan, regex=True)
        )

        # Convert to numeric minutes
        RouteOptimizationDetail[col] = pd.to_numeric(
            RouteOptimizationDetail[col],
            errors='coerce'
        )

        # Fill missing values for WorkOrders with 0 minutes
        RouteOptimizationDetail.loc[wo_mask, col] = (
            RouteOptimizationDetail.loc[wo_mask, col]
            .fillna(0)
        )

        # Convert minutes -> SQL TIME
        RouteOptimizationDetail[col] = (
                pd.Timestamp('1900-01-01')
                + pd.to_timedelta(RouteOptimizationDetail[col], unit='m')
        ).dt.time
    # =========================================================
    # DROP UNUSED COLUMNS
    # =========================================================

    RouteOptimizationDetail.drop(
        columns=[
            'duration',
            'eventDay'
        ],
        errors='ignore',
        inplace=True
    )

    # =========================================================
    # MASTER TABLE
    # =========================================================

    routing_request = json.dumps(
        rr.dict(),
        default=str
    )

    current_time = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S.%f"
    )[:-3]

    list_of_errors = [
        str(i)
        for i in list_of_errors
    ]

    if len(list_of_errors):

        Status = 3

        message = str(
            '\n'.join(list_of_errors)
        )

        bf_response = BetaBestFitResponse(
            assignedEventList=routingResponse.assignedEventList,
            unassignedEventList=routingResponse.unassignedEventList,
            status='FAILED',
            message=message
        )

    else:

        Status = 3

        message = None

        bf_response = BetaBestFitResponse(
            assignedEventList=routingResponse.assignedEventList,
            unassignedEventList=routingResponse.unassignedEventList,
            status='COMPLETE',
            message=""
        )

    routing_response_json = json.dumps(
        bf_response.dict(),
        default=str
    )

    routeOptimizationMasterDict = {

        "EmployeeNo": req.WoDetail['EmployeeNo'],
        "WorkingFromDate": startDate_str,
        "WorkingToDate": endDate_str,
        "RequestData": routing_request,
        "ResponseData": routing_response_json,
        "IsProcessed": 0,
        "IsActive": 1,
        "ApiId": requestId,
        "Status": Status,
        "StatusUpdatedDate": current_time,
        "SourceFromDate": startDate_str,
        "SourceToDate": endDate_str,
        "IsExternalSource": 1,
        "UnassignedMessage": message,
        "CreatedBy": req.EmployeeId,
        "CreatedDate": current_time
    }

    routeOptimizationMaster = pd.DataFrame.from_records(
        [routeOptimizationMasterDict]
    )

    # =========================================================
    # INSERT MASTER
    # =========================================================

    if not routeOptimizationMaster.empty:

        insert_into_db(
            routeOptimizationMaster,
            "ServiceCore.RouteOptimizationMaster"
        )

    # =========================================================
    # FETCH MASTER ID
    # =========================================================

    route_master_id = fetch_data_from_db(
        f"""
        SELECT id
        FROM ServiceCore.RouteOptimizationMaster rom
        WHERE rom.ApiId = '{requestId}'
        """
    )

    if route_master_id.empty:

        raise ValueError(
            f"No RouteOptimizationMaster found for ApiId={requestId}"
        )

    optimization_master_id = (
        route_master_id.iloc[0]['id']
    )

    # =========================================================
    # AUDIT COLUMNS
    # =========================================================

    RouteOptimizationDetail['CreatedBy'] = (
        req.EmployeeId
    )

    RouteOptimizationDetail['CreatedDate'] = (
        current_time
    )

    RouteOptimizationDetail.loc[
        :,
        'OptimizationMasterId'
    ] = optimization_master_id

    # =========================================================
    # INSERT DETAIL
    # =========================================================

    RouteOptimizationDetail = (
        RouteOptimizationDetail
        .drop_duplicates()
    )

    if not RouteOptimizationDetail.empty:

        insert_into_db(
            RouteOptimizationDetail,
            "ServiceCore.RouteOptimizationDetail"
        )

    RouteOptimizationDetailLunchEvent = (
        RouteOptimizationDetail.loc[
            mask_lunch
        ]
    )

    RouteOptimizationDetailLunchEvent.loc[
        :,
        'EntityId'
    ] = (
        RouteOptimizationDetailLunchEvent[
            'EntityNo'
        ]
    )

    RouteOptimizationDetailLunchEvent.loc[
        :,
        'EntityNo'
    ] = None

    RouteOptimizationDetailLunchEvent.drop(
        columns=[
            'Services',
            'StatusSysName',
            'Address1',
            'Address2',
            'CityName',
            'Zipcode',
            'Statename',
            'CountryName',
            'Latitude',
            'Longitude'
        ],
        errors='ignore',
        inplace=True
    )

    if not RouteOptimizationDetailLunchEvent.empty:

        insert_into_db(
            RouteOptimizationDetailLunchEvent,
            "ServiceCore.RouteOptimizationDetailLunchEvent"
        )

    # =========================================================
    # JOB RESPONSE
    # =========================================================

    eve_df = work_order_details[
        ~(
            work_order_details['eventType']
            == 'BlockTime'
        )
    ][
        [
            'eventId',
            'userPreferredTechnicianId',
            'routenotusing',
            'RouteName',
            'eventDate'
        ]
    ]

    if eve_df.empty or tech_df.empty:

        job_df = pd.DataFrame()

    else:

        job_df = (
            eve_df.merge(
                tech_df[
                    [
                        'FirstName',
                        'MiddleName',
                        'LastName',
                        'FullName',
                        'EmployeeId',
                        'EmployeeNo'
                    ]
                ],
                left_on='userPreferredTechnicianId',
                right_on='EmployeeNo',
                how='left'
            )
            .drop_duplicates()
            .drop(
                columns=[
                    'userPreferredTechnicianId'
                ],
                errors='ignore'
            )
            .rename(
                columns={
                    "routenotusing": "RouteId"
                }
            )
        )

    response = {
        "routeOptimizationMasterId": int(
            optimization_master_id
        ),
        "Jobs": []
    }

    for row in job_df.to_dict("records"):

        job = {
            "eventId": str(
                row.get("eventId")
            ),
            "eventDate": row.get(
                "eventDate"
            ),
            "AssignedTo": {
                "EmployeeId": (
                    row["EmployeeId"]
                    if pd.notna(
                        row["EmployeeId"]
                    )
                    else "0"
                ),
                "EmployeeNo": (
                    str(row["EmployeeNo"])
                    if pd.notna(
                        row["EmployeeNo"]
                    )
                    else ""
                ),
                "FullName": (
                    row["FullName"]
                    if pd.notna(
                        row["FullName"]
                    )
                    else ""
                ),
                "FirstName": (
                    row["FirstName"]
                    if pd.notna(
                        row["FirstName"]
                    )
                    else ""
                ),
                "MiddleName": (
                    row["MiddleName"]
                    if pd.notna(
                        row["MiddleName"]
                    )
                    else ""
                ),
                "LastName": (
                    row["LastName"]
                    if pd.notna(
                        row["LastName"]
                    )
                    else ""
                ),
                "RouteName": (
                    row["RouteName"]
                    if pd.notna(
                        row["RouteName"]
                    )
                    else ""
                ),
                "RouteId": (
                    row["RouteId"]
                    if pd.notna(
                        row["RouteId"]
                    )
                    else "0"
                )
            }
        }

        response['Jobs'].append(job)

    return response