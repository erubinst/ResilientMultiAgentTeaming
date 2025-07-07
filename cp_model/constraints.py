from docplex.cp.model import * 
import pandas as pd

def add_explicit_task_constraints(model, explicit_task_intervals, request_data):
    """
    Add constraints on explicit tasks to the model.
    """
    requirement_times = explicit_task_intervals['requirement_times']
    orders = request_data['orders']
    requirements = request_data['requirements']
    assignment_options = request_data['assignment_options']

    model.add(
        [
            size_of(requirement_times[j]) == requirements.iloc[j]['duration'] * presence_of(requirement_times[j])
            for _, order in orders.iterrows()
            for j in range(len(requirements))
            if order['orderID'] == requirements.iloc[j]['orderID']
        ] +
        [
            alternative(
                requirement_times[j],
                [
                    explicit_task_intervals['assignment_times'][k]
                    for k in range(len(assignment_options))
                    if assignment_options.iloc[k]['taskID'] == requirements.iloc[j]['taskID']
                    and assignment_options.iloc[k]['capability_id'] == requirements.iloc[j]['capability_id']
                ]
            )
            for _, order in orders.iterrows()
            for j in range(len(requirements))
            if order['orderID'] == requirements.iloc[j]['orderID']
        ] +
        [model.if_then(presence_of(requirement_times[j]), end_of(requirement_times[j]) <= request_data['requirements'].iloc[j]['duedate']) for j in range(len(request_data['requirements']))] +
        [model.if_then(presence_of(requirement_times[j]), start_of(requirement_times[j]) >= request_data['requirements'].iloc[j]['earlieststartdate']) for j in range(len(request_data['requirements']))]
    )

    

    for i in range(len(request_data['requirements'])):
        equivalent_task = request_data['tasks'].index[
            (request_data['tasks']['taskID'] == requirements.iloc[i]['taskID']) &
            (request_data['tasks']['orderID'] == requirements.iloc[i]['orderID'])
        ][0]
        model.add(start_of(requirement_times[i]) == start_of(explicit_task_intervals['task_times'][equivalent_task]))
        model.add(end_of(requirement_times[i]) == end_of(explicit_task_intervals['task_times'][equivalent_task]))


    for i in range(len(request_data['orders'])):
        model.add(span(
            explicit_task_intervals['request_times'][i],
            [requirement_times[j] 
            for j in range(len(requirements)) 
            if requirements.iloc[j]["orderID"] == orders.iloc[i]["orderID"]]
        ))
        
        tasks = request_data['tasks']
        subtasks = request_data['orders'].iloc[i]['subtasks']
        order_id = request_data['orders'].iloc[i]['orderID']
        subtasks_df = pd.DataFrame(subtasks, columns = ['taskName'])
        subtasks_df['orderID'] = order_id 
        merged_df = subtasks_df.merge(tasks[['taskName', 'orderID', 'taskID']], 
                                    on=['taskName', 'orderID'], how='inner')
        if len(merged_df) > 1:
            for k in range(len(merged_df) - 1):
                current_task_id = merged_df.iloc[k]['taskID']
                next_task_id = merged_df.iloc[k + 1]['taskID']
                current_task = tasks[tasks['taskID'] == current_task_id].index[0]
                next_task = tasks[tasks['taskID'] == next_task_id].index[0]
                model.add(start_at_end(explicit_task_intervals['task_times'][next_task], explicit_task_intervals['task_times'][current_task]))

    return model


def add_unavailability_constraints(model, request_data, explicit_task_intervals):
    """Add constraints on unavailability to the model."""
    assignment_options = request_data['assignment_options']
    workers = request_data['workers']
    for w in range(len(workers)):
        for u in range(len(request_data['unavailabilities'])):
            if workers.iloc[w]['name'] == request_data['unavailabilities'][u]['resourceName']:
                not_allowed_options = [
                    ao for ao in range(len(assignment_options))
                    if assignment_options.iloc[ao]['capability_id'] not in request_data['unavailabilities'][u]['permitted_skill_ids']
                    and assignment_options.iloc[ao]['resourceId'] == workers.iloc[w]['resourceId']
                ]
                for i in range(len(not_allowed_options)):
                    model.add(no_overlap([explicit_task_intervals['unavailable_times'][u]] + [explicit_task_intervals['assignment_times'][not_allowed_options[i]]]))
    
    return model


