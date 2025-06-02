from docplex.cp.model import * 
from config import H


def build_explicit_task_intervals(request_data):
    """Build intervals for explicit request file tasks."""
    request_times = [interval_var(end=[0,H], optional=True) for _, t in request_data['orders'].iterrows()]
    task_times = [interval_var(end=[0,H], optional=True) for _, t in request_data['tasks'].iterrows()]
    requirement_times = [interval_var(end=[0,H], optional=r['optional']) for _, r in request_data['requirements'].iterrows()]
    assignment_times = [interval_var(end=[0,H], optional=True) for _, a in request_data['assignment_options'].iterrows()]
    unavailable_times = [interval_var(start=[u["startTime"],H], end=[0,u["endTime"]], size=u['duration'], optional=True) for u in request_data['unavailabilities']]

    return {
        'request_times': request_times,
        'task_times': task_times,
        'requirement_times': requirement_times,
        'assignment_times': assignment_times,
        'unavailable_times': unavailable_times
    }


def build_static_task_sequence(request_data, assignment_times):
    """Build static task sequence for assignment options."""
    assignment_options = request_data['assignment_options']
    static_task_schedule = [
        sequence_var(
            [assignment_times[i] for i in range(len(assignment_options)) if assignment_options.iloc[i]["resourceId"] == w["resourceId"]],
            [assignment_options.iloc[i]["taskID"] for i in range(len(assignment_options)) if assignment_options.iloc[i]["resourceId"] == w["resourceId"]]
        )
        for _, w in request_data['workers'].iterrows()
    ]
    return static_task_schedule


def build_non_traveller_travel(static_task_schedule, assignment_times, request_data, travel_data):
    """Build non-driver travel time intervals and information."""
    assignment_options = request_data['assignment_options']
    next_static_task_id = [
        type_of_next(
            static_task_schedule[assignment_options.iloc[i]["resourceId"] - 1],
            assignment_times[i],
            0
    )
        for i in range(len(assignment_options))
]

    sorted_static_tasks = request_data['tasks'].sort_values(by="taskID").to_dict(orient="records")
    static_start_locations = [travel_data['locations'].index(sorted_static_tasks[i]['start-location']) for i in range(len(sorted_static_tasks))]
    # assumes final location is remote location
    next_static_task_start_location = [
        ((next_static_task_id[i] == 0) | (presence_of(assignment_times[i]) == 0)) * (len(travel_data['locations'])-1) +
        ((next_static_task_id[i] != 0) & (presence_of(assignment_times[i]) != 0)) *
        element(static_start_locations, abs(next_static_task_id[i] - 1))
        for i in range(len(request_data['assignment_options']))
    ]
    end_location_options = [
        request_data['assignment_options'].iloc[i]['end-location']
        for i in range(len(request_data['assignment_options']))
    ]
    non_driver_travel_times = [
        element(
            travel_data['driving_times_flat'],
            end_location_options[i] * len(travel_data['locations']) + next_static_task_start_location[i])
        * presence_of(assignment_times[i])
        * (next_static_task_id[i] != 0)
        for i in range(len(request_data['assignment_options']))
    ]
    non_driver_travel_list = []

    for i in range(len(request_data['assignment_options'])):
        row = request_data['assignment_options'].iloc[i]
        if row['resourceId'] not in travel_data['traveler_worker_ids']:
            non_driver_travel_list.append({
                'assignment_option': row.to_dict(),  # convert Series to dict if needed
                'index': i,
                'travel_start': row['end-location'],
                'travel_end': next_static_task_start_location[i]
            })
            
    non_driver_travel = [interval_var(end=[0,H], optional=True) for i in range(len(non_driver_travel_list))]

    non_driver_travel_data = {
        'static_task_schedule': static_task_schedule,
        'non_driver_travel_times': non_driver_travel_times,
        'non_driver_travel_list': non_driver_travel_list,
        'non_driver_travel_intervals': non_driver_travel
    }

    return non_driver_travel_data


