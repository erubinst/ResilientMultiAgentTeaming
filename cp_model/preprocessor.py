import json
import pandas as pd
import numpy as np
from config import EPOCH_DATE


def load_json_file(filename, data_path):
    """Load a JSON file from the configured data path."""
    with open(data_path + filename) as f:
        return json.load(f)
    

def parse_location(request_dict):
    """Parse the location of the template tasks from the orders."""
    orders_by_name = {order["name"]: order for order in request_dict["orders"]}
    for template in request_dict["templates"]:
        order = orders_by_name.get(template["name"])
        if order:
            start_loc = order["start-location"]
            end_loc = order["end-location"]
            for subtask in template["subtasks"]:
                if subtask["start-location"] == "@start-location":
                    subtask["start-location"] = start_loc
                if subtask["end-location"] == "@end-location":
                    subtask["end-location"] = end_loc
    
    return request_dict
    

def load_all_data(request_file, travel_matrix_file, data_path):
    """Load request data and travel matrix."""
    request_dict = load_json_file(request_file, data_path)
    data = parse_location(request_dict)
    travel_matrix = load_json_file(travel_matrix_file, data_path)
    return data, travel_matrix


def retrieve_derived_data(data, travel_matrix):
    """Retrieve derived data from the request data."""
    orders_df = retrieve_orders(data)
    tasks_df = retrieve_subtasks(orders_df)
    unavailabilities = retrieve_unavailability_periods(data)
    worker_skills_df, capabilities_df, resourceTypes_df = retrieve_worker_skills(data)
    requirements_df = retrieve_requirements(tasks_df, capabilities_df, data['locations'])
    assignment_options_df = retrieve_assignment_options(requirements_df, worker_skills_df)
    travel_matrix, traveler_worker_ids, transport_worker_ids = retrieve_travel_information(
        worker_skills_df, travel_matrix
    )
    return {
        "tasks": tasks_df,
        "unavailabilities": unavailabilities,
        "requirements": requirements_df,
        "assignment_options": assignment_options_df,
        "travel_matrix": travel_matrix,
        "traveler_worker_ids": traveler_worker_ids,
        "transport_worker_ids": transport_worker_ids,
        "orders": orders_df,
        "workers": resourceTypes_df
    }


def retrieve_orders(data):
    orders_df = pd.DataFrame(data['orders'])
    orders_df['tasks'] = orders_df['tasks'].apply(lambda x: str(x[0]))
    templates_df = pd.DataFrame(data['templates'])
    templates_df.rename(columns={"name": "tasks"}, inplace = True)
    orders_df = orders_df.merge(templates_df, how='inner', on= 'tasks')
    orders_df['orderID'] = range(1, len(orders_df) + 1)
    orders_df['earlieststartdate'] = pd.to_datetime(orders_df['earlieststartdate'])
    orders_df['duedate'] = pd.to_datetime(orders_df['duedate'])
    epoch = pd.to_datetime(EPOCH_DATE)
    orders_df['earlieststartdate'] = (orders_df['earlieststartdate'] - epoch).dt.total_seconds() // 60
    orders_df['duedate'] = (orders_df['duedate'] - epoch).dt.total_seconds() // 60

    return orders_df


def retrieve_unavailability_periods(data):
    """Retrieve unavailability periods from the request data."""
    unavailabilities = []
    for resource in data['resources']:
        for downtime in resource["downtimes"]:
            unavailabilities.append({
                "resourceName": resource["name"],
                "baseLocation": resource["location"],
                **downtime
            })

    return unavailabilities


def retrieve_subtasks(orders_df):
    orders_exploded = orders_df.explode('subtasks')
    subtasks_df = pd.json_normalize(orders_exploded['subtasks'])
    subtasks_df['start-location-order'] = orders_exploded['start-location'].values
    subtasks_df['end-location-order'] = orders_exploded['end-location'].values
    subtasks_df['optional'] = orders_exploded['optional'].values
    subtasks_df['start-location'] = subtasks_df.apply(
        lambda row: row['start-location-order'] if row['start-location'] == '@start-location' else row['start-location'],
        axis=1
    )
    subtasks_df['end-location'] = subtasks_df.apply(
        lambda row: row['end-location-order'] if row['end-location'] == '@end-location' else row['end-location'],
        axis=1
    )
    subtasks_df.drop(columns=['start-location-order', 'end-location-order'], inplace=True)
    subtasks_df['taskID'] = range(1, len(subtasks_df) + 1)
    orders_cols = ['orderID', 'name', 'earlieststartdate', 'duedate']
    for col in orders_cols:
        subtasks_df[col] = orders_exploded[col].values
    
    subtasks_df.rename(columns={'name': 'requestName'}, inplace=True)

    return subtasks_df


