from docplex.cp.model import *
from config import CPLEX_PATH

def solve_model(model, explicit_task_intervals, request_data):
    """
    Solve the model and return the solution.
    """
    # Solve the model
    # obj = model.minimize(max([end_of(explicit_task_intervals['requirement_times'][j]) for j in range(len(request_data['requirements']))]))
    obj = model.maximize(sum(presence_of(explicit_task_intervals['assignment_times'][j])*request_data['assignment_options'].iloc[j]['is_preferred'] for j in range(len(request_data['assignment_options']))))
    model.add(obj)
    solution = model.solve(TimeLimit=100, agent='local', execfile=CPLEX_PATH)
    
    # Check if a solution was found
    if solution:
        print("Solution found!")
    else:
        print("No solution found.")
    
    return solution