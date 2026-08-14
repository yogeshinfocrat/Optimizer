# import numpy as np
# from datetime import date
# from calendar import monthrange
from src.SQL_Manger.db_operations.db_manager  import fetch_data_from_db
from src.ETL.beta_operations.geofence import preprocess_from_df, get_inbound_parallel
from src.Utils.date_utils import get_days_from_value
from datetime import datetime, timedelta
from datetime import time
import pandas as pd
from src.Utils.log import logger


def create_date_range(req) -> list:
    if not req.DateRange:
        return pd.to_datetime([req.StartDate])
    date_range = []
    for i in range(req.DateRange):
        date = req.StartDate + timedelta(days=i)
        date_range.append(date)
    return date_range


def duration_to_int(x):
    if pd.isna(x):
        return 0

    # already int/float
    if isinstance(x, (int, float)):
        return int(x)

    # datetime.time
    if isinstance(x, time):
        return x.hour * 60 + x.minute

    # string like "01:30" or "01:30:00"
    if isinstance(x, str):

        parts = x.split(":")

        if len(parts) >= 2:
            return int(parts[0]) * 60 + int(parts[1])

        # numeric string
        if x.isdigit():
            return int(x)

    return 0


def remove_overlapping_block_times(block_time_df):
    df = block_time_df.copy()

    df["FromDate"] = pd.to_datetime(df["FromDate"])
    df["ToDate"] = pd.to_datetime(df["ToDate"])

    merged_rows = []

    for emp_no, group in df.groupby("EmployeeNo"):
        group = group.sort_values("FromDate").reset_index(drop=True)

        current = group.iloc[0].copy()

        for i in range(1, len(group)):
            next_row = group.iloc[i]

            if next_row["FromDate"] <= current["ToDate"]:

                # extend interval
                current["ToDate"] = max(
                    current["ToDate"],
                    next_row["ToDate"]
                )

                # fill lat/lon from any overlapping row
                if pd.isna(current["Latitude"]) and pd.notna(next_row["Latitude"]):
                    current["Latitude"] = next_row["Latitude"]

                if pd.isna(current["Longitude"]) and pd.notna(next_row["Longitude"]):
                    current["Longitude"] = next_row["Longitude"]

            else:
                merged_rows.append(current)
                current = next_row.copy()

        merged_rows.append(current)

    return pd.DataFrame(merged_rows).reset_index(drop=True)


