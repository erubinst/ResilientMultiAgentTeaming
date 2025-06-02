from docplex.cp.model import * 
import pandas as pd
from config import *

def retrieve_interval_solution(solution, explicit_task_intervals, request_data, non_driver_travel_data, transporter_travel_data):
    """
    Retrieve the solution for the intervals in the model.
    """
    # Get the solution for the intervals
    explicit_tasks = [solution.get_var_solution(explicit_task_intervals['assignment_times'][i]) for i in range(len(request_data['assignment_options']))]
    transporter_travel = [solution.get_var_solution(transporter_travel_data['transporter_travel_intervals'][i]) for i in range(len(transporter_travel_data['all_driver_tasks']))]
    non_driver_travel = [solution.get_var_solution(non_driver_travel_data['non_driver_travel_intervals'][i]) for i in range(len(non_driver_travel_data['non_driver_travel_list']))]
    transport_tasks = [solution.get_var_solution(transporter_travel_data['driver_task_options'][i]) for i in range(len(transporter_travel_data['driver_task_options']))]

    return explicit_tasks, transporter_travel, non_driver_travel, transport_tasks


def format_explicit_tasks(output_data, request_data, explicit_tasks):
    """
    Format the explicit tasks for output.
    """
    assignment_options = request_data['assignment_options']
    for i in range(len(assignment_options)):
        if explicit_tasks[i].is_present():
            output_data.append([
                assignment_options.iloc[i]['resourceName'],
                assignment_options.iloc[i]['taskName'],
                explicit_tasks[i].start,
                explicit_tasks[i].end,
                assignment_options.iloc[i]['requestName'],
                assignment_options.iloc[i]['capability'],
                assignment_options.iloc[i]['explicit_transport_task']
            ])
    return output_data


def format_non_driver_travel(output_data, non_driver_travel_data, non_driver_travel):
    non_driver_travel_list = non_driver_travel_data['non_driver_travel_list']   
    for i in range(len(non_driver_travel_list)):
        output_data.append([
            non_driver_travel_list[i]['assignment_option']['resourceName'],
            "travel from" + non_driver_travel_list[i]['assignment_option']['taskName'],
            non_driver_travel[i].start,
            non_driver_travel[i].end,
            "travel",
            "travel",
            False
        ])
    return output_data


def format_transport_tasks(output_data, request_data, transporter_travel_data, transport_tasks):
    """
    Format the transport tasks for output.
    """
    driver_combinations = transporter_travel_data['driver_combinations']
    for i in range(len(driver_combinations)):
        output_data.append([
            request_data['workers'].iloc[driver_combinations[i]['driver']-1]['name'],
            "transportation from" + driver_combinations[i]['previous_task']['taskName'],
            transport_tasks[i].start,
            transport_tasks[i].end,
            "TRANSPORT",
            "travel",
            False
        ])
    return output_data


def format_transporter_travel(output_data, request_data, transporter_travel_data, transporter_travel):
    """
    Format the transporter travel for output.
    """
    for i in range(len(transporter_travel_data['all_driver_tasks'])):
        if transporter_travel[i].is_present():
            output_data.append([
                request_data['workers'].iloc[transporter_travel_data['driver_task_workers'][i]-1]['name'],
                "travel from " + transporter_travel_data['driver_task_names'][i],
                transporter_travel[i].start,
                transporter_travel[i].end,
                "travel",
                "travel",
                False
            ])
    return output_data