def retrieve_requirements(subtasks_df, capabilities_df, locations):
    """Retrieve requirements from the request data."""
    requirements_df = subtasks_df.explode('requiredCapabilities')
    requirements_df.rename(columns={"requiredCapabilities": "capability"}, inplace = True)
    requirements_df = requirements_df.merge(capabilities_df, how='inner', on= 'capability')
    requirements_df['end-location'] = requirements_df['end-location'].apply(lambda x: locations.index(x))
    requirements_df['start-location'] = requirements_df['start-location'].apply(lambda x: locations.index(x))

    return requirements_df


def retrieve_worker_skills(data):
    """Retrieve worker skills from the request data."""
    resourceTypes_df = pd.DataFrame(data['resourceTypes'])
    resourceTypes_df['resourceId'] = range(1, len(resourceTypes_df) + 1)
    exploded = resourceTypes_df.explode('capabilities')
    unique_capabilities = exploded['capabilities'].dropna().unique()
    capabilities_df = pd.DataFrame({
        'capability': sorted(unique_capabilities),
        'capability_id': range(1, len(unique_capabilities) + 1)
    })

    worker_skills_df = exploded.rename(columns={'capabilities': 'capability', 'name': 'resourceName'})
    worker_skills_df = worker_skills_df.merge(capabilities_df, on='capability', how='inner')
    return worker_skills_df, capabilities_df, resourceTypes_df


def retrieve_assignment_options(requirements_df, worker_skills_df):
    """Retrieve assignment options based on requirements and worker skills."""
    assignment_options_df = requirements_df.merge(
        worker_skills_df,
        on=["capability_id", "capability"],
        how="inner" 
    )
    assignment_options_df['is_preferred'] = False
    # Filter out capabilities that contain "presence" (case-insensitive)
    filtered_df = assignment_options_df[~assignment_options_df['capability'].str.contains('presence', case=False)]

    # Group by taskName and capability, and get unique resourceNames
    grouped = (
        filtered_df.groupby(['taskName', 'capability'])['resourceName']
        .apply(lambda x: sorted(set(x)))  # convert to set for uniqueness, then sort for consistency
    )

    for (task, capability), resources in grouped.items():
        print(f"\nTask: {task}")
        print(f"  Capability: {capability}")
        print(f"    Available resources: {resources}")
        
        if len(resources) == 1:
            preferred = resources[0]
            print(f"    Only one resource available: '{preferred}' — automatically selected.")
        else:
            preferred = input("    Enter preferred resource from above: ").strip()
            while preferred not in resources:
                print("    Invalid choice. Please select from the list above.")
                preferred = input("    Enter preferred resource from above: ").strip()

        # Mark preferred in the original DataFrame
        condition = (
            (assignment_options_df['taskName'] == task) &
            (assignment_options_df['capability'] == capability) &
            (assignment_options_df['resourceName'] == preferred)
        )
        assignment_options_df.loc[condition, 'is_preferred'] = True


    return assignment_options_df


def retrieve_travel_information(worker_skills_df, travel_matrix):
    """Retrieve travel information from the travel matrix and worker skills."""
    travel_matrix = pd.DataFrame(travel_matrix).values
    traveler_worker_ids = list(set(
        worker_skills_df[worker_skills_df["capability"] == "traveler"]["resourceId"]
    ))

    transport_worker_ids = list(set(
        worker_skills_df[worker_skills_df["capability"] == "transport"]["resourceId"]
    ))
    return travel_matrix, traveler_worker_ids, transport_worker_ids


def preprocess_data(request_file, travel_matrix_file, data_path):
    """Preprocess the data and return the required variables."""
    data, travel_matrix = load_all_data(request_file, travel_matrix_file, data_path)
    derived_data = retrieve_derived_data(data, travel_matrix)

    request_data = {
        "tasks": derived_data["tasks"],
        "workers": derived_data["workers"],
        "orders": derived_data["orders"],
        "order-constraints": data["order-constraints"],
        "requirements": derived_data["requirements"],
        "unavailabilities": derived_data["unavailabilities"],
        "assignment_options": derived_data["assignment_options"]
    }

    travel_data = {
        "travel_matrix": derived_data['travel_matrix'],
        "driving_times_flat": np.array(derived_data['travel_matrix']).flatten(),
        "locations": data["locations"],
        "traveler_worker_ids": derived_data["traveler_worker_ids"],
        "transport_worker_ids": derived_data["transport_worker_ids"]
    }
    
    return request_data, travel_data
