
import pandas as pd
from typing import Optional


def find_allowed_vehicle_ids_new_fuction(event,
                tech_df,  skills_df, skill_flag,config, location_mode:Optional[str] = None) -> list[str]:
    """Finds the allowed vehicle ids. If lockTech is true, then only the lockTechId is allowed.
    If lockTech is false, then all technicians with all of the required skills are allowed
    """
    allowed_vehicle_ids: list[str] = []
    lockTech = event.get('lockTech')
    lockTechId = event.get('userPreferredTechnicianId')
    skills = event.get('serviceSysName')
    excludedTechIds = event.get('userNonPreferredTechnicianIds')

    tech_df = tech_df.assign(
        ConsiderSkillInRouteOptimization=config.ConsiderSkillInRouteOptimization,
        IsEnableRoGeofencing=config.IsEnableRoGeofencing,
        considerDriveTime=config.considerDriveTime,
        considerZipCode=config.considerZipCode,
        considerBranch=config.considerBranch,
        IsPropertyTypeInRO=config.IsPropertyTypeInRO
    )

    for ind, row in tech_df.iterrows():
        if lockTech and row.EmployeeNo == lockTech:
            if row.considerZipCode:
                if event.zip_code in row.ZipCodes:
                    if row.considerBranch:
                        if event.branch_id in row.BranchMasterId:
                            if row.IsPropertyTypeInRO:
                                if not pd.isna(row.get('PropertyType')):
                                    tech_property_type = row.get('PropertyType').split(', ')
                                else:
                                    tech_property_type = []
                                if event.property_type in tech_property_type:
                                    if row.ConsiderSkillInRouteOptimization:
                                        has_all_skills = True
                                        for event_skill in skills:
                                            try:
                                                tech_skills_list = \
                                                skills_df[skills_df['EmployeeNo'] == row.EmployeeNo][''].iloc[0]
                                            except:
                                                has_all_skills = False
                                                break
                                            tech_skills = [s for s in tech_skills_list if s == event_skill]
                                            if tech_skills.__len__() == 0:
                                                has_all_skills = False
                                                break
                                        has_all_attributes = True
                                        if not pd.isna(row.get('attributes_id')):
                                            tech_att = row.get('attributes_id').split(', ')
                                        else:
                                            tech_att = []

                                        if not pd.isna(event.get('ServicesAttribute')):
                                            event_att = event.get('ServicesAttribute').split(', ')
                                        else:
                                            event_att = []

                                        for att in event_att:
                                            if att not in tech_att:
                                                has_all_attributes = False
                                                break

                                        if has_all_skills and has_all_attributes:
                                            allowed_vehicle_ids.append(row.EmployeeNo)
                                            break
                                    else:
                                        allowed_vehicle_ids.append(row.EmployeeNo)
                                        break

                            else:
                                if row.ConsiderSkillInRouteOptimization:
                                    has_all_skills = True
                                    for event_skill in skills:
                                        try:
                                            tech_skills_list = \
                                                skills_df[skills_df['EmployeeNo'] == row.EmployeeNo][''].iloc[0]
                                        except:
                                            has_all_skills = False
                                            break
                                        tech_skills = [s for s in tech_skills_list if s == event_skill]
                                        if tech_skills.__len__() == 0:
                                            has_all_skills = False
                                            break
                                    has_all_attributes = True
                                    if not pd.isna(row.get('attributes_id')):
                                        tech_att = row.get('attributes_id').split(', ')
                                    else:
                                        tech_att = []

                                    if not pd.isna(event.get('ServicesAttribute')):
                                        event_att = event.get('ServicesAttribute').split(', ')
                                    else:
                                        event_att = []

                                    for att in event_att:
                                        if att not in tech_att:
                                            has_all_attributes = False
                                            break

                                    if has_all_skills and has_all_attributes:
                                        allowed_vehicle_ids.append(row.EmployeeNo)
                                        break
                                else:
                                    allowed_vehicle_ids.append(row.EmployeeNo)
                                    break
                    else:
                        if row.IsPropertyTypeInRO:
                            if not pd.isna(row.get('PropertyType')):
                                tech_property_type = row.get('PropertyType').split(', ')
                            else:
                                tech_property_type = []
                            if event.property_type in tech_property_type:
                                if row.ConsiderSkillInRouteOptimization:
                                    has_all_skills = True
                                    for event_skill in skills:
                                        try:
                                            tech_skills_list = \
                                                skills_df[skills_df['EmployeeNo'] == row.EmployeeNo][''].iloc[0]
                                        except:
                                            has_all_skills = False
                                            break
                                        tech_skills = [s for s in tech_skills_list if s == event_skill]
                                        if tech_skills.__len__() == 0:
                                            has_all_skills = False
                                            break
                                    has_all_attributes = True
                                    if not pd.isna(row.get('attributes_id')):
                                        tech_att = row.get('attributes_id').split(', ')
                                    else:
                                        tech_att = []

                                    if not pd.isna(event.get('ServicesAttribute')):
                                        event_att = event.get('ServicesAttribute').split(', ')
                                    else:
                                        event_att = []

                                    for att in event_att:
                                        if att not in tech_att:
                                            has_all_attributes = False
                                            break

                                    if has_all_skills and has_all_attributes:
                                        allowed_vehicle_ids.append(row.EmployeeNo)
                                        break
                                else:
                                    allowed_vehicle_ids.append(row.EmployeeNo)
                                    break

                        else:
                            if row.ConsiderSkillInRouteOptimization:
                                has_all_skills = True
                                for event_skill in skills:
                                    try:
                                        tech_skills_list = \
                                            skills_df[skills_df['EmployeeNo'] == row.EmployeeNo][''].iloc[0]
                                    except:
                                        has_all_skills = False
                                        break
                                    tech_skills = [s for s in tech_skills_list if s == event_skill]
                                    if tech_skills.__len__() == 0:
                                        has_all_skills = False
                                        break
                                has_all_attributes = True
                                if not pd.isna(row.get('attributes_id')):
                                    tech_att = row.get('attributes_id').split(', ')
                                else:
                                    tech_att = []

                                if not pd.isna(event.get('ServicesAttribute')):
                                    event_att = event.get('ServicesAttribute').split(', ')
                                else:
                                    event_att = []

                                for att in event_att:
                                    if att not in tech_att:
                                        has_all_attributes = False
                                        break

                                if has_all_skills and has_all_attributes:
                                    allowed_vehicle_ids.append(row.EmployeeNo)
                                    break
                            else:
                                allowed_vehicle_ids.append(row.EmployeeNo)
                                break
            elif row.IsEnableRoGeofencing:
                if row.EmployeeNo in event.get('inBoundEmployeeNo'):
                    if row.considerBranch:
                        if event.branch_id in row.BranchMasterId:
                            if row.IsPropertyTypeInRO:
                                if not pd.isna(row.get('PropertyType')):
                                    tech_property_type = row.get('PropertyType').split(', ')
                                else:
                                    tech_property_type = []
                                if event.property_type in tech_property_type:
                                    if row.ConsiderSkillInRouteOptimization:
                                        has_all_skills = True
                                        for event_skill in skills:
                                            try:
                                                tech_skills_list = \
                                                    skills_df[skills_df['EmployeeNo'] == row.EmployeeNo][''].iloc[0]
                                            except:
                                                has_all_skills = False
                                                break
                                            tech_skills = [s for s in tech_skills_list if s == event_skill]
                                            if tech_skills.__len__() == 0:
                                                has_all_skills = False
                                                break
                                        has_all_attributes = True
                                        if not pd.isna(row.get('attributes_id')):
                                            tech_att = row.get('attributes_id').split(', ')
                                        else:
                                            tech_att = []

                                        if not pd.isna(event.get('ServicesAttribute')):
                                            event_att = event.get('ServicesAttribute').split(', ')
                                        else:
                                            event_att = []

                                        for att in event_att:
                                            if att not in tech_att:
                                                has_all_attributes = False
                                                break

                                        if has_all_skills and has_all_attributes:
                                            allowed_vehicle_ids.append(row.EmployeeNo)
                                            break
                                    else:
                                        allowed_vehicle_ids.append(row.EmployeeNo)
                                        break

                            else:
                                if row.ConsiderSkillInRouteOptimization:
                                    has_all_skills = True
                                    for event_skill in skills:
                                        try:
                                            tech_skills_list = \
                                                skills_df[skills_df['EmployeeNo'] == row.EmployeeNo][''].iloc[0]
                                        except:
                                            has_all_skills = False
                                            break
                                        tech_skills = [s for s in tech_skills_list if s == event_skill]
                                        if tech_skills.__len__() == 0:
                                            has_all_skills = False
                                            break
                                    has_all_attributes = True
                                    if not pd.isna(row.get('attributes_id')):
                                        tech_att = row.get('attributes_id').split(', ')
                                    else:
                                        tech_att = []

                                    if not pd.isna(event.get('ServicesAttribute')):
                                        event_att = event.get('ServicesAttribute').split(', ')
                                    else:
                                        event_att = []

                                    for att in event_att:
                                        if att not in tech_att:
                                            has_all_attributes = False
                                            break

                                    if has_all_skills and has_all_attributes:
                                        allowed_vehicle_ids.append(row.EmployeeNo)
                                        break
                                else:
                                    allowed_vehicle_ids.append(row.EmployeeNo)
                                    break
                    else:
                        if row.IsPropertyTypeInRO:
                            if not pd.isna(row.get('PropertyType')):
                                tech_property_type = row.get('PropertyType').split(', ')
                            else:
                                tech_property_type = []
                            if event.property_type in tech_property_type:
                                if row.ConsiderSkillInRouteOptimization:
                                    has_all_skills = True
                                    for event_skill in skills:
                                        try:
                                            tech_skills_list = \
                                                skills_df[skills_df['EmployeeNo'] == row.EmployeeNo][''].iloc[0]
                                        except:
                                            has_all_skills = False
                                            break
                                        tech_skills = [s for s in tech_skills_list if s == event_skill]
                                        if tech_skills.__len__() == 0:
                                            has_all_skills = False
                                            break
                                    has_all_attributes = True
                                    if not pd.isna(row.get('attributes_id')):
                                        tech_att = row.get('attributes_id').split(', ')
                                    else:
                                        tech_att = []

                                    if not pd.isna(event.get('ServicesAttribute')):
                                        event_att = event.get('ServicesAttribute').split(', ')
                                    else:
                                        event_att = []

                                    for att in event_att:
                                        if att not in tech_att:
                                            has_all_attributes = False
                                            break

                                    if has_all_skills and has_all_attributes:
                                        allowed_vehicle_ids.append(row.EmployeeNo)
                                        break
                                else:
                                    allowed_vehicle_ids.append(row.EmployeeNo)
                                    break

                        else:
                            if row.ConsiderSkillInRouteOptimization:
                                has_all_skills = True
                                for event_skill in skills:
                                    try:
                                        tech_skills_list = \
                                            skills_df[skills_df['EmployeeNo'] == row.EmployeeNo][''].iloc[0]
                                    except:
                                        has_all_skills = False
                                        break
                                    tech_skills = [s for s in tech_skills_list if s == event_skill]
                                    if tech_skills.__len__() == 0:
                                        has_all_skills = False
                                        break
                                has_all_attributes = True
                                if not pd.isna(row.get('attributes_id')):
                                    tech_att = row.get('attributes_id').split(', ')
                                else:
                                    tech_att = []

                                if not pd.isna(event.get('ServicesAttribute')):
                                    event_att = event.get('ServicesAttribute').split(', ')
                                else:
                                    event_att = []

                                for att in event_att:
                                    if att not in tech_att:
                                        has_all_attributes = False
                                        break

                                if has_all_skills and has_all_attributes:
                                    allowed_vehicle_ids.append(row.EmployeeNo)
                                    break
                            else:
                                allowed_vehicle_ids.append(row.EmployeeNo)
                                break
            else:
                if row.considerBranch:
                    if event.branch_id in row.BranchMasterId:
                        if row.IsPropertyTypeInRO:
                            if not pd.isna(row.get('PropertyType')):
                                tech_property_type = row.get('PropertyType').split(', ')
                            else:
                                tech_property_type = []
                            if event.property_type in tech_property_type:
                                if row.ConsiderSkillInRouteOptimization:
                                    has_all_skills = True
                                    for event_skill in skills:
                                        try:
                                            tech_skills_list = \
                                                skills_df[skills_df['EmployeeNo'] == row.EmployeeNo][''].iloc[0]
                                        except:
                                            has_all_skills = False
                                            break
                                        tech_skills = [s for s in tech_skills_list if s == event_skill]
                                        if tech_skills.__len__() == 0:
                                            has_all_skills = False
                                            break
                                    has_all_attributes = True
                                    if not pd.isna(row.get('attributes_id')):
                                        tech_att = row.get('attributes_id').split(', ')
                                    else:
                                        tech_att = []

                                    if not pd.isna(event.get('ServicesAttribute')):
                                        event_att = event.get('ServicesAttribute').split(', ')
                                    else:
                                        event_att = []

                                    for att in event_att:
                                        if att not in tech_att:
                                            has_all_attributes = False
                                            break

                                    if has_all_skills and has_all_attributes:
                                        allowed_vehicle_ids.append(row.EmployeeNo)
                                        break
                                else:
                                    allowed_vehicle_ids.append(row.EmployeeNo)
                                    break

                        else:
                            if row.ConsiderSkillInRouteOptimization:
                                has_all_skills = True
                                for event_skill in skills:
                                    try:
                                        tech_skills_list = \
                                            skills_df[skills_df['EmployeeNo'] == row.EmployeeNo][''].iloc[0]
                                    except:
                                        has_all_skills = False
                                        break
                                    tech_skills = [s for s in tech_skills_list if s == event_skill]
                                    if tech_skills.__len__() == 0:
                                        has_all_skills = False
                                        break
                                has_all_attributes = True
                                if not pd.isna(row.get('attributes_id')):
                                    tech_att = row.get('attributes_id').split(', ')
                                else:
                                    tech_att = []

                                if not pd.isna(event.get('ServicesAttribute')):
                                    event_att = event.get('ServicesAttribute').split(', ')
                                else:
                                    event_att = []

                                for att in event_att:
                                    if att not in tech_att:
                                        has_all_attributes = False
                                        break

                                if has_all_skills and has_all_attributes:
                                    allowed_vehicle_ids.append(row.EmployeeNo)
                                    break
                            else:
                                allowed_vehicle_ids.append(row.EmployeeNo)
                                break
                else:
                    if row.IsPropertyTypeInRO:
                        if not pd.isna(row.get('PropertyType')):
                            tech_property_type = row.get('PropertyType').split(', ')
                        else:
                            tech_property_type = []
                        if event.property_type in tech_property_type:
                            if row.ConsiderSkillInRouteOptimization:
                                has_all_skills = True
                                for event_skill in skills:
                                    try:
                                        tech_skills_list = \
                                            skills_df[skills_df['EmployeeNo'] == row.EmployeeNo][''].iloc[0]
                                    except:
                                        has_all_skills = False
                                        break
                                    tech_skills = [s for s in tech_skills_list if s == event_skill]
                                    if tech_skills.__len__() == 0:
                                        has_all_skills = False
                                        break
                                has_all_attributes = True
                                if not pd.isna(row.get('attributes_id')):
                                    tech_att = row.get('attributes_id').split(', ')
                                else:
                                    tech_att = []

                                if not pd.isna(event.get('ServicesAttribute')):
                                    event_att = event.get('ServicesAttribute').split(', ')
                                else:
                                    event_att = []

                                for att in event_att:
                                    if att not in tech_att:
                                        has_all_attributes = False
                                        break

                                if has_all_skills and has_all_attributes:
                                    allowed_vehicle_ids.append(row.EmployeeNo)
                                    break
                            else:
                                allowed_vehicle_ids.append(row.EmployeeNo)
                                break

                    else:
                        if row.ConsiderSkillInRouteOptimization:
                            has_all_skills = True
                            for event_skill in skills:
                                try:
                                    tech_skills_list = \
                                        skills_df[skills_df['EmployeeNo'] == row.EmployeeNo][''].iloc[0]
                                except:
                                    has_all_skills = False
                                    break
                                tech_skills = [s for s in tech_skills_list if s == event_skill]
                                if tech_skills.__len__() == 0:
                                    has_all_skills = False
                                    break
                            has_all_attributes = True
                            if not pd.isna(row.get('attributes_id')):
                                tech_att = row.get('attributes_id').split(', ')
                            else:
                                tech_att = []

                            if not pd.isna(event.get('ServicesAttribute')):
                                event_att = event.get('ServicesAttribute').split(', ')
                            else:
                                event_att = []

                            for att in event_att:
                                if att not in tech_att:
                                    has_all_attributes = False
                                    break

                            if has_all_skills and has_all_attributes:
                                allowed_vehicle_ids.append(row.EmployeeNo)
                                break
                        else:
                            allowed_vehicle_ids.append(row.EmployeeNo)
                            break
        else:
            if row.considerZipCode:
                if event.zip_code in row.ZipCodes:
                    if row.considerBranch:
                        if event.branch_id in row.BranchMasterId:
                            if row.IsPropertyTypeInRO:
                                if not pd.isna(row.get('PropertyType')):
                                    tech_property_type = row.get('PropertyType').split(', ')
                                else:
                                    tech_property_type = []
                                if event.property_type in tech_property_type:
                                    if row.ConsiderSkillInRouteOptimization:
                                        has_all_skills = True
                                        for event_skill in skills:
                                            try:
                                                tech_skills_list = \
                                                    skills_df[skills_df['EmployeeNo'] == row.EmployeeNo][''].iloc[0]
                                            except:
                                                has_all_skills = False
                                                break
                                            tech_skills = [s for s in tech_skills_list if s == event_skill]
                                            if tech_skills.__len__() == 0:
                                                has_all_skills = False
                                                break
                                        has_all_attributes = True
                                        if not pd.isna(row.get('attributes_id')):
                                            tech_att = row.get('attributes_id').split(', ')
                                        else:
                                            tech_att = []

                                        if not pd.isna(event.get('ServicesAttribute')):
                                            event_att = event.get('ServicesAttribute').split(', ')
                                        else:
                                            event_att = []

                                        for att in event_att:
                                            if att not in tech_att:
                                                has_all_attributes = False
                                                break

                                        if has_all_skills and has_all_attributes:
                                            allowed_vehicle_ids.append(row.EmployeeNo)
                                            break
                                    else:
                                        allowed_vehicle_ids.append(row.EmployeeNo)
                                        break

                            else:
                                if row.ConsiderSkillInRouteOptimization:
                                    has_all_skills = True
                                    for event_skill in skills:
                                        try:
                                            tech_skills_list = \
                                                skills_df[skills_df['EmployeeNo'] == row.EmployeeNo][''].iloc[0]
                                        except:
                                            has_all_skills = False
                                            break
                                        tech_skills = [s for s in tech_skills_list if s == event_skill]
                                        if tech_skills.__len__() == 0:
                                            has_all_skills = False
                                            break
                                    has_all_attributes = True
                                    if not pd.isna(row.get('attributes_id')):
                                        tech_att = row.get('attributes_id').split(', ')
                                    else:
                                        tech_att = []

                                    if not pd.isna(event.get('ServicesAttribute')):
                                        event_att = event.get('ServicesAttribute').split(', ')
                                    else:
                                        event_att = []

                                    for att in event_att:
                                        if att not in tech_att:
                                            has_all_attributes = False
                                            break

                                    if has_all_skills and has_all_attributes:
                                        allowed_vehicle_ids.append(row.EmployeeNo)
                                        break
                                else:
                                    allowed_vehicle_ids.append(row.EmployeeNo)
                                    break
                    else:
                        if row.IsPropertyTypeInRO:
                            if not pd.isna(row.get('PropertyType')):
                                tech_property_type = row.get('PropertyType').split(', ')
                            else:
                                tech_property_type = []
                            if event.property_type in tech_property_type:
                                if row.ConsiderSkillInRouteOptimization:
                                    has_all_skills = True
                                    for event_skill in skills:
                                        try:
                                            tech_skills_list = \
                                                skills_df[skills_df['EmployeeNo'] == row.EmployeeNo][''].iloc[0]
                                        except:
                                            has_all_skills = False
                                            break
                                        tech_skills = [s for s in tech_skills_list if s == event_skill]
                                        if tech_skills.__len__() == 0:
                                            has_all_skills = False
                                            break
                                    has_all_attributes = True
                                    if not pd.isna(row.get('attributes_id')):
                                        tech_att = row.get('attributes_id').split(', ')
                                    else:
                                        tech_att = []

                                    if not pd.isna(event.get('ServicesAttribute')):
                                        event_att = event.get('ServicesAttribute').split(', ')
                                    else:
                                        event_att = []

                                    for att in event_att:
                                        if att not in tech_att:
                                            has_all_attributes = False
                                            break

                                    if has_all_skills and has_all_attributes:
                                        allowed_vehicle_ids.append(row.EmployeeNo)
                                        break
                                else:
                                    allowed_vehicle_ids.append(row.EmployeeNo)
                                    break

                        else:
                            if row.ConsiderSkillInRouteOptimization:
                                has_all_skills = True
                                for event_skill in skills:
                                    try:
                                        tech_skills_list = \
                                            skills_df[skills_df['EmployeeNo'] == row.EmployeeNo][''].iloc[0]
                                    except:
                                        has_all_skills = False
                                        break
                                    tech_skills = [s for s in tech_skills_list if s == event_skill]
                                    if tech_skills.__len__() == 0:
                                        has_all_skills = False
                                        break
                                has_all_attributes = True
                                if not pd.isna(row.get('attributes_id')):
                                    tech_att = row.get('attributes_id').split(', ')
                                else:
                                    tech_att = []

                                if not pd.isna(event.get('ServicesAttribute')):
                                    event_att = event.get('ServicesAttribute').split(', ')
                                else:
                                    event_att = []

                                for att in event_att:
                                    if att not in tech_att:
                                        has_all_attributes = False
                                        break

                                if has_all_skills and has_all_attributes:
                                    allowed_vehicle_ids.append(row.EmployeeNo)
                                    break
                            else:
                                allowed_vehicle_ids.append(row.EmployeeNo)
                                break
            elif row.IsEnableRoGeofencing:
                if row.EmployeeNo in event.get('inBoundEmployeeNo'):
                    if row.considerBranch:
                        if event.branch_id in row.BranchMasterId:
                            if row.IsPropertyTypeInRO:
                                if not pd.isna(row.get('PropertyType')):
                                    tech_property_type = row.get('PropertyType').split(', ')
                                else:
                                    tech_property_type = []
                                if event.property_type in tech_property_type:
                                    if row.ConsiderSkillInRouteOptimization:
                                        has_all_skills = True
                                        for event_skill in skills:
                                            try:
                                                tech_skills_list = \
                                                    skills_df[skills_df['EmployeeNo'] == row.EmployeeNo][''].iloc[0]
                                            except:
                                                has_all_skills = False
                                                break
                                            tech_skills = [s for s in tech_skills_list if s == event_skill]
                                            if tech_skills.__len__() == 0:
                                                has_all_skills = False
                                                break
                                        has_all_attributes = True
                                        if not pd.isna(row.get('attributes_id')):
                                            tech_att = row.get('attributes_id').split(', ')
                                        else:
                                            tech_att = []

                                        if not pd.isna(event.get('ServicesAttribute')):
                                            event_att = event.get('ServicesAttribute').split(', ')
                                        else:
                                            event_att = []

                                        for att in event_att:
                                            if att not in tech_att:
                                                has_all_attributes = False
                                                break

                                        if has_all_skills and has_all_attributes:
                                            allowed_vehicle_ids.append(row.EmployeeNo)
                                            break
                                    else:
                                        allowed_vehicle_ids.append(row.EmployeeNo)
                                        break

                            else:
                                if row.ConsiderSkillInRouteOptimization:
                                    has_all_skills = True
                                    for event_skill in skills:
                                        try:
                                            tech_skills_list = \
                                                skills_df[skills_df['EmployeeNo'] == row.EmployeeNo][''].iloc[0]
                                        except:
                                            has_all_skills = False
                                            break
                                        tech_skills = [s for s in tech_skills_list if s == event_skill]
                                        if tech_skills.__len__() == 0:
                                            has_all_skills = False
                                            break
                                    has_all_attributes = True
                                    if not pd.isna(row.get('attributes_id')):
                                        tech_att = row.get('attributes_id').split(', ')
                                    else:
                                        tech_att = []

                                    if not pd.isna(event.get('ServicesAttribute')):
                                        event_att = event.get('ServicesAttribute').split(', ')
                                    else:
                                        event_att = []

                                    for att in event_att:
                                        if att not in tech_att:
                                            has_all_attributes = False
                                            break

                                    if has_all_skills and has_all_attributes:
                                        allowed_vehicle_ids.append(row.EmployeeNo)
                                        break
                                else:
                                    allowed_vehicle_ids.append(row.EmployeeNo)
                                    break
                    else:
                        if row.IsPropertyTypeInRO:
                            if not pd.isna(row.get('PropertyType')):
                                tech_property_type = row.get('PropertyType').split(', ')
                            else:
                                tech_property_type = []
                            if event.property_type in tech_property_type:
                                if row.ConsiderSkillInRouteOptimization:
                                    has_all_skills = True
                                    for event_skill in skills:
                                        try:
                                            tech_skills_list = \
                                                skills_df[skills_df['EmployeeNo'] == row.EmployeeNo][''].iloc[0]
                                        except:
                                            has_all_skills = False
                                            break
                                        tech_skills = [s for s in tech_skills_list if s == event_skill]
                                        if tech_skills.__len__() == 0:
                                            has_all_skills = False
                                            break
                                    has_all_attributes = True
                                    if not pd.isna(row.get('attributes_id')):
                                        tech_att = row.get('attributes_id').split(', ')
                                    else:
                                        tech_att = []

                                    if not pd.isna(event.get('ServicesAttribute')):
                                        event_att = event.get('ServicesAttribute').split(', ')
                                    else:
                                        event_att = []

                                    for att in event_att:
                                        if att not in tech_att:
                                            has_all_attributes = False
                                            break

                                    if has_all_skills and has_all_attributes:
                                        allowed_vehicle_ids.append(row.EmployeeNo)
                                        break
                                else:
                                    allowed_vehicle_ids.append(row.EmployeeNo)
                                    break

                        else:
                            if row.ConsiderSkillInRouteOptimization:
                                has_all_skills = True
                                for event_skill in skills:
                                    try:
                                        tech_skills_list = \
                                            skills_df[skills_df['EmployeeNo'] == row.EmployeeNo][''].iloc[0]
                                    except:
                                        has_all_skills = False
                                        break
                                    tech_skills = [s for s in tech_skills_list if s == event_skill]
                                    if tech_skills.__len__() == 0:
                                        has_all_skills = False
                                        break
                                has_all_attributes = True
                                if not pd.isna(row.get('attributes_id')):
                                    tech_att = row.get('attributes_id').split(', ')
                                else:
                                    tech_att = []

                                if not pd.isna(event.get('ServicesAttribute')):
                                    event_att = event.get('ServicesAttribute').split(', ')
                                else:
                                    event_att = []

                                for att in event_att:
                                    if att not in tech_att:
                                        has_all_attributes = False
                                        break

                                if has_all_skills and has_all_attributes:
                                    allowed_vehicle_ids.append(row.EmployeeNo)
                                    break
                            else:
                                allowed_vehicle_ids.append(row.EmployeeNo)
                                break
            else:
                if row.considerBranch:
                    if event.branch_id in row.BranchMasterId:
                        if row.IsPropertyTypeInRO:
                            if not pd.isna(row.get('PropertyType')):
                                tech_property_type = row.get('PropertyType').split(', ')
                            else:
                                tech_property_type = []
                            if event.property_type in tech_property_type:
                                if row.ConsiderSkillInRouteOptimization:
                                    has_all_skills = True
                                    for event_skill in skills:
                                        try:
                                            tech_skills_list = \
                                                skills_df[skills_df['EmployeeNo'] == row.EmployeeNo][''].iloc[0]
                                        except:
                                            has_all_skills = False
                                            break
                                        tech_skills = [s for s in tech_skills_list if s == event_skill]
                                        if tech_skills.__len__() == 0:
                                            has_all_skills = False
                                            break
                                    has_all_attributes = True
                                    if not pd.isna(row.get('attributes_id')):
                                        tech_att = row.get('attributes_id').split(', ')
                                    else:
                                        tech_att = []

                                    if not pd.isna(event.get('ServicesAttribute')):
                                        event_att = event.get('ServicesAttribute').split(', ')
                                    else:
                                        event_att = []

                                    for att in event_att:
                                        if att not in tech_att:
                                            has_all_attributes = False
                                            break

                                    if has_all_skills and has_all_attributes:
                                        allowed_vehicle_ids.append(row.EmployeeNo)
                                        break
                                else:
                                    allowed_vehicle_ids.append(row.EmployeeNo)
                                    break

                        else:
                            if row.ConsiderSkillInRouteOptimization:
                                has_all_skills = True
                                for event_skill in skills:
                                    try:
                                        tech_skills_list = \
                                            skills_df[skills_df['EmployeeNo'] == row.EmployeeNo][''].iloc[0]
                                    except:
                                        has_all_skills = False
                                        break
                                    tech_skills = [s for s in tech_skills_list if s == event_skill]
                                    if tech_skills.__len__() == 0:
                                        has_all_skills = False
                                        break
                                has_all_attributes = True
                                if not pd.isna(row.get('attributes_id')):
                                    tech_att = row.get('attributes_id').split(', ')
                                else:
                                    tech_att = []

                                if not pd.isna(event.get('ServicesAttribute')):
                                    event_att = event.get('ServicesAttribute').split(', ')
                                else:
                                    event_att = []

                                for att in event_att:
                                    if att not in tech_att:
                                        has_all_attributes = False
                                        break

                                if has_all_skills and has_all_attributes:
                                    allowed_vehicle_ids.append(row.EmployeeNo)
                                    break
                            else:
                                allowed_vehicle_ids.append(row.EmployeeNo)
                                break
                else:
                    if row.IsPropertyTypeInRO:
                        if not pd.isna(row.get('PropertyType')):
                            tech_property_type = row.get('PropertyType').split(', ')
                        else:
                            tech_property_type = []
                        if event.property_type in tech_property_type:
                            if row.ConsiderSkillInRouteOptimization:
                                has_all_skills = True
                                for event_skill in skills:
                                    try:
                                        tech_skills_list = \
                                            skills_df[skills_df['EmployeeNo'] == row.EmployeeNo][''].iloc[0]
                                    except:
                                        has_all_skills = False
                                        break
                                    tech_skills = [s for s in tech_skills_list if s == event_skill]
                                    if tech_skills.__len__() == 0:
                                        has_all_skills = False
                                        break
                                has_all_attributes = True
                                if not pd.isna(row.get('attributes_id')):
                                    tech_att = row.get('attributes_id').split(', ')
                                else:
                                    tech_att = []

                                if not pd.isna(event.get('ServicesAttribute')):
                                    event_att = event.get('ServicesAttribute').split(', ')
                                else:
                                    event_att = []

                                for att in event_att:
                                    if att not in tech_att:
                                        has_all_attributes = False
                                        break

                                if has_all_skills and has_all_attributes:
                                    allowed_vehicle_ids.append(row.EmployeeNo)
                                    break
                            else:
                                allowed_vehicle_ids.append(row.EmployeeNo)
                                break

                    else:
                        if row.ConsiderSkillInRouteOptimization:
                            has_all_skills = True
                            for event_skill in skills:
                                try:
                                    tech_skills_list = \
                                        skills_df[skills_df['EmployeeNo'] == row.EmployeeNo][''].iloc[0]
                                except:
                                    has_all_skills = False
                                    break
                                tech_skills = [s for s in tech_skills_list if s == event_skill]
                                if tech_skills.__len__() == 0:
                                    has_all_skills = False
                                    break
                            has_all_attributes = True
                            if not pd.isna(row.get('attributes_id')):
                                tech_att = row.get('attributes_id').split(', ')
                            else:
                                tech_att = []

                            if not pd.isna(event.get('ServicesAttribute')):
                                event_att = event.get('ServicesAttribute').split(', ')
                            else:
                                event_att = []

                            for att in event_att:
                                if att not in tech_att:
                                    has_all_attributes = False
                                    break

                            if has_all_skills and has_all_attributes:
                                allowed_vehicle_ids.append(row.EmployeeNo)
                                break
                        else:
                            allowed_vehicle_ids.append(row.EmployeeNo)
                            break

    return allowed_vehicle_ids



def _get_tech_skills(skills_df: pd.DataFrame, employee_no) -> list:
    """Return the list of skill codes for a technician, or [] if none found."""
    matches = skills_df.loc[skills_df['EmployeeNo'] == employee_no, 'Skills']
    if matches.empty:
        return []
    skills = matches.iloc[0]
    return skills if isinstance(skills, list) else []


def _has_all_skills(tech_skills: list, required_skills: list) -> bool:
    return all(skill in tech_skills for skill in required_skills)


def _has_all_attributes(tech_attributes_raw, event_attributes_raw) -> bool:
    tech_attrs = tech_attributes_raw.split(', ') if pd.notna(tech_attributes_raw) else []
    event_attrs = event_attributes_raw.split(', ') if pd.notna(event_attributes_raw) else []
    return all(attr in tech_attrs for attr in event_attrs)


def _passes_location_check(row, event) -> bool:

    """Zip-code check takes priority; falls back to geofencing; else unrestricted."""
    if row.considerZipCode:
        if isinstance(row.ZipCodes, list):
            tech_zip_codes = row.ZipCodes
        elif pd.isna(row.ZipCodes):
            tech_zip_codes = []
        else:
            tech_zip_codes = [z.strip() for z in str(row.ZipCodes).split(',')]
        return event.get('Zipcode') in tech_zip_codes
    if row.IsEnableRoGeofencing:
        return row.EmployeeNo in (event.get('inBoundEmployeeNo') or [])
    return True


