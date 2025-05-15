import json
import pandas as pd
import numpy as np
from config import DATA_PATH, REQUEST_FILE, TRAVEL_MATRIX_FILE


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
    tasks = retrieve_subtasks(data)
    unavailabilities = retrieve_unavailability_periods(data)
    requirements_df = retrieve_requirements(data)
    worker_skills_df = retrieve_worker_skills(data)
    assignment_options = retrieve_assignment_options(requirements_df, worker_skills_df)
    travel_matrix, traveler_worker_ids, transport_worker_ids = retrieve_travel_information(
        worker_skills_df, travel_matrix
    )
    requirements = requirements_df.to_dict(orient="records")
    return tasks, unavailabilities, requirements, assignment_options, travel_matrix, traveler_worker_ids, transport_worker_ids


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


def retrieve_subtasks(data):
    tasks = []
    for template in data["templates"]:
        tasks.extend(template.get("subtasks", []))
    return tasks


def retrieve_requirements(data):
    """Retrieve requirements from the request data."""
    requirements = []
    for template in data["templates"]:
        for subtask in template.get("subtasks", []):
            capabilities = subtask.get("requiredCapabilities", [])
            capability_ids = subtask.get("requiredCapabilityIds", [])
            
            for cap, cap_id in zip(capabilities, capability_ids):
                requirements.append({
                    "requestId": template["id"],
                    "requestName": template["name"],
                    "taskId": subtask["id"],
                    "taskName": subtask["taskName"],
                    "capability": cap,
                    "capabilityId": cap_id,
                    "end-location": data['locations'].index(subtask["end-location"]),
                    "start-location": data['locations'].index(subtask["start-location"]),
                    "duration": subtask["duration"],
                    "explicit_transport_task": subtask.get("explicit_transport_task", False)
                })

    requirements = pd.DataFrame(requirements)
    orders = pd.DataFrame(data["orders"], columns=['name', 'earlieststartdate', 'duedate'])
    requirements = pd.merge(
        requirements,
        orders,
        left_on=["requestName"],
        right_on=["name"],
        how="inner"
    )
    return requirements


def retrieve_worker_skills(data):
    """Retrieve worker skills from the request data."""
    worker_skills = []
    for resource in data['resourceTypes']:
        for cap, cap_id in zip(resource["capabilities"], resource["capability_ids"]):
            worker_skills.append({
                "resourceName": resource["name"],
                "resourceId": resource["id"],
                "capability": cap,
                "capabilityId": cap_id,
            })
    worker_skills = pd.DataFrame(worker_skills)
    return worker_skills


def retrieve_assignment_options(requirements_df, worker_skills_df):
    """Retrieve assignment options based on requirements and worker skills."""
    assignment_options = requirements_df.merge(
        worker_skills_df,
        left_on=["capabilityId", "capability"],
        right_on=["capabilityId", "capability"],
        how="inner" 
    )
    assignment_options = assignment_options.to_dict(orient="records")
    return assignment_options


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
    tasks, unavailabilities, requirements, assignment_options, travel_matrix, traveler_worker_ids, transport_worker_ids = retrieve_derived_data(data, travel_matrix)

    request_data = {
        "tasks": tasks,
        "workers": data["resourceTypes"],
        "templates": data["templates"],
        "order-constraints": data["order-constraints"],
        "requirements": requirements,
        "unavailabilities": unavailabilities,
        "assignment_options": assignment_options
    }

    travel_data = {
        "travel_matrix": travel_matrix,
        "driving_times_flat": np.array(travel_matrix).flatten(),
        "locations": data["locations"],
        "traveler_worker_ids": traveler_worker_ids,
        "transport_worker_ids": transport_worker_ids
    }
    
    return request_data, travel_data