def build_transportation_assignments(non_driver_travel_list, transport_worker_ids):
    """Build transportation assignments for transporters during non traveler's travel."""
    driver_combinations = []
    for i in range(len(non_driver_travel_list)):
        for j in range(len(transport_worker_ids)):
            driver_combinations.append({
                "driver": transport_worker_ids[j],
                "previous_task": non_driver_travel_list[i]['assignment_option'],
                "travel_start": non_driver_travel_list[i]['travel_start'],
                "travel_end": non_driver_travel_list[i]['travel_end']
            })

    driver_tasks = [interval_var(end=[0,H], optional=True) for d in non_driver_travel_list]
    driver_task_options = [interval_var(end=[0,H], optional=True) for d in driver_combinations]

    transportation_assignment_data = {
        'driver_combinations': driver_combinations,
        'driver_task_intervals': driver_tasks,
        'driver_task_options': driver_task_options
    }
    return transportation_assignment_data


def build_transporter_schedule(assignment_times, request_data, travel_data, transportation_assignment_data):
    """Build transporter schedule for transport workers."""
    assignment_options = request_data['assignment_options']
    all_driver_tasks = (
        [assignment_times[i] for i in range(len(assignment_options))
        if assignment_options.iloc[i]['resourceId'] in travel_data['transport_worker_ids']] +
        [transportation_assignment_data['driver_task_options'][i]
        for i in range(len(transportation_assignment_data['driver_combinations']))]
    )

    driver_task_names = (
        [assignment_options.iloc[i]['taskName'] for i in range(len(assignment_options))
        if assignment_options.iloc[i]['resourceId'] in travel_data['transport_worker_ids']] +
        ["transportation from " + transportation_assignment_data['driver_combinations'][i]['previous_task']['taskName']
        for i in range(len(transportation_assignment_data['driver_combinations']))]
    )

    driver_task_workers = (
        [assignment_options.iloc[i]['resourceId'] for i in range(len(assignment_options))
        if assignment_options.iloc[i]['resourceId'] in travel_data['transport_worker_ids']] +
        [transportation_assignment_data['driver_combinations'][i]['driver']
        for i in range(len(transportation_assignment_data['driver_combinations']))]
    )

    task_id_by_worker = [[] for _ in range(len(request_data['workers']))]
    task_name_by_worker = [[] for _ in range(len(request_data['workers']))]
    for i in range(len(all_driver_tasks)):
        if driver_task_workers[i] in travel_data['transport_worker_ids']:
            task_id_by_worker[driver_task_workers[i]-1].append(i)
            task_name_by_worker[driver_task_workers[i]-1].append(driver_task_names[i])

    driver_schedule = [
        sequence_var(
            [all_driver_tasks[i] for i in range(len(all_driver_tasks)) if driver_task_workers[i] == w['resourceId']],
            task_id_by_worker[w['resourceId'] - 1]
        )
        for _, w in request_data['workers'].iterrows() if w['resourceId'] in travel_data['transport_worker_ids']
    ]

    transporter_data = {
        'all_driver_tasks': all_driver_tasks,
        'driver_task_workers': driver_task_workers,
        'driver_task_names': driver_task_names,
        'driver_sequence': driver_schedule,
        **transportation_assignment_data,
    }

    return transporter_data


