from docplex.cp.model import *
from config import CPLEX_PATH, SCENARIO, DATA_PATH


def solve_model(model, explicit_task_intervals, transporter_travel_data, request_data):
    """
    Solve the model and return the solution.
    """
    preferences_json_path = DATA_PATH + SCENARIO + "/request_json/preferences.json"
    with open(preferences_json_path, 'r') as f:
        data = json.load(f)
    preferences = data['preferences']

    max_travel_time = len(transporter_travel_data['transporter_travel_intervals'])
    travel_times_sum = sum(presence_of(transporter_travel_data['transporter_travel_intervals'][i]) 
                             for i in range(len(transporter_travel_data['transporter_travel_intervals'])))
    normalized_travel_times = travel_times_sum / max_travel_time 
    max_preferences = len(preferences)
    preferences_sum = sum(presence_of(explicit_task_intervals['assignment_times'][j]) *
                          request_data['assignment_options'].iloc[j]['score'] 
                          for j in range(len(request_data['assignment_options'])))
    normalized_preferences = preferences_sum / max_preferences

    # Solve the model
    # obj = model.minimize(max([end_of(explicit_task_intervals['requirement_times'][j]) for j in range(len(request_data['requirements']))]))
    # obj = model.minimize(travel_times_sum)
    # obj = model.maximize(preferences_sum)
    obj = model.minimize(0.9*normalized_travel_times + 0.1*normalized_preferences)
    model.add(obj)
    solution = model.solve(TimeLimit=100, agent='local', execfile=CPLEX_PATH)

    # Check if a solution was found
    if solution:
        print("Solution found!")
    else:
        print("No solution found.")

    return solution
