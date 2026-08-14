from src.SQL_Manger.db_operations.db_manager  import fetch_data_from_db
import pandas as pd


def get_tech_details(req, config):
    if len(req.EmployeeNos) > 1:
        q1 = f"IN {tuple(req.EmployeeNos)}"
    else:
        q1 = f" = '{req.EmployeeNos[0]}'"

    WeekIdMapper = {2: "monday", 3: "tuesday", 4: "wednesday", 5: "thursday", 6: "friday", 7: "saturday", 1: "sunday"}
    day_start_end_code = {1: "Home", 2: "Office", 3: "FirstJob", 4: "LastJob"}
    driving_enum = {2: "Faster", 1 : "Slower"}

    tech_df = fetch_data_from_db(f"""
    SELECT e.FirstName, e.MiddleName, e.LastName, CONCAT_WS(' ', e.FirstName, e.MiddleName, e.LastName) AS FullName,
     e.EmployeeId, e.EmployeeNo,
    CASE WHEN wd.DayStartLocation IN (2,3,4) THEN bm.Latitude ELSE e.Latitude END AS Latitude, CASE WHEN 
    wd.DayStartLocation IN (2,3,4) THEN bm.Longitude 
    ELSE e.Longitude END AS Longitude, wd.WeekId, wd.ArriveFirstJobNoEarlierThan AS InTime, 
    wd.ArriveAtLastJobNoLaterThan, wd.EndLastJobNoLaterThan, 
    wd.EarliestLunchTime, wd.LatestLunchTime, wd.LunchDuration, wd.MaxServiceDuration, wd.MaxTotalDayDuration, 
    wd.MaxDriveTime, wd.MaxProductionValue,
    wd.MaxNoOfJobs, wd.MinNoOfJobs, wd.DayStartLocation, wd.DayEndLocation, e.DrivingSpeedVariation AS variation_percent,
     e.DrivingSpeed AS driving_mode, 
    ewh.FromTime, ewh.ToTime, e.BranchMasterId, zm.ZipCodes, am.attributes_id , e.EmployeeFlowType
    FROM HRMS.Employee e WITH (NOLOCK) 
    INNER JOIN HRMS.EmployeeWorkingDetail wd 
    WITH (NOLOCK) ON e.EmployeeId = wd.EmployeeId INNER JOIN HRMS.EmployeeWorkingHrs ewh ON
     ewh.EmployeeId = e.EmployeeId AND ewh.WeekId = wd.WeekId INNER JOIN
    common.BranchMaster bm ON bm.BranchMasterId = e.BranchMasterId LEFT JOIN 
    (SELECT EmployeeId, STRING_AGG(ZipCode, ',') AS ZipCodes FROM HRMS.EmployeeZipCodeMapping
    GROUP BY EmployeeId) zm ON zm.EmployeeId = e.EmployeeId LEFT JOIN 
    (SELECT EmployeeId, STRING_AGG(AttributeId, ',') AS attributes_id 
    FROM hrms.EmployeeAttributeMapping GROUP BY EmployeeId) am ON am.EmployeeId = e.EmployeeId WHERE  e.EmployeeNo {q1}
     AND e.CompanyId = '{config.HRMS_CompId}';""")

    tech_df['BranchMasterId'] = tech_df['BranchMasterId'].apply(lambda x: [x])
    tech_df['PropertyType'] = tech_df['EmployeeFlowType'].replace('All', 'Residential, Commercial')

    skills_df = fetch_data_from_db(f"""SELECT string_agg(sm.[SysName],', ') as serviceSysName , e.EmployeeNo  FROM 
    HRMS.EmployeeSkills es Join hrms.Employee e on es.EmployeeId= e.EmployeeId
    join ServiceCore.ServiceMaster sm on sm.ServiceMasterId= es.ServiceMasterID WHERE e.EmployeeNo {q1} 
    and e.CompanyId = '{config.HRMS_CompId}' group by e.EmployeeNo ;""")

    if skills_df.empty:
        sk_columns = [
            "",
            "EmployeeNo"
        ]
        skills_df = pd.DataFrame(columns=sk_columns)

    tech_df['WeekId'] = (
        tech_df['WeekId']
        .replace(WeekIdMapper)
    )

    tech_df['DayStartLocation'] = (
        tech_df['DayStartLocation']
        .replace(day_start_end_code)
    )

    tech_df['DayEndLocation'] = (
        tech_df['DayEndLocation']
        .replace(day_start_end_code)
    )

    tech_df['driving_mode'] = (
        tech_df['driving_mode']
        .replace(driving_enum)
    )
    tech_df['Latitude'] = tech_df['Latitude'].apply(lambda x: round(x, 7))
    tech_df['Longitude'] = tech_df['Longitude'].apply(lambda x: round(x, 7))
    tech_df['driving_mode'] = tech_df['driving_mode'].fillna('average')
    tech_df['variation_percent'] = tech_df['variation_percent'].fillna(0)
    tech_df['driving_mode'] = tech_df['driving_mode'].astype(str).str.lower()

    return skills_df, tech_df