def build_transporter_travel(request_data, travel_data, transporter_data):
    assignment_options = request_data['assignment_options']
    transport_worker_ids = travel_data['transport_worker_ids']
    id_to_driverschedule_index = {worker_id: idx for idx, worker_id in enumerate(transport_worker_ids)}
    next_task_id_driver_schedule = [type_of_next(transporter_data['driver_sequence'][id_to_driverschedule_index[transporter_data['driver_task_workers'][i]]],
                                    transporter_data['all_driver_tasks'][i], -1) 
                                    * (size_of(transporter_data['all_driver_tasks'][i]) != 0) for i in range(len(transporter_data['all_driver_tasks']))]
    
    driver_task_start_locations = (
        [assignment_options.iloc[i]['start-location'] for i in range(len(assignment_options)) 
        if assignment_options.iloc[i]['resourceId'] in transport_worker_ids] +
        [transporter_data['driver_combinations'][i]['travel_start'] for i in range(len(transporter_data['driver_combinations']))]
    )
    
    driver_task_end_locations = (
        [assignment_options.iloc[i]['end-location'] for i in range(len(assignment_options))
        if assignment_options.iloc[i]['resourceId'] in transport_worker_ids] +
        [transporter_data['driver_combinations'][i]['travel_end'] for i in range(len(transporter_data['driver_combinations']))]
    )

    next_task_start_location_driver_schedule = [element(driver_task_start_locations, abs(next_task_id_driver_schedule[i]))
                                                for i in range(len(transporter_data['all_driver_tasks']))]

    travel_times_driver_schedule = [
        element(
        travel_data['driving_times_flat'],
        driver_task_end_locations[i] * len(travel_data['locations']) + next_task_start_location_driver_schedule[i])
        * (size_of(transporter_data['all_driver_tasks'][i]) != 0)
        * (next_task_id_driver_schedule[i] != -1)
        for i in range(len(transporter_data['all_driver_tasks']))
    ]

    transporter_travel = [interval_var(end=[0,H], optional=True) for i in range(len(transporter_data['all_driver_tasks']))]
    transporter_travel_data = {
        'transporter_travel_intervals': transporter_travel,
        'transporter_travel_times': travel_times_driver_schedule,
        **transporter_data,

    }

    return transporter_travel_data


def build_completed_sequence(assignment_times, request_data, non_driver_travel_data, transporter_travel_data):
    """Build completed sequence for all tasks and all workers."""
    assignment_options = request_data['assignment_options']
    completed_schedule = [
        sequence_var(
            [assignment_times[i] for i in range(len(assignment_options))
            if assignment_options.iloc[i]["resourceId"] == worker["resourceId"]] +
            [non_driver_travel_data['non_driver_travel_intervals'][i] for i in range(len(non_driver_travel_data['non_driver_travel_list']))
            if non_driver_travel_data['non_driver_travel_list'][i]['assignment_option']["resourceId"] == worker["resourceId"]] +
            [transporter_travel_data['transporter_travel_intervals'][i] for i in range(len(transporter_travel_data['all_driver_tasks']))
            if transporter_travel_data['driver_task_workers'][i] == worker["resourceId"]] +
            [transporter_travel_data['driver_task_options'][i] for i in range(len(transporter_travel_data['driver_combinations']))
            if transporter_travel_data['driver_combinations'][i]["driver"] == worker["resourceId"]]
        )
        for _, worker in request_data['workers'].iterrows()
    ]
    return completed_schedule


def add_kpis(model, non_driver_travel_data):
    """Add KPIs to the model."""
    # Add KPIs to the model
    non_driver_travel_list = non_driver_travel_data['non_driver_travel_list']
    for i in range(len(non_driver_travel_list)):
        model.add_kpi(non_driver_travel_list[i]['travel_end'], non_driver_travel_list[i]['assignment_option']['taskName'] + str(i))
    
    return model


def build_model(request_data, travel_data):
    """Build the model and return the model object."""
    model = CpoModel()
    explicit_task_intervals = build_explicit_task_intervals(request_data)
    static_task_schedule = build_static_task_sequence(request_data, explicit_task_intervals['assignment_times'])
    non_driver_travel_data = build_non_traveller_travel(static_task_schedule, explicit_task_intervals['assignment_times'], request_data, travel_data)
    transportation_assignment_data = build_transportation_assignments(non_driver_travel_data['non_driver_travel_list'], travel_data['transport_worker_ids'])
    transporter_data = build_transporter_schedule(explicit_task_intervals['assignment_times'], request_data, travel_data, transportation_assignment_data)
    transporter_travel_data = build_transporter_travel(request_data, travel_data, transporter_data)
    completed_schedule = build_completed_sequence(explicit_task_intervals['assignment_times'], request_data, non_driver_travel_data, transporter_travel_data)
    model = add_kpis(model, non_driver_travel_data)

    return model, explicit_task_intervals, non_driver_travel_data, transporter_travel_data, completed_schedule