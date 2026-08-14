from typing import Callable
import googlemaps
from src.Mongo_Manager.db_repos.travel_data import TravelData, TravelDataRepository
from src.Mongo_Manager.db_repos.cost_analysis import ApiData, ApiDataManager
from src.Mongo_Manager.schemas.beta.internal_schema import Data
from src.Utils.log import logger
import time
from datetime import datetime
from src.Utils.config import GlobalConfig

class TimeMatrixAPI:
    """Time Matrix API"""

    def __init__(self, travel_data_repository: TravelDataRepository, api_key: str | None, requestId, user_details,
                 object_id, log_flag):
        """Constructor"""
        self.travel_data_repository = travel_data_repository
        self.api_key = api_key
        self.log_flag  = log_flag
        self.failed_coordinates = []  # Store failed coordinates here
        if GlobalConfig.UNIVERSAL_KEY:
            self.api_key = GlobalConfig.UNIVERSAL_KEY
        else:
            self.api_key = api_key
        # Need to set this to False in production.
        self.debug = GlobalConfig.DEBUG_FLAG
        self.request_id = requestId
        self.client_id = user_details['clientID']
        self.user_id = user_details['userID']
        self.object_id = object_id


    def sub_batch_processing(self, callback: Callable[[list[str], list[str]], list[TravelData]], loc,
                             travel_data_from_db, all_pairs):
        pairs = [(
            loc[i], loc[i + 1], loc[i + 2], loc[i + 3], loc[i + 4])
            for i in range(0, len(loc) - 4, 5)]
        # Generate combinations of pairs
        combinations = []
        for pair1 in pairs:
            for pair2 in pairs:
                combinations.append((pair1, pair2))
        logger.info(f"Number of Sub-batches formed: {len(combinations)}")

        # Create a list of all location pairs from the combinations
        loc_pairs = []
        travel_data_from_api = []
        # Process each combination of pairs
        for combo in combinations:
            origins = combo[0]
            destinations = combo[1]
            data_from_db_within_batch = []

            # Elements with in batch i.e. 100
            batch_pairs = []
            for org in origins:
                for dest in destinations:
                    batch_pairs.append((org, dest))
                    loc_pairs.append((org, dest))

            for i in travel_data_from_db:
                if (str(i.origin), str(i.dest)) in batch_pairs:
                    # Removing elements that are already present in DB.
                    data_from_db_within_batch.append(i)
                    batch_pairs.remove((str(i.origin), str(i.dest)))

            present_in_db = len(data_from_db_within_batch)
            if len(batch_pairs) > 15:
                # Checkpoint - API CALLS Restrictions.
                self.api_key = self.remaining_api_calls_check(25)
                # If less than 10 pairs are found in the database, call API for all 25 pairs at once
                # print(f"{present_in_db} Element found in DB in this batch calling API for all 25 elements at once")
                # print(f"Extra charged ${round(present_in_db * 0.004, 4)}")
                origin_addresses = list(combo[0])
                destination_addresses = list(combo[1])
                response = callback(origin_addresses, destination_addresses)
                # Inserting all 100 elements to DB.
                self.travel_data_repository.batch_insert_travel_data(response)
                travel_data_from_api.extend(response)
                # Inserting API DATA to DB
                api_data = ApiData(request_id=self.request_id, date=datetime.now(), estimated_cost=25 * 0.004,
                                   key=self.api_key,
                                   elements=25, company_id=self.client_id, user_id=self.user_id,
                                   all_elements=len(all_pairs), object_id=self.object_id)
                result = ApiDataManager.insert_or_update_api_data(api_data)
                # print(f"Upserted API-DATA id: {result.upserted_id}")

            else:
                # If 20 or more pairs are found in the database,
                # call API for the remaining pairs one by one removing all the pairs that are in DB
                # log_info(f"Found {present_in_db} elements out of 100 elements in DB in single batch")
                # Only call api if all 100 elements are not in DB.
                if (present_in_db - 25) and len(batch_pairs):
                    # Checkpoint - API CALLS Restrictions.
                    self.api_key = self.remaining_api_calls_check(25 - present_in_db)
                    logger.info(f"Calling API one by one for {25 - present_in_db} elements for this batch")
                    travel_data_from_api.extend(self.split_callback(self.get_travel_matrix_from_api, batch_pairs))
                    # Inserting API DATA to DB
                    api_data = ApiData(request_id=self.request_id, date=datetime.now(),
                                       estimated_cost=len(batch_pairs) * 0.004, key=self.api_key,
                                       elements=len(batch_pairs), company_id=self.client_id, user_id=self.user_id,
                                       all_elements=len(all_pairs), object_id=self.object_id)
                    result = ApiDataManager.insert_or_update_api_data(api_data)
                    # print(f"Upserted API-DATA id: {result.upserted_id}")

                travel_data_from_api.extend(data_from_db_within_batch)
                # log_info(f"Catching {len(data_from_db_within_batch)} elements from DB in this batch.")

        return travel_data_from_api


    def batch_processing(self, callback: Callable[[list[str], list[str]], list[TravelData]], loc, travel_data_from_db,
                         all_pairs):
        """
        Processes a list of locations to generate pairs and combinations,
        then checks these pairs against a database and decides on further action
        whether to call GOOGLE API or NOT.

        Args:
            loc (list): List of unique locations.
            travel_data_from_db (list): List of elements that found in the database.
            all_pairs (list): List of all possible elements with all events and technician.

        Returns:
            list: Processed travel data, combining API results and data from the database.

        Note:
            1) For less than 9 events api will be called one by one for all the elements that are not in DB.
            2) For more than 9 events batches will be formed each batch contains 100 elements
                ** if in one batch out of 100 elements more than 20 elements present in DB then
                    GOOGLE API will be called one by one for all remaining elements
                ** if in one batch out 100 elements less than 20 elements found in DB then
                    GOOGLE API will be called one time for all elements.
            3) Max we can send 100 elements to google api that's why batch size 100 decided.
            4) Single api call with 100 elements takes 1.2 sec, while api call for one elements takes .57 sec.
        """
        start_time = time.time()
        additional_elements = 0
        # Create pairs from the list in chunks of 10 elements
        pairs = [(
            loc[i], loc[i + 1], loc[i + 2], loc[i + 3], loc[i + 4], loc[i + 5], loc[i + 6], loc[i + 7], loc[i + 8],
            loc[i + 9])
            for i in range(0, len(loc) - 9, 10)]

        # Generate combinations of pairs
        combinations = []
        for pair1 in pairs:
            for pair2 in pairs:
                combinations.append((pair1, pair2))

        logger.info(f"Number of batches formed: {len(combinations)}")

        # Create a list of all location pairs from the combinations
        loc_pairs = []
        travel_data_from_api = []
        # Process each combination of pairs
        for combo in combinations:
            origins = combo[0]
            destinations = combo[1]
            data_from_db_within_batch = []

            # Elements with in batch i.e. 100
            batch_pairs = []
            for org in origins:
                for dest in destinations:
                    batch_pairs.append((org, dest))
                    loc_pairs.append((org, dest))

            for i in travel_data_from_db:
                if (str(i.origin), str(i.dest)) in batch_pairs:
                    # Removing elements that are already present in DB.
                    data_from_db_within_batch.append(i)
                    batch_pairs.remove((str(i.origin), str(i.dest)))

            present_in_db = len(data_from_db_within_batch)
            if len(batch_pairs) > 40:
                # Checkpoint - API CALLS Restrictions.
                self.api_key = self.remaining_api_calls_check(100)
                # If less than 20 pairs are found in the database, call API for all 100 pairs at once
                # print(f"{present_in_db} Element found in DB in this batch calling API for all 100 elements at once")
                # print(f"Extra charged ${round(present_in_db * 0.004, 4)}")
                additional_elements += present_in_db
                origin_addresses = list(combo[0])
                destination_addresses = list(combo[1])
                response = callback(origin_addresses, destination_addresses)
                # Inserting all 100 elements to DB.
                self.travel_data_repository.batch_insert_travel_data(response)
                travel_data_from_api.extend(response)
                # Inserting API DATA to DB
                api_data = ApiData(request_id=self.request_id, date=datetime.now(), estimated_cost=100 * 0.004,
                                   key=self.api_key,
                                   elements=100, company_id=self.client_id, user_id=self.user_id,
                                   all_elements=len(all_pairs), object_id=self.object_id)
                result = ApiDataManager.insert_or_update_api_data(api_data)
                # print(f"Upserted API-DATA id: {result.upserted_id}")

            else:
                # If 20 or more pairs are found in the database,
                # call API for the remaining pairs one by one removing all the pairs that are in DB
                # log_info(f"Found {present_in_db} elements out of 100 elements in DB in single batch creating sub batches")
                # Only call api if all 100 elements are not in DB.
                if (present_in_db - 100) and len(batch_pairs):
                    # Checkpoint - API CALLS Restrictions.
                    self.api_key = self.remaining_api_calls_check(100 - present_in_db)
                    logger.info(f"Calling API one by one for {100 - present_in_db} elements for this batch")
                    travel_data_from_api.extend(self.split_callback(self.get_travel_matrix_from_api, batch_pairs))
                    # Inserting API DATA to DB
                    api_data = ApiData(request_id=self.request_id, date=datetime.now(),
                                       estimated_cost=len(batch_pairs) * 0.004, key=self.api_key,
                                       elements=len(batch_pairs), company_id=self.client_id, user_id=self.user_id,
                                       all_elements=len(all_pairs), object_id=self.object_id)
                    result = ApiDataManager.insert_or_update_api_data(api_data)
                    # print(f"Upserted API-DATA id: {result.upserted_id}")

                travel_data_from_api.extend(data_from_db_within_batch)

                # Checkpoint - API CALLS Restrictions.
                #     self.api_key = self.remaining_api_calls_check(100 - present_in_db)
                #
                #     # Creating sub batch of smaller sizes
                #     response = self.sub_batch_processing(self.get_travel_matrix_from_api, combo[0],
                #                                          travel_data_from_db, all_pairs)
                #     travel_data_from_api.extend(response)
                # else:
                #     travel_data_from_api.extend(data_from_db_within_batch)
                # log_info(f"Catching {len(data_from_db_within_batch)} elements from DB in this batch.")

        # Determine the pairs that are not in the previously created pairs
        remaining_pairs = list(set(all_pairs).difference(set(loc_pairs)))

        for i in travel_data_from_db:
            if (str(i.origin), str(i.dest)) in remaining_pairs:
                # Adding element to travel data from api that are already present in DB.
                travel_data_from_api.append(i)
                # Removing elements that are already present in DB.
                remaining_pairs.remove((str(i.origin), str(i.dest)))

        # log_info(f"Catching {len(travel_data_from_api)} elements from DB in this batch.")

        if len(remaining_pairs):
            # Checkpoint - API CALLS Restrictions.
            self.api_key = self.remaining_api_calls_check(len(remaining_pairs))
            logger.info(f"Calling Google Map API for {len(remaining_pairs)} elements")
            # Call the API for each of the remaining pairs that are not present in DB
            travel_data_from_api.extend(self.split_callback(self.get_travel_matrix_from_api,
                                                            remaining_pairs))
            # Inserting API DATA to DB
            api_data = ApiData(request_id=self.request_id, date=datetime.now(),
                               estimated_cost=len(remaining_pairs) * 0.004, key=self.api_key,
                               elements=len(remaining_pairs), company_id=self.client_id, user_id=self.user_id,
                               all_elements=len(all_pairs), object_id=self.object_id)
            result = ApiDataManager.insert_or_update_api_data(api_data)
            # print(f"Upserted API-DATA id: {result.upserted_id}")
        else:
            pass
            # print("All remaining elements found in DB.")

        end_time = time.time()
        time_taken = end_time - start_time
        logger.info(f"{self.request_id}, Distance Matrix API Call Time: {time_taken} seconds")
        return travel_data_from_api


    def remaining_api_calls_check(self, remaining_elements):
        if self.debug:
            return ApiDataManager.fetch_curr_day_elements(remaining_elements)
        else:
            return self.api_key

    def get_travel_matrix(self, data: Data) -> list[list[TravelData]]:
        """Gets the time matrix for the given data.
        1. First, checks if the time matrix is already in the database. NOTE: If driving directions changes,
        the db data becomes stale.
        2. If it is not in the database, then it calls the Google Maps API to get the time matrix.
        3. Finally, it returns the travel matrix."""
        """ ELEMENT : One pair from origin to destination"""

        # Initialize the travel matrix with None
        travel_matrix: list[list[TravelData]] = []
        len_nodes_ = len([i for i in data.nodes if i.node_type.value not in ('FIRST_JOB', 'LAST_JOB')])

        for i in range(len(data.nodes)):
            travel_matrix.append([None] * len(data.nodes))

        # Get the latitude and longitude of each node
        """Fetch all the coordinates including technician and work orders(events)"""
        fill_matrix_dest : list[str] = []
        destinations: list[str] = []
        for node in data.nodes:
            if node.node_type.value in ('FIRST_JOB', 'LAST_JOB'):
                fill_matrix_dest.append(f"-50.282528, 92.597161")
            else:
                fill_matrix_dest.append(f"{node.latitude},{node.longitude}")
            if node.node_type.value not in ('FIRST_JOB', 'LAST_JOB'):
                destinations.append(f"{node.latitude},{node.longitude}")
        # log_info(f"destinations: {destinations}")

        # Remove duplicates from the destinations
        unique_destinations: list[str] = list(dict.fromkeys(destinations))

        # Get the travel data from the database
        travel_data_from_db = self.get_travel_data_from_db(unique_destinations)

        location_pairs = []
        for origin in unique_destinations:
            for dest in unique_destinations:
                location_pairs.append((origin, dest))

        # Check if no travel data was found in the database
        if len(travel_data_from_db) == 0:
            # If no travel data was found in the database, then call API and return the travel matrix
            # log_info("No destinations found in database")
            travel_data_from_api = self.batch_processing(self.get_travel_matrix_from_api, unique_destinations,
                                                         travel_data_from_db,
                                                         location_pairs)
            return self.fill_travel_matrix(travel_matrix, fill_matrix_dest, travel_data_from_api), self.failed_coordinates

        # Check if all the destinations were found in the database
        elif len(travel_data_from_db) == len(unique_destinations) * len(unique_destinations):
            print("all the destinations were found in the database")
            api_data = ApiData(request_id=self.request_id, date=datetime.now(), estimated_cost=0, key=self.api_key,
                               elements=0, company_id=self.client_id, user_id=self.user_id,
                               all_elements=len(location_pairs), object_id=self.object_id)
            result = ApiDataManager.insert_or_update_api_data(api_data)
            # print(f"Upserted API-DATA id: {result.upserted_id}")
            # If all the destinations were found in the database, then return the travel matrix
            # print(f"Catching all elements from DB Google API NOT called.")
            # Fill the travel matrix with the travel data from the database
            travel_matrix = self.fill_travel_matrix(travel_matrix, fill_matrix_dest, travel_data_from_db)
            return travel_matrix, self.failed_coordinates

        else:
            travel_data_from_api = self.batch_processing(self.get_travel_matrix_from_api, unique_destinations,
                                                         travel_data_from_db,
                                                         location_pairs)
            return self.fill_travel_matrix(travel_matrix, fill_matrix_dest, travel_data_from_api), self.failed_coordinates

    def get_travel_data_from_db(self, destinations: list[str]) -> list[TravelData]:
        """Creates a time matrix by retrieving as many values as possible from the database."""
        # Iterate through each destination and create a matrix of origin and destination
        location_pairs = []
        for origin in destinations:
            for destination in destinations:
                location_pairs.append((origin, destination))
        # Get the travel data from the database
        travel_data_list = self.travel_data_repository.get_matching_travel_data(location_pairs)
        if self.log_flag:
            logger.info(f'Found {len(travel_data_list)} pairs out of {len(location_pairs)} locations in DB')
        # print(f'Estimated cost will be: $ {round((len(location_pairs) - len(travel_data_list))*0.004, 4)}\n')
        return travel_data_list

    def get_indexes_of_destination(self, destination: str, destinations: list[str]) -> list[int]:
        """Gets the indexes of a destination in a list of destinations. This is
        required for multi-day routes because the same origin can appear multiple
        times due to vehicles being duplicated for each day."""
        indexes_to_query = []
        for i in range(len(destinations)):
            if destinations[i] == destination:
                indexes_to_query.append(i)
        return indexes_to_query

    def fill_travel_matrix(
            self,
            travel_matrix: list[list[TravelData | None]],
            destinations: list[str],
            travel_data_list: list[TravelData],
    ) -> list[list[TravelData]]:
        """Fills the travel matrix with the travel data."""
        for travel_data in travel_data_list:
            # Get the indexes of the origin and destination in the travel matrix
            origin_indexes = self.get_indexes_of_destination(travel_data.origin, destinations)
            destination_indexes = self.get_indexes_of_destination(travel_data.dest, destinations)
            reverse_travel_data = TravelData(
                origin=travel_data.dest,
                dest=travel_data.origin,
                distance=travel_data.distance,
                time=travel_data.time,
            )
            for origin_index in origin_indexes:
                for destination_index in destination_indexes:
                    travel_matrix[origin_index][destination_index] = travel_data
                    travel_matrix[destination_index][origin_index] = reverse_travel_data
        return travel_matrix

    def get_travel_matrix_from_api(self, origins: list[str], destinations: list[str]) -> list[TravelData]:
        return self.call_google_maps_api(origins, destinations)

    # This is used to get the time matrix and the time windows for the nodes.
    # TODO should use only same route from point A-B and B-A
    def split_callback(
            self,
            callback: Callable[[list[str], list[str]], list[TravelData]], location_pairs
    ) -> list[TravelData]:
        """
        When we want to use same route for both side.
        make same_route = True
        """
        same_route = False
        if same_route:
            pass
            # location_pairs = []
            # for origin in unique_destinations:
            #     for dest in unique_destinations:
            #         if (dest, origin) not in location_pairs:
            #             location_pairs.append((origin, dest))

        """
        Calling google api for each element(location pairs) one by one
        """
        counter = 0
        num_addresses = len(location_pairs)
        travel_data_from_api = []
        for i in range(num_addresses):
            origin = [location_pairs[i][0]]
            dest = [location_pairs[i][1]]
            if origin == dest:
                response = TravelData(
                    origin=origin[0],
                    dest=dest[0],
                    distance=0,
                    time=0,
                )
                travel_data_from_api.append(response)
            else:
                # Google api call only for different origin and destination.
                response = callback(origin, dest)
                counter += 1
                travel_data_from_api.extend(response)
        # print(f"\nDistance matrix api called {counter} times\n")

        self.travel_data_repository.batch_insert_travel_data(travel_data_from_api)
        return travel_data_from_api

    def call_google_maps_api(self, origin_addresses: list[str], destination_addresses: list[str]) -> list[TravelData]:
        """Calls the Google Maps API to get the time matrix based on the origin and destination addresses.
        # https://developers.google.com/maps/documentation/distance-matrix/usage-and-billing
        NOTE: There is currently a limit of 100 elements per fetch"""
        # Example result:
        # {
        #     'destination_addresses': ['123 Main St, New York, NY 10001, USA', '456 Broadway, New York, NY 10013, USA'],
        #     'origin_addresses': ['123 Main St, New York, NY 10001, USA', '456 Broadway, New York, NY 10013, USA'],
        #     'rows': [
        #         {
        #             'elements': [
        #                 {'distance': {'text': '0.1 mi', 'value': 161}, 'duration': {'text': '1 min', 'value': 16}, 'status': 'OK'},
        #                 {'distance': {'text': '0.1 mi', 'value': 161}, 'duration': {'text': '1 min', 'value': 16}, 'status': 'OK'}
        #             ]
        #         },
        #         {
        #             'elements': [
        #                 {'distance': {'text': '0.1 mi', 'value': 161}, 'duration': {'text': '1 min', 'value': 16}, 'status': 'OK'},
        #                 {'distance': {'text': '0.1 mi', 'value': 161}, 'duration': {'text': '1 min', 'value': 16}, 'status': 'OK'}
        #             ]
        #         }
        #     ],
        #     'status': 'OK'
        # }
        # Get the travel time and distance between each pair of destinations
        for Attempt in range(3):
            try:
                g_maps = googlemaps.Client(key=self.api_key)
                result = g_maps.distance_matrix(
                    origins=origin_addresses,
                    destinations=destination_addresses,
                    mode="driving",
                )
                status = result.get("status")
                if status == "OK":
                    travel_data_list = []
                    for i, origin in enumerate(origin_addresses):
                        for j, destination in enumerate(destination_addresses):
                            element = result["rows"][i]["elements"][j]
                            if element["status"] == "OK":
                                distance_in_meters = element["distance"]["value"]
                                time_in_minutes = element["duration"]["value"] / 60
                                travel_data_list.append(
                                    TravelData(
                                        origin=origin,
                                        dest=destination,
                                        distance=distance_in_meters,
                                        time=time_in_minutes,
                                    )
                                )
                            else:
                                if self.log_flag:
                                    logger.info(
                                    f"Warning: Skipping origin {origin} to destination {destination} due to element status {element['status']}")
                                self.failed_coordinates.append({
                                    "origin": origin,
                                    "destination": destination,
                                    "status": element["status"]
                                })
                    return travel_data_list
                else:
                    raise Exception(f"Google Maps API Error: {status}")
            except Exception as e:
                logger.info(f"Attempt {Attempt + 1} failed: {e}")
                if Attempt == 3:
                    raise Exception(f"Google Maps API failed: {e}")
                else:
                    time.sleep(2)