def pull_solution_data(solution,request_data, explicit_task_intervals, non_driver_travel_data, transporter_travel_data):
    """
    Format the output data for the solution.
    """
    # Initialize the output data
    output_data = []
    
    explicit_tasks, transporter_travel, non_driver_travel, transport_tasks = retrieve_interval_solution(
        solution,
        explicit_task_intervals,
        request_data,
        non_driver_travel_data,
        transporter_travel_data
    )

    # Format the explicit tasks
    output_data = format_explicit_tasks(output_data, request_data, explicit_tasks)
    # Format the non-driver travel 
    output_data = format_non_driver_travel(output_data, non_driver_travel_data, non_driver_travel)
    # Format the transport tasks
    output_data = format_transport_tasks(output_data, request_data, transporter_travel_data, transport_tasks)
    # Format the transporter travel
    output_data = format_transporter_travel(output_data, request_data, transporter_travel_data, transporter_travel)

    # Create a DataFrame from the output data
    df = pd.DataFrame(output_data, columns=["Worker", "Task", "Start", "End", "Request", "Skill", "ExplicitTransport"])
    return df, explicit_tasks


def load_json_file(filename, data_path):
    """Load a JSON file from the configured data path."""
    with open(data_path + filename) as f:
        return json.load(f)
    

def save_json_file(filename, data_path, data):
    """Save a JSON file to the configured data path."""
    with open(data_path + filename, 'w') as f:
        json.dump(data, f, indent=4)


def update_request_file(solution, locations, explicit_tasks, non_driver_travel_data):
    transport = []
    dynamic_locations = solution.get_kpis()
    non_driver_travel_list = non_driver_travel_data['non_driver_travel_list']
    for i in range(len(non_driver_travel_list)):
        if explicit_tasks[non_driver_travel_list[i]['index']].is_present():
            transport.append([
                non_driver_travel_list[i]['assignment_option']['requestName'],
                non_driver_travel_list[i]['assignment_option']['taskName'],
                non_driver_travel_list[i]['assignment_option']['resourceName'],
                non_driver_travel_list[i]['travel_start'],
                dynamic_locations[non_driver_travel_list[i]['assignment_option']['taskName']+ str(i)],
            ])
    transport_df = pd.DataFrame(transport, columns=["name", "previous_subtask", "resource", "start-location", "end-location"])
    original_request_dict = load_json_file(REQUEST_FILE, DATA_PATH)
    # loop through transport df
    for row in transport_df.iterrows():
        for request in original_request_dict['templates']:
            # check if any of the subtasks have explicit_transport_task to true
            has_transport = any(d.get('explicit_transport_task') is True for d in request['subtasks'])
            if request['name'] == row[1]['name'] and not has_transport:
                resource_capability = row[1]["resource"].lower()+"_presence"
                subtasks = []
                subtasks.append({
                    "taskName": "pickup_" + row[1]['previous_subtask'],
                    "requiredCapabilities": [],
                    "requiredCapabilityIds": [],
                    "start-location": locations[row[1]['start-location']],
                    "end-location": locations[row[1]['start-location']],
                    "duration": 0
                })
                subtasks.append({
                    "taskName": "dropoff_" + row[1]['previous_subtask'],
                    "requiredCapabilities": [],
                    "requiredCapabilityIds": [],
                    "start-location": locations[row[1]['end-location']],
                    "end-location": locations[row[1]['end-location']],
                    "duration": 0,
                })
                outernest_subtask = {
                    "taskName": "pickup_and_dropoff_" + row[1]['previous_subtask'],
                    "type": "serial",
                    "requiredCapabilities": ["transport", resource_capability],
                    "subtasks": subtasks
                }
                request['subtasks'].append(outernest_subtask)

    # Save the updated request file
    save_json_file(UPDATED_REQUEST_FILE, UPDATED_DATA_PATH, original_request_dict)
    return transport_df


def postprocess_data(solution, request_data, travel_data, explicit_task_intervals, non_driver_travel_data, transporter_travel_data):
    """
    Postprocess the solution data and save it to a CSV file.
    """
    # Pull the solution data
    df, explicit_tasks = pull_solution_data(solution, request_data, explicit_task_intervals, non_driver_travel_data, transporter_travel_data)
    
    # Save the DataFrame to a CSV file
    output_path = OUTPUT_PATH + "output.csv"
    df.to_csv(output_path, index=False)
    
    # Update the request file
    # update_request_file(solution, travel_data['locations'], explicit_tasks, non_driver_travel_data)