def add_transportation_task_constraints(model, transporter_travel_data, non_driver_travel_data):
    """
    Add constraints on transportation tasks to the model.
    """
    model.add(
        [alternative(transporter_travel_data['driver_task_intervals'][i], [transporter_travel_data['driver_task_options'][j] for j in range(len(transporter_travel_data['driver_combinations'])) 
                                            if transporter_travel_data['driver_combinations'][j]["previous_task"]['taskID'] == non_driver_travel_data['non_driver_travel_list'][i]['assignment_option']['taskID']])
                                            for i in range(len(non_driver_travel_data['non_driver_travel_list']))] +
        [start_of(transporter_travel_data['driver_task_intervals'][i]) == start_of(non_driver_travel_data['non_driver_travel_intervals'][i]) for i in range(len(non_driver_travel_data['non_driver_travel_list']))] +
        [end_of(transporter_travel_data['driver_task_intervals'][i]) == end_of(non_driver_travel_data['non_driver_travel_intervals'][i]) for i in range(len(non_driver_travel_data['non_driver_travel_list']))] +
        [presence_of(transporter_travel_data['driver_task_intervals'][i]) == (size_of(transporter_travel_data['driver_task_intervals'][i]) > 0) for i in range(len(non_driver_travel_data['non_driver_travel_list']))]
    )

    return model


def add_travel_task_constraints(model, explicit_task_intervals, transporter_travel_data, non_driver_travel_data):
    """
    Add constraints on travel tasks to the model.
    """
    non_driver_travel_list = non_driver_travel_data['non_driver_travel_list']
    model.add(
        [size_of(non_driver_travel_data['non_driver_travel_intervals'][i]) == non_driver_travel_data['non_driver_travel_times'][non_driver_travel_list[i]['index']] for i in range(len(non_driver_travel_list))] +
        [end_before_start(explicit_task_intervals['assignment_times'][non_driver_travel_list[i]['index']], non_driver_travel_data['non_driver_travel_intervals'][i]) for i in range(len(non_driver_travel_list))] +
        # [end_of(non_driver_travel[i]) <= nextTaskStart[non_driver_travel_list[i]['index']] for i in range(len(non_driver_travel_list))] +
        [presence_of(non_driver_travel_data['non_driver_travel_intervals'][i]) == (size_of(non_driver_travel_data['non_driver_travel_intervals'][i]) > 0) for i in range(len(non_driver_travel_list))] +
        [size_of(transporter_travel_data['transporter_travel_intervals'][i]) == transporter_travel_data['transporter_travel_times'][i] for i in range(len(transporter_travel_data['all_driver_tasks']))] +
        [presence_of(transporter_travel_data['transporter_travel_intervals'][i]) == (size_of(transporter_travel_data['transporter_travel_intervals'][i]) > 0) for i in range(len(transporter_travel_data['all_driver_tasks']))] +
        [start_at_end(transporter_travel_data['transporter_travel_intervals'][i],transporter_travel_data['all_driver_tasks'][i]) for i in range(len(transporter_travel_data['all_driver_tasks']))]
    )
    return model


def add_sequence_constraints(model, non_driver_travel_data, transporter_travel_data, completed_schedule, travel_data, request_data):
    """
    Add sequence constraints to the model.
    """
    model.add(
        [no_overlap(transporter_travel_data['driver_sequence'][w]) for w in range(len(travel_data['transport_worker_ids']))] +
        [no_overlap(completed_schedule[w]) for w in range(len(request_data['workers']))] +
        [no_overlap(non_driver_travel_data['static_task_schedule'][w]) for w in range(len(request_data['workers']))]
    )
    return model


def add_order_constraints(model, request_data, explicit_task_intervals):
    """
    Add order constraints to the model.
    """
    orders = request_data['orders']
    request_times = explicit_task_intervals['request_times']
    for oc in request_data['order-constraints']:
        source_requests = orders[orders['name'] == oc['source']].index.tolist()
        destination_requests = orders[orders['name'] == oc['destination']].index.tolist()
        for source_request in source_requests:
            for destination_request in destination_requests:
                if source_request != destination_request:
                    model.add(end_before_start(request_times[source_request], request_times[destination_request]))
    return model


def add_model_constraints(model, request_data, travel_data, completed_schedule, explicit_task_intervals, transporter_travel_data, non_driver_travel_data):
    """
    Add all constraints to the model.
    """
    model = add_explicit_task_constraints(model, explicit_task_intervals, request_data)
    model = add_unavailability_constraints(model, request_data, explicit_task_intervals)
    model = add_transportation_task_constraints(model, transporter_travel_data, non_driver_travel_data)
    model = add_travel_task_constraints(model, explicit_task_intervals, transporter_travel_data, non_driver_travel_data)
    model = add_order_constraints(model, request_data, explicit_task_intervals)
    model = add_sequence_constraints(model, non_driver_travel_data, transporter_travel_data, completed_schedule, travel_data, request_data)
    
    return model