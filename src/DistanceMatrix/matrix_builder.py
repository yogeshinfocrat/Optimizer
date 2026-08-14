from src.Mongo_Manager.db_repos.travel_data import TravelData, TravelDataRepository, get_flags_details
from src.DistanceMatrix.time_matrix_api import TimeMatrixAPI
from src.Mongo_Manager.schemas.beta.internal_schema import Data


def build_travel_matrix(
    object_id,
    requestId,
    user_details,
    dataSchema: Data,
    travel_data_repository: TravelDataRepository,
    api_key: str,
    log_flag
) -> list[list[TravelData]]:
    time_matrix_api = TimeMatrixAPI(travel_data_repository, api_key,requestId,user_details,object_id,log_flag)
    travel_matrix, failed_coordinates = time_matrix_api.get_travel_matrix(dataSchema)

    if len(failed_coordinates):
        return travel_matrix, failed_coordinates

    for i, row in enumerate(travel_matrix):
        for j, loc_ in enumerate(row):
            if not loc_:
                travel_matrix[i][j] = TravelData(origin='0.0,0.0', dest='0.0,0.0', distance=0, time=0)


    return travel_matrix, failed_coordinates