def _passes_branch_check(row, event) -> bool:
    if not row.considerBranch:
        return True
    return event.get('branchId') in row.BranchMasterId


def _passes_property_type_check(row, event) -> bool:
    if not row.IsPropertyTypeInRO:
        return True
    tech_property_types = (
        row.get('PropertyType').split(', ') if pd.notna(row.get('PropertyType')) else []
    )
    return event.get('PropertyType') in tech_property_types


def _passes_skill_and_attribute_check(row, event, skills_df, required_skills) -> bool:
    if not row.ConsiderSkillInRouteOptimization:
        return True
    tech_skills = _get_tech_skills(skills_df, row.EmployeeNo)
    if not _has_all_skills(tech_skills, required_skills):
        return False
    return _has_all_attributes(row.get('attributes_id'), event.get('ServicesAttribute'))


def _is_tech_eligible(row, event, skills_df, required_skills) -> bool:
    return (
        _passes_location_check(row, event)
        and _passes_branch_check(row, event)
        and _passes_property_type_check(row, event)
        and _passes_skill_and_attribute_check(row, event, skills_df, required_skills)
    )


def find_allowed_vehicle_ids_flatten(
    event,
    tech_df: pd.DataFrame,
    skills_df: pd.DataFrame,
    config
) -> list:
    """
    Finds the allowed vehicle (technician) ids for an event.

    - If the event has a locked technician (`lockTech` is true and a
      `userPreferredTechnicianId` is set), only that technician is
      considered, and only returned if they pass all eligibility checks.
    - Otherwise, every technician who passes all eligibility checks
      (location, branch, property type, skills, attributes) is returned.
    - Technicians explicitly excluded via `userNonPreferredTechnicianIds`
      are never eligible, even if they are the locked technician.
    """
    lock_tech_id = event.get('userPreferredTechnicianId')
    is_locked = bool(event.get('lockTech')) and lock_tech_id is not None
    excluded_tech_ids = set(event.get('userNonPreferredTechnicianIds') or [])
    required_skills = event.get('serviceSysName') or []

    tech_df = tech_df.assign(
        ConsiderSkillInRouteOptimization=config.ConsiderSkillInRouteOptimization,
        IsEnableRoGeofencing=config.IsEnableRoGeofencing,
        considerDriveTime=config.considerDriveTime,
        considerZipCode=config.considerZipCode,
        considerBranch=config.considerBranch,
        IsPropertyTypeInRO=config.IsPropertyTypeInRO,
    )

    allowed_vehicle_ids: list = []

    for _, row in tech_df.iterrows():
        if row.EmployeeNo in excluded_tech_ids:
            continue

        if is_locked:
            if row.EmployeeNo != lock_tech_id:
                continue
            if _is_tech_eligible(row, event, skills_df, required_skills):
                allowed_vehicle_ids.append(row.EmployeeNo)
            break  # the locked technician has been resolved; no one else matters
        else:
            if _is_tech_eligible(row, event, skills_df, required_skills):
                allowed_vehicle_ids.append(row.EmployeeNo)

    return allowed_vehicle_ids