def get_wo_details(req, config, tech_df):
    date_range = pd.to_datetime(create_date_range(req))
    startDate = pd.to_datetime(req.StartDate)

    # convert to string (SQL-friendly format)
    startDate_str = startDate.strftime('%Y-%m-%d 00:00:00.000')
    if req.DateRange:
        endDate = startDate + pd.Timedelta(days=req.DateRange - 1)
        endDate_str = endDate.strftime('%Y-%m-%d 23:59:59.000')
        dq = f"BETWEEN '{startDate_str}' AND '{endDate_str}'"
    else:
        endDate = pd.to_datetime(req.StartDate)
        endDate_str = endDate.strftime('%Y-%m-%d 23:59:59.000')
        dq = f"BETWEEN '{startDate_str}' AND '{endDate_str}'"

    wo_columns = [
        "Services",
        "StatusSysName",
        "Address1",
        "Address2",
        "CityName",
        "Statename",
        "CountryName",
        "InitialRouteNo",
        "RouteName",
        "TotalEstimationTimeInt",
        "SubWorkOrderId",
        "subwoServiceDate",
        "subwoEmployeeNo",
        "eventId",
        "name",
        "eventType",
        "AccountNumber",
        "eventDate",
        "ScheduleTime",
        "lockTime",
        "lockTech",
        "ProductionAmount",
        "duration",
        "routenotusing",
        "ServiceStartStartTime",
        "ServiceStartEndTime",
        "EarliestServiceDate",
        "LatestServiceDate",
        "userPreferredTechnicianId",
        "EligibleDaysTo",
        "EligibleDaysFrom",
        "EligibleDaysOfWeek",
        "serviceSysName",
        "lat",
        "lng",
        "subWorkOrderProductionAmount",
        "SubWorkOrderNo",
        "branchId",
        "ServicesAttribute",
        "Zipcode",
        "PropertyType"
    ]

    if len(req.EmployeeNos) > 1:
        q1 = f"IN {tuple(req.EmployeeNos)}"
    else:
        q1 = f" = '{req.EmployeeNos[0]}'"
    wo_query = f"""
    SELECT  MAX(CASE WHEN wos.IsPrimary = 1 THEN sm.Name END) as Services,  wos2.name as StatusSysName, 
    wo.ProductionAmount as subWorkOrderProductionAmount, ca.Address1, ca.Address2, ca.CityName,
     sm2.Name as Statename, cm.Name as CountryName,
    rm.RouteNo  as InitialRouteNo, rm.RouteName, wo.DriveTime
    ,swo.TotalEstimationTimeInt, swo.SubWorkOrderId,swo.SubWorkOrderNo,swo.ServiceDateTime as subwoServiceDate ,swo.EmployeeNo as subwoEmployeeNo ,
    wo.WorkorderId AS eventId, wo.WorkOrderNo AS name, wo.OrderType AS eventType, wo.AccountNumber, wo.branchId,
    wo.ServiceDate AS eventDate, wo.ScheduleTime, wo.lockTime, wo.LockTechnician AS lockTech,
    wo.TotalEstimationTime AS duration, wo.InitialRouteId AS routenotusing, wo.ServiceStartStartTime, 
    wo.ServiceStartEndTime, wo.RangeofTimeId,wo.EarliestServiceDate, wo.LatestServiceDate, wo.EmployeeNo AS userPreferredTechnicianId,
    wo.EligibleDaysFrom as EligibleDaysTo, wo.EligibleDaysTo as EligibleDaysFrom, wo.EligibleDaysOfWeek, STRING_AGG(sm.[SysName], ', ') as serviceSysName, 
    ca.Latitude as lat, ca.Longitude as lng, ca.Zipcode, wo.ServicesAttribute,
    ca.AddressSubType as PropertyType
     FROM ServiceCore.WorkOrder wo JOIN ServiceCore.WorkOrderServices wos ON 
    wo.WorkorderId = wos.WorkorderId JOIN ServiceCore.ServiceMaster sm ON sm.ServiceMasterId = wos.ServiceId 
    --JOIN ServiceCore.ServiceCategoryMaster scm ON sm.CategoryId = scm.CategoryId
    JOIN [CRM].[Account] a ON a.accountNo = wo.accountNumber JOIN [CRM].[CustomerAddress] ca ON ca.AccountId = a.AccountId 
    AND  ca.CustomerAddressId = wo.ServiceAddressId 
    join ServiceCore.WorkOrderStatus wos2 on wos2.WoStatusId = wo.WoStatusId 
    left join ServiceCore.SubWorkOrder swo on swo.WorkOrderId = wo.WorkorderId  
    left  join Common.RouteMaster rm  on rm.RouteId = wo.InitialRouteId 
    join Common.StateMaster sm2 on sm2.StateId = ca.StateId 
    join  Common.CountryMaster cm on ca.CountryId = cm.CountryId 
    WHERE wo.EmployeeNo {q1} AND wo.CompanyId = {config.Common_CompId}  
    AND a.CompanyId = {config.CRM_CompId} AND wo.ServiceDate {dq}
    AND wos2.Name in ('Incomplete','reset') AND a.IsHold = 0 and (wo.IsHold = 0 or wo.Ishold is NULL ) 
    AND (a.CollectionStatus NOT IN (3,4)
    OR a.CollectionStatus IS NULL) and ca.IsPrimary = 1
    AND ((swo.ServiceDateTime IS NULL) OR (swo.ServiceDateTime  {dq})) 
    GROUP BY ca.Latitude, ca.Longitude, wo.WorkorderId, wo.WorkOrderNo, wo.OrderType, wo.AccountNumber, 
    wo.ServiceDate, wo.ScheduleTime, wo.lockTime, wo.LockTechnician, wo.ProductionAmount, wo.TotalEstimationTime,
    wo.InitialRouteId, wo.ServiceStartStartTime, wo.ServiceStartEndTime, wo.EarliestServiceDate, 
    wo.LatestServiceDate, wo.EmployeeNo, wo.EligibleDaysFrom, wo.EligibleDaysTo, wo.EligibleDaysOfWeek,
    swo.TotalEstimationTimeInt, swo.SubWorkOrderId, swo.ServiceDateTime, swo.EmployeeNo,  wos2.name, ca.Address1,ca.Address2,ca.CityName, ca.Zipcode,sm2.Name , cm.Name,
    rm.RouteNo , rm.RouteName, wo.DriveTime ,wo.RangeofTimeId, swo.SubWorkOrderNo, wo.branchId, ca.Zipcode, ca.AddressSubType, wo.ServicesAttribute;"""

    wo_df = fetch_data_from_db(wo_query)

    # wo_df = wo_df[wo_df['eventType']!='CallBack']
    if wo_df.empty:
        logger.info("No work order found for given filters")
        wo_df = pd.DataFrame(columns=wo_columns)

    if not wo_df.empty:
        unique_wo_ids = tuple(wo_df['eventId'].unique().tolist())

        if len(unique_wo_ids)==1:
            wo_type = fetch_data_from_db(f"""SELECT wos.WorkorderId as eventId , dt.DepartmentTypeName FROM 
            ServiceCore.WorkOrderServices wos 
                join ServiceCore.ServiceMaster sm  on sm.ServiceMasterId = wos.ServiceId 
                join servicecore.ServiceCategoryMaster scm on scm.CategoryId = sm.CategoryId 
                join common.DepartmentMaster dm on dm.DepartmentMasterId = scm.DepartmentId 
                join Common.DepartmentType dt on dm.DepartmentTypeId = dt.DepartmentTypeId 
                WHERE wos.WorkorderId = {unique_wo_ids[0]};""")
        else:
            wo_type = fetch_data_from_db(f"""SELECT wos.WorkorderId as eventId,dt.DepartmentTypeName FROM 
                                                ServiceCore.WorkOrderServices wos 
                join ServiceCore.ServiceMaster sm  on sm.ServiceMasterId = wos.ServiceId 
                join servicecore.ServiceCategoryMaster scm on scm.CategoryId = sm.CategoryId 
                join common.DepartmentMaster dm on dm.DepartmentMasterId = scm.DepartmentId 
                join Common.DepartmentType dt on dm.DepartmentTypeId = dt.DepartmentTypeId 
                WHERE wos.WorkorderId in {unique_wo_ids};""")

        wo_df = wo_df.merge(wo_type, on='eventId', how='inner')
        wo_df = wo_df[~((wo_df['DepartmentTypeName'] == 'Mechanical') & (wo_df['SubWorkOrderId'].isna()))]

        wo_df['serviceSysName'] = wo_df['serviceSysName'].apply(
            lambda x: ', '.join(dict.fromkeys(
                item.strip() for item in str(x).split(',')
            )) if pd.notna(x) else x
        )
        wo_df = wo_df.drop_duplicates(subset=['eventId', 'name', 'AccountNumber'])

        unique_range_time_id =tuple(
                                wo_df.loc[
                                    wo_df['RangeofTimeId'].notna() &
                                    (wo_df['RangeofTimeId'] != -1),
                                    'RangeofTimeId'
                                ].unique().tolist()
                            )
        if  len(unique_range_time_id)==1:
            range_time_query = f"""
            SELECT StartInterval, EndInterval ,RangeofTimeId FROM Common.RangeofTime rt 
            WHERE rt.RangeofTimeId = {unique_range_time_id[0]};
            """
        elif len(unique_range_time_id)>1:
            range_time_query = f"""
            SELECT StartInterval, EndInterval ,RangeofTimeId FROM Common.RangeofTime rt 
            WHERE rt.RangeofTimeId in {unique_range_time_id};
            """
        else:
            range_time_query = None

        if range_time_query:
            time_range_master_df = fetch_data_from_db(range_time_query)
            mapping_start = time_range_master_df.set_index('RangeofTimeId')['StartInterval']
            mapping_end = time_range_master_df.set_index('RangeofTimeId')['EndInterval']

            mask1 = wo_df['RangeofTimeId'].isin(mapping_start.index)

            wo_df.loc[mask1, 'ServiceStartStartTime'] = wo_df.loc[mask1, 'RangeofTimeId'].map(mapping_start)
            wo_df.loc[mask1, 'ServiceStartEndTime'] = wo_df.loc[mask1, 'RangeofTimeId'].map(mapping_end)


        if len(unique_wo_ids) == 1:
            price_query = f"""
            SELECT SUM(ProductionValue * Quantity) AS ProductionAmount,  WorkorderId
            FROM ServiceCore.WorkOrderServices WHERE WorkorderId = {unique_wo_ids[0]}
            GROUP BY WorkorderId;
            """
        else:
            price_query = f"""
            SELECT SUM(ProductionValue * Quantity) AS ProductionAmount,  WorkorderId
            FROM ServiceCore.WorkOrderServices WHERE WorkorderId in {unique_wo_ids}
            GROUP BY WorkorderId;
            """

        price_ = fetch_data_from_db(price_query)
        wo_df = wo_df.merge(price_, how='inner',left_on='eventId', right_on='WorkorderId')

        unique_wo_names = tuple(str(i) for i in wo_df['name'].unique())

        if len(unique_wo_names) == 1:
            query = f"""SELECT
                SUM(AppliedDiscountAmt) AS discount,
                WorkOrderNo AS name
            FROM ServiceAuto.WorkOrderAppliedDiscount woad
            WHERE woad.WorkOrderNo  = '{unique_wo_names[0]}' and woad.CompanyKey = '{req.CompanyKey}' 
            group by woad.WorkOrderNo;"""
        else:
            query = f"""
                SELECT
                    SUM(AppliedDiscountAmt) AS discount,
                    WorkOrderNo AS name
                FROM ServiceAuto.WorkOrderAppliedDiscount woad
                WHERE woad.WorkOrderNo IN {unique_wo_names} and woad.CompanyKey = '{req.CompanyKey}'
                GROUP BY woad.WorkOrderNo;
            """

        discount_ = fetch_data_from_db(query)

        if not discount_.empty:
            wo_df_with_discount_ = wo_df.merge(
                discount_,
                on='name',
                how='left'
            )

            wo_df_with_discount_['discount'] = wo_df_with_discount_['discount'].fillna(0)

            wo_df_with_discount_['ProductionAmount'] = (
                    wo_df_with_discount_['ProductionAmount']
                    - wo_df_with_discount_['discount']
            )
            wo_df = wo_df_with_discount_

    # first_day = date(startDate.year, startDate.month, 1)
    #
    # last_day = date(
    #     startDate.year,
    #     startDate.month,
    #     monthrange(startDate.year, startDate.month)[1]
    # )
    #
    # wo_df['EarliestServiceDate'] = wo_df['EarliestServiceDate'].fillna(first_day)
    # wo_df['LatestServiceDate'] = wo_df['LatestServiceDate'].fillna(last_day)

    # -----------------------------
    # Filter only required rows
    # -----------------------------
    filtered_df = wo_df.loc[
        wo_df['subwoEmployeeNo'].isin(req.EmployeeNos)
        | wo_df['SubWorkOrderId'].isna()
        ].copy()

    # -----------------------------
    # Create WO dict directly
    # -----------------------------
    wo_detail = req.WoDetail

    rename_map = {
        "TotalEstimationTime": "duration",
        "WorkOrderId": "eventId",
        "WorkOrderNo": "name",
        "LockTime": "lockTime",
        "LockTechnician": "lockTech",
        "InvoiceAmount": "ProductionAmount",
        "RouteId": "routenotusing",
        "EmployeeNo": "userPreferredTechnicianId",
        "serviceSysName": "serviceSysName",
        "ScheduleTime": "ScheduleTime"
    }

    temp_dict = {
        rename_map.get(k, k): v
        for k, v in wo_detail.items()
    }

    try:
        temp_dict['ServiceStartStartTime'] = None
        # temp_dict['ServiceStartStartTime'] = pd.to_datetime(
        #     temp_dict['ServiceStartStartTime'],
        #     format='%I:%M %p'
        # ).time()
    except:
        temp_dict['ServiceStartStartTime'] = None

    try:
        temp_dict['ServiceStartEndTime'] = None
        # temp_dict['ServiceStartEndTime'] = pd.to_datetime(
        #     temp_dict['ServiceStartEndTime'],
        #     format='%I:%M %p'
        # ).time()
    except:
        temp_dict['ServiceStartEndTime'] = None
    # -----------------------------
    # Fetch location
    # -----------------------------
    if req.WoDetail.get('ServiceAddressId'):
        temp_wo_loc = fetch_data_from_db(f"""
        SELECT
            ca.Latitude AS lat,
            ca.Longitude AS lng,
            ca.AddressSubType as PropertyType,
            a.AccountNo AS AccountNumber
        FROM CRM.Account a
        JOIN CRM.CustomerAddress ca
            ON ca.AccountId = a.AccountId
        WHERE
            a.AccountNo = '{wo_detail["AccountNumber"]}'
            AND a.CompanyId = {config.CRM_CompId}
            AND ca.CustomerAddressId = {int(req.WoDetail.get('ServiceAddressId'))}
        """)
    else:
        temp_wo_loc = fetch_data_from_db(f"""
        SELECT
            ca.Latitude AS lat,
            ca.Longitude AS lng,
            ca.AddressSubType as PropertyType,
            a.AccountNo AS AccountNumber
        FROM CRM.Account a
        JOIN CRM.CustomerAddress ca
            ON ca.AccountId = a.AccountId
        JOIN CRM.AddressTypeMaster atm
            ON ca.AddressTypeId = atm.AddressTypeId
            AND a.CompanyId = atm.CompanyId
        WHERE
            a.AccountNo = '{wo_detail["AccountNumber"]}'
            AND atm.SysName = 'Service'
            AND a.CompanyId = {config.CRM_CompId}
        """)

    temp_dict['EligibleDaysFrom'], temp_dict['EligibleDaysTo'] = (
        temp_dict['EligibleDaysTo'],
        temp_dict['EligibleDaysFrom']
    )
    # -----------------------------
    # Build single base row
    # -----------------------------
    base_row = {
        **temp_dict,
        **temp_wo_loc.iloc[0].to_dict(),
        "EarliestServiceDate": startDate,
        "LatestServiceDate": endDate,
        "eventType": "WorkOrder",
        "eventId": 0
    }

    # -----------------------------
    # Fast conversions
    # -----------------------------
    base_row["EligibleDaysTo"] = (
        int(base_row["EligibleDaysTo"])
        if base_row.get("EligibleDaysTo")
        else None
    )

    base_row["EligibleDaysFrom"] = (
        int(base_row["EligibleDaysFrom"])
        if base_row.get("EligibleDaysFrom")
        else None
    )

    if isinstance(base_row.get("serviceSysName"), list):
        base_row["serviceSysName"] = ", ".join(
            dict.fromkeys(
                str(x) for x in base_row["serviceSysName"]
                if x is not None
            )
        ) if base_row["serviceSysName"] else ""


    if base_row.get("ScheduleTime"):
        base_row["ScheduleTime"] = pd.to_datetime(
            base_row["ScheduleTime"]
        ).time()

    if req.WoDetail['BestFitInitialPreferedId']:
        temp_time = fetch_data_from_db(f"""SELECT TOP (1000) [RangeofTimeId]
                          ,[StartInterval] ,[EndInterval] FROM [pstrmcore].[Common].[RangeofTime]
                          where [RangeofTimeId] = {int(req.WoDetail['BestFitInitialPreferedId'])} and IsActive = 1 
                          and IsDeleted = 0 and CompanyId = {config.Common_CompId}""")
        base_row['ServiceStartStartTime'] = pd.to_datetime(temp_time['StartInterval'].iloc[0]).time()
        base_row['ServiceStartEndTime'] = pd.to_datetime(temp_time['EndInterval'].iloc[0]).time()

    # -----------------------------
    # Create rows for all dates
    # -----------------------------
    new_rows_df = pd.DataFrame({
        **{
            k: [v] * len(date_range)
            for k, v in base_row.items()
        },
        "eventDate": date_range
    })

    new_rows_df['serviceSysName'] = new_rows_df['serviceSysName'].fillna("")
    # Keep only required cols
    new_rows_df = new_rows_df.reindex(
        columns=filtered_df.columns
    )
    new_rows_df.drop(columns=['Zipcode','branchId'], inplace=True,axis=1)

    if req.WoDetail.get('ServiceAddressId'):
        temp_wo_add = fetch_data_from_db(f"""SELECT ca.Latitude , ca.Longitude ,ca.Address1, ca.Address2,  ca.AddressSubType as PropertyType,
        ca.CityName, ca.Zipcode,sm.Name as Statename , cm.Name as CountryName, a.AccountNo FROM crm.Account a 
        join CRM.CustomerAddress ca  on ca.AccountId= a.AccountId join  common.StateMaster sm  on ca.StateId = sm.StateId 
        join Common.CountryMaster cm on sm.CountryId= cm.CountryId 
        WHERE a.AccountNo = '{req.WoDetail['AccountNumber']}' AND 
        ca.CustomerAddressId = {int(req.WoDetail.get('ServiceAddressId'))}
        and a.CompanyId  = {config.CRM_CompId}  and IsPrimary = 1 ;""")

    else:
        temp_wo_add = fetch_data_from_db(f"""SELECT ca.Latitude , ca.Longitude ,ca.Address1, ca.Address2,  ca.AddressSubType as PropertyType,
        ca.CityName, ca.Zipcode,sm.Name as Statename , cm.Name as CountryName, a.AccountNo FROM crm.Account a 
        join CRM.CustomerAddress ca  on ca.AccountId= a.AccountId join  common.StateMaster sm  on ca.StateId = sm.StateId 
        join Common.CountryMaster cm on sm.CountryId= cm.CountryId 
        join crm.AddressTypeMaster atm on atm.AddressTypeId  = ca.AddressTypeId 
        WHERE a.AccountNo = '{req.WoDetail['AccountNumber']}' and atm.Name  = 'Service'
         and a.CompanyId  = {config.CRM_CompId}  and IsPrimary = 1 ;""")
    # -----------------------------
    # Append once
    # -----------------------------

    # temp_wo_route = fetch_data_from_db(f"""SELECT RouteNo FROM common.RouteMaster rm WHERE rm.RouteId ={req.WoDetail['RouteId']}
    #  and rm.CompanyId ={config.Common_CompId};""")
    new_rows_df['lat'] = temp_wo_add['Latitude'].iloc[0]
    new_rows_df['lng'] = temp_wo_add['Longitude'].iloc[0]
    new_rows_df['Address1'] = temp_wo_add['Address1'].iloc[0]
    new_rows_df['Address2'] = temp_wo_add['Address2'].iloc[0]
    new_rows_df['CityName'] = temp_wo_add['CityName'].iloc[0]
    new_rows_df['Zipcode'] = temp_wo_add['Zipcode'].iloc[0]
    new_rows_df['Statename'] = temp_wo_add['Statename'].iloc[0]
    new_rows_df['CountryName'] = temp_wo_add['CountryName'].iloc[0]
    # new_rows_df['InitialRouteNo'] = temp_wo_route['RouteNo'].iloc[0]
    new_rows_df['StatusSysName'] = "Incomplete"
    new_rows_df['Services'] = req.WoDetail['ServiceName']

    # temp_wo_routes = fetch_data_from_db(f"""SELECT RouteNo, rm.RouteName, re.EmployeeNo ,re.RouteId  FROM Common.RouteMaster rm join
    # Common.RouteEmployee re  on rm.RouteId = re.RouteId WHERE re.EmployeeNo {q1} and re.IsLead = 1
    # and rm.IsActive = 1 and  rm.CompanyId = {config.Common_CompId};""")

    temp_wo_routes = fetch_data_from_db(f"""   SELECT RouteNo, rm.RouteName, re.EmployeeNo ,re.RouteId, rm.branchId  
    FROM Common.RouteMaster rm join Common.RouteEmployee re  on rm.RouteId = re.RouteId join HRMS.Employee e 
    on e.EmployeeNo = re.EmployeeNo WHERE re.EmployeeNo {q1}  and re.IsLead = 1 and e.CompanyId = {config.HRMS_CompId}
    AND rm.BranchId = e.BranchMasterId and rm.IsActive = 1 and  rm.CompanyId = {config.Common_CompId} and e.IsActive = 1 
    """).drop_duplicates(subset = ['EmployeeNo','branchId'])

    new_rows_df.drop(columns=['userPreferredTechnicianId', 'routenotusing', 'RouteName'], axis=1, inplace=True)
    new_rows_df = new_rows_df.merge(
        temp_wo_routes,
        how="cross"
    )
    new_rows_df.rename(columns={'EmployeeNo': 'userPreferredTechnicianId', 'RouteId': 'routenotusing'}, inplace=True)
    new_rows_df['InitialRouteNo'] = new_rows_df['RouteNo']
    new_rows_df['lockTech'] = False
    new_rows_df['lockTime'] = False

    new_rows_df['EarliestServiceDate'] = new_rows_df['eventDate']
    new_rows_df['LatestServiceDate'] = new_rows_df['eventDate']

    import numpy as np

    # Create lookup dataframe
    new_rows_df['WeekId'] = new_rows_df['eventDate'].dt.day_name().str.lower()
    tech_lookup = tech_df[['EmployeeNo', 'FromTime', 'ToTime','WeekId']].drop_duplicates()
    # Merge
    new_rows_df = new_rows_df.merge(
        tech_lookup,
        left_on=['userPreferredTechnicianId','WeekId'],
        right_on=['EmployeeNo','WeekId'],
        how='left'
    )

    # Condition
    mask2 = (
            # new_rows_df['name'].str[:10].eq('RO-TempGWO') &
            new_rows_df['eventId'] == 0
    )

    # Fill ServiceStartStartTime only when blank/NA
    start_na = (
            new_rows_df['ServiceStartStartTime'].isna() |
            new_rows_df['ServiceStartStartTime'].eq('')
    )

    new_rows_df.loc[
        mask2 & start_na,
        'ServiceStartStartTime'
    ] = new_rows_df.loc[
        mask2 & start_na,
        'FromTime'
    ]

    # Fill ServiceStartEndTime only when blank/NA
    end_na = (
            new_rows_df['ServiceStartEndTime'].isna() |
            new_rows_df['ServiceStartEndTime'].eq('')
    )

    new_rows_df.loc[
        mask2 & end_na,
        'ServiceStartEndTime'
    ] = new_rows_df.loc[
        mask2 & end_na,
        'ToTime'
    ]

    # Optional cleanup
    new_rows_df.drop(
        columns=['EmployeeNo', 'FromTime', 'ToTime'],
        inplace=True
    )

    filtered_df = pd.concat(
        [filtered_df, new_rows_df],
        ignore_index=True,
        copy=False
    )

    # -----------------------------
    # Geofencing
    # -----------------------------
    filtered_df["inBoundEmployeeNo"] = None

    if config.IsEnableRoGeofencing:
        geo_query = f"""
        SELECT
            ModeType,
            EmployeeNo,
            CircleCenter,
            CircleRadius,
            RectangleSouthWest,
            RectangleNorthEast,
            PolygonLatLngArray
        FROM HRMS.EmployeeGeoFencingAreaAssignment faa
        JOIN HRMS.EmployeeGeoFencingArea gfa
            ON gfa.EmployeeGeoFencingAreaId = faa.EmployeeGeoFencingAreaId
        JOIN HRMS.employee e
            ON e.EmployeeId = faa.EmployeeId
        WHERE
            faa.IsActive = 1
            AND e.EmployeeNo {q1}
            AND e.CompanyId = {config.HRMS_CompId}
        """

        geo_df = fetch_data_from_db(geo_query)

        processed_employees = preprocess_from_df(geo_df)

        filtered_df["lat"] = filtered_df["lat"].astype(float)
        filtered_df["lng"] = filtered_df["lng"].astype(float)

        filtered_df["inBoundEmployeeNo"] = [
            get_inbound_parallel(
                processed_employees,
                lat,
                lng
            )
            for lat, lng in zip(
                filtered_df["lat"].values,
                filtered_df["lng"].values
            )
        ]

    # -----------------------------
    # Vectorized cleanup
    # -----------------------------
    filtered_df["TotalEstimationTimeInt"] = (
        pd.to_numeric(
            filtered_df["TotalEstimationTimeInt"],
            errors="coerce"
        )
        .fillna(0)
        .astype(np.int32)
    )

    filtered_df["SubWorkOrderId"] = (
        pd.to_numeric(
            filtered_df["SubWorkOrderId"],
            errors="coerce"
        )
        .astype("Int64")
    )

    numeric_cols = [
        "ProductionAmount",
        "lat",
        "lng"
    ]

    filtered_df[numeric_cols] = (
        filtered_df[numeric_cols]
        .astype(float)
    )

    # -----------------------------
    # Update duration
    # -----------------------------

    filtered_df['ParentEntityId'] = 0

    mask3 = (
            filtered_df['SubWorkOrderId'].notna()
            & filtered_df['SubWorkOrderId'].ne('')
    )

    original_entity_id = filtered_df.loc[
        mask3,
        'eventId'
    ].copy()

    filtered_df.loc[
        mask3,
        'ParentEntityId'
    ] = original_entity_id

    filtered_df.loc[
        mask3,
        'eventId'
    ] = filtered_df.loc[
        mask3,
        'SubWorkOrderId'
    ]

    filtered_df.loc[
        mask3,
        "name"
    ] = filtered_df.loc[
        mask3,
        "SubWorkOrderNo"
    ]


    filtered_df.loc[
        mask3,
        "duration"
    ] = filtered_df.loc[
        mask3,
        "TotalEstimationTimeInt"
    ]

    filtered_df.loc[
        mask3,
        "eventType"
    ] = 'SubWorkOrder'


    # filtered_df.loc[
    #     mask3,
    #     "eventId"
    # ] = filtered_df.loc[
    #     mask3,
    #     "SubWorkOrderId"
    # ]

    filtered_df.loc[
        mask3,
        "ProductionAmount"
    ] = 0


    filtered_df.loc[
        mask3,
        "eventDate"
    ] = filtered_df.loc[
        mask3,
        "subwoServiceDate"
    ]

    filtered_df.loc[mask3, ["EligibleDaysTo", "EligibleDaysFrom"]] = None
    filtered_df.loc[mask3, "EligibleDaysOfWeek"] = 0
    # -----------------------------
    # Fill defaults
    # -----------------------------
    filtered_df["ServiceStartStartTime"] = (
        filtered_df["ServiceStartStartTime"]
        .replace("", pd.NA)
        .fillna(pd.to_datetime("00:00").time())
    )

    filtered_df["ServiceStartEndTime"] = (
        filtered_df["ServiceStartEndTime"]
        .replace("", pd.NA)
        .fillna(pd.to_datetime("23:59").time())
    )

    # filtered_df["EarliestServiceDate"] = (
    #     filtered_df["EarliestServiceDate"]
    #     .fillna(startDate)
    # )
    #
    # filtered_df["LatestServiceDate"] = (
    #     filtered_df["LatestServiceDate"]
    #     .fillna(endDate)
    # )

    filtered_df["EligibleDaysOfWeek"] = (
        filtered_df["EligibleDaysOfWeek"]
        .fillna(0)
        .astype(int)
        .apply(get_days_from_value)
    )

    filtered_df["duration"] = (
        filtered_df["duration"]
        .apply(duration_to_int)
        .astype(np.int32)
    )

    filtered_df["eventType"] = (
        filtered_df["eventType"]
        .replace("ServiceOrder", "WorkOrder")
    )

    filtered_df["eventType"] = (
        filtered_df["eventType"]
        .replace("CallBack", "WorkOrder")
    )

    block_time = fetch_data_from_db(f"""SELECT e.EmployeeNo,bt.FromDate, bt.ToDate, bt.Title, bt.Latitude, 
    bt.Longitude, bt.AddressLine1 as Address1,	bt.AddressLine2 as Address2,bt.City as CityName, bt.ZipCode as Zipcode, bt.StateId, bt.CountryId, sm.Name as Statename
     , cnm.Name as CountryName	FROM HRMS.EmployeeBlockTime
    bt WITH (NOLOCK) INNER JOIN HRMS.EmployeeBlockTimeAssignment bta WITH (NOLOCK) ON
    bta.EmployeeBlockTimeId = bt.EmployeeBlockTimeId AND bta.IsActive = 1
    INNER JOIN HRMS.Employee e WITH (NOLOCK) ON e.EmployeeId = bta.EmployeeId
    INNER JOIN HRMS.CompanyMaster cm WITH (NOLOCK) ON cm.CompanyId = e.CompanyId 
     left JOIN   common.StateMaster sm  on bt.StateId = sm.StateId 
     left JOIN  Common.CountryMaster cnm on sm.CountryId= cm.CountryId WHERE 
    bt.FromDate BETWEEN'{startDate_str}' AND '{endDate_str}' AND e.CompanyId = {config.HRMS_CompId}
    AND e.EmployeeNo {q1};""")

    if not block_time.empty:
        block_time['blockDate'] = block_time['FromDate'].apply(lambda x: x.date())
        original_block_time_df = block_time.copy()
        block_time = remove_overlapping_block_times(block_time)
        # -----------------------------------
        # Blocktimes having coordinates
        # -----------------------------------
        geo_block_mask = (
                block_time["Latitude"].notna()
                & block_time["Longitude"].notna()
        )

        geo_block_df = block_time.loc[geo_block_mask].copy()

        # remove from original block_time
        # block_time = block_time.loc[~geo_block_mask].copy()
        """commented above because we are removing them inside request mapper using to_removed"""

    else:
        bt_columns = [
            "EmployeeNo",
            "FromDate",
            "ToDate",
            "Title",
            "Latitude",
            "Longitude"
        ]

        block_time = pd.DataFrame(columns=bt_columns)
        original_block_time_df = block_time.copy()
        geo_block_df = pd.DataFrame(columns=bt_columns)
    # -----------------------------------
    # Convert to filtered_df schema
    # -----------------------------------
    edit_wo_names = filtered_df[filtered_df['eventId'] == 0]['name'].unique()
    filtered_df = filtered_df[~((filtered_df['eventId'] != 0) & (filtered_df['name'].isin(edit_wo_names)))]

    filtered_df.sort_values(by='eventId', inplace=True)

    if not geo_block_df.empty:
        geo_events = pd.DataFrame(index=geo_block_df.index)

        # relevant mapped columns
        geo_events["lat"] = geo_block_df["Latitude"].astype(float)
        geo_events["lng"] = geo_block_df["Longitude"].astype(float)
        geo_events["Address1"] = geo_block_df["Address1"]
        geo_events["Address2"] = geo_block_df["Address2"]
        geo_events["CityName"] = geo_block_df["CityName"]
        geo_events["Zipcode"] = geo_block_df["Zipcode"]
        geo_events["Statename"] = geo_block_df["Statename"]
        geo_events["CountryName"] = geo_block_df["CountryName"]

        geo_events["eventDate"] = pd.to_datetime(
            geo_block_df["FromDate"]
        ).dt.normalize()

        geo_events["name"] = geo_block_df["Title"]

        geo_events["eventType"] = "BlockTime"

        geo_events["userPreferredTechnicianId"] = (
            geo_block_df["EmployeeNo"].astype(str)
        )

        geo_events["ScheduleTime"] = (
            pd.to_datetime(
                geo_block_df["FromDate"]
            ).dt.time
        )

        geo_events["ServiceStartStartTime"] = (
            pd.to_datetime(
                geo_block_df["FromDate"]
            ).dt.time
        )

        geo_events["ServiceStartEndTime"] = (
            pd.to_datetime(
                geo_block_df["ToDate"]
            ).dt.time
        )

        # duration in minutes
        geo_events["duration"] = (
            (
                    pd.to_datetime(geo_block_df["ToDate"])
                    -
                    pd.to_datetime(geo_block_df["FromDate"])
            )
            .dt.total_seconds()
            .floordiv(60)
            .astype(int)
        )

        # -----------------------------------
        # dummy/default values
        # -----------------------------------
        geo_events["eventId"] = np.random.randint(
            100000,
            999999,
            size=len(geo_events)
        )

        geo_events["AccountNumber"] = None

        geo_events["lockTime"] = True
        geo_events["lockTech"] = True

        geo_events["ProductionAmount"] = 0

        geo_events["routenotusing"] = None

        geo_events["EarliestServiceDate"] = geo_events["eventDate"]
        geo_events["LatestServiceDate"] = geo_events["eventDate"]

        geo_events["EligibleDaysTo"] = np.nan
        geo_events["EligibleDaysFrom"] = np.nan

        geo_events["EligibleDaysOfWeek"] = [[] for _ in range(len(geo_events))]

        geo_events["serviceSysName"] = ""

        geo_events["SubWorkOrderId"] = pd.NA
        geo_events["subwoEmployeeNo"] = pd.NA
        geo_events["subwoServiceDate"] = pd.NaT

        geo_events["TotalEstimationTimeInt"] = 0

        geo_events["inBoundEmployeeNo"] = None

        # -----------------------------------
        # Match filtered_df schema
        # -----------------------------------
        geo_events = geo_events.reindex(
            columns=filtered_df.columns
        )

        # append
        filtered_df = pd.concat(
            [filtered_df, geo_events],
            ignore_index=True,
            copy=False
        )

    filtered_df['lat'] = filtered_df['lat'].apply(lambda x: round(x, 7))
    filtered_df['lng'] = filtered_df['lng'].apply(lambda x: round(x, 7))
    mask4 = (
            filtered_df['lockTime'].eq(False)
            & (
                    filtered_df['ScheduleTime'].isna()
                    | filtered_df['ScheduleTime'].eq('')
            )
    )

    filtered_df.loc[mask4, 'ScheduleTime'] = pd.to_datetime("09:00").time()

    filtered_df['ServiceStartStartTime'] = filtered_df['ServiceStartStartTime'].apply(
        lambda x: pd.to_datetime(x).time() if isinstance(x, str) else x if pd.notna(x) else None
    )

    filtered_df['ServiceStartEndTime'] = filtered_df['ServiceStartEndTime'].apply(
        lambda x: pd.to_datetime(x).time() if isinstance(x, str) else x if pd.notna(x) else None
    )
    filtered_df["eventDate"] = pd.to_datetime(
        filtered_df["eventDate"],
        errors="coerce"
    ).dt.normalize()
    filtered_df['eventType'] = filtered_df['eventType'].replace({'Commission': 'WorkOrder'})
    return filtered_df, q1, startDate_str, endDate_str, date_range, block_time,  original_block_time_df
