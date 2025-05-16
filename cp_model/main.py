from config import *
from preprocessor import preprocess_data
from model import build_model
from constraints import add_model_constraints
from solver import solve_model
from postprocessor import postprocess_data

def main():
    # Load the request data and travel matrix
    request_data, travel_data = preprocess_data(REQUEST_FILE, TRAVEL_MATRIX_FILE, DATA_PATH)

    # Build the model
    model, explicit_task_intervals, non_driver_travel_data, transporter_travel_data, completed_schedule = build_model(request_data, travel_data)
    # Add constraints to the model
    model = add_model_constraints(model, request_data, travel_data, completed_schedule, explicit_task_intervals, transporter_travel_data, non_driver_travel_data)
    # Solve the model
    solution = solve_model(model, explicit_task_intervals, request_data)
    postprocess_data(solution, request_data, travel_data, explicit_task_intervals, non_driver_travel_data, transporter_travel_data)


main()