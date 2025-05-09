from docplex.cp.model import * 
import json
import pandas as pd
import numpy as np

with open("/Users/esmerubinstein/Desktop/ICLL/ResilientMultiAgentTeaming/schedule_manager/y3_scenario_stn.json") as file:
    data = json.load(file)

with open("/Users/esmerubinstein/Desktop/ICLL/ResilientMultiAgentTeaming/schedule_manager/y3_scenario_travel_matrix_stn.json") as file:
    travel_matrix = json.load(file)

H = 100

orders_by_name = {order["name"]: order for order in data["orders"]}

# Update placeholders in-place
for template in data["templates"]:
    order = orders_by_name.get(template["name"])
    if order:
        start_loc = order["start-location"]
        end_loc = order["end-location"]
        for subtask in template["subtasks"]:
            if subtask["start-location"] == "@start-location":
                subtask["start-location"] = start_loc
            if subtask["end-location"] == "@end-location":
                subtask["end-location"] = end_loc

# workers contains name, id, capabilities, and capability ids
Workers = data['resourceTypes']

# precedences contains relation, source, destination
OrderConstraints = data['order-constraints']

# tasks contains taskName, id, requiredCapabilities, requiredCapabilityIds, duration, start-location, end-location
Tasks = []
for template in data["templates"]:
    Tasks.extend(template.get("subtasks", []))

Templates = data["templates"]
Locations = data["locations"]

Orders = data["orders"]
Orders = pd.DataFrame(Orders, columns=['name', 'earlieststartdate', 'duedate'])

ResourceInformation = data['resources']
Unavailabilities = []
for resource in ResourceInformation:
    for downtime in resource["downtimes"]:
        Unavailabilities.append({
            "resourceName": resource["name"],
            "baseLocation": resource["location"],
            **downtime
        })

Requirements = []
for template in data["templates"]:
    for subtask in template.get("subtasks", []):
        capabilities = subtask.get("requiredCapabilities", [])
        capability_ids = subtask.get("requiredCapabilityIds", [])
        
        for cap, cap_id in zip(capabilities, capability_ids):
            Requirements.append({
                "requestId": template["id"],
                "requestName": template["name"],
                "taskId": subtask["id"],
                "taskName": subtask["taskName"],
                "capability": cap,
                "capabilityId": cap_id,
                "end-location": Locations.index(subtask["end-location"]),
                "start-location": Locations.index(subtask["start-location"]),
                "duration": subtask["duration"]
            })
Requirements = pd.DataFrame(Requirements)
Requirements = pd.merge(
    Requirements,
    Orders,
    left_on=["requestName"],
    right_on=["name"],
    how="inner"
)

WorkerSkills = []
for resource in Workers:
    for cap, cap_id in zip(resource["capabilities"], resource["capability_ids"]):
        WorkerSkills.append({
            "resourceName": resource["name"],
            "resourceId": resource["id"],
            "capability": cap,
            "capabilityId": cap_id,
        })
WorkerSkills = pd.DataFrame(WorkerSkills)

AssignmentOptions = Requirements.merge(
    WorkerSkills,
    left_on=["capabilityId", "capability"],
    right_on=["capabilityId", "capability"],
    how="inner" 
)
AssignmentOptions = AssignmentOptions.to_dict(orient="records")
Requirements = Requirements.to_dict(orient="records")

travel_df = pd.DataFrame(travel_matrix)
travel_matrix = travel_df.values

traveler_worker_ids = list(set(
    WorkerSkills[WorkerSkills["capability"] == "traveler"]["resourceId"]
))

transport_worker_ids = list(set(
    WorkerSkills[WorkerSkills["capability"] == "transport"]["resourceId"]
))

model = CpoModel()

request_times = [interval_var(end=[0,H], optional=True) for t in Templates]
task_times = [interval_var(end=[0,H], optional=True) for t in Tasks]
requirement_times = [interval_var(end=[0,H], optional=True) for r in Requirements]
assignment_times = [interval_var(end=[0,H], optional=True) for a in AssignmentOptions]
unavailable_times = [interval_var(start=[u["startTime"],H], end=[0,u["endTime"]], size=u['duration']) for u in Unavailabilities]

static_task_schedule = [
    sequence_var(
        [assignment_times[i] for i in range(len(AssignmentOptions)) if AssignmentOptions[i]["resourceId"] == w["id"]],
        [ao["taskId"] for ao in AssignmentOptions if ao["resourceId"] == w["id"]]
    )
    for w in Workers
]

next_static_task_id = [type_of_next(static_task_schedule[AssignmentOptions[i]["resourceId"]-1],
                           assignment_times[i], 0 ) for i in range(len(AssignmentOptions))]

prev_static_task_id = [type_of_prev(static_task_schedule[AssignmentOptions[i]["resourceId"]-1],
                           assignment_times[i], 0 ) for i in range(len(AssignmentOptions))]

sorted_static_tasks = sorted(Tasks, key=lambda x: x["id"])

static_start_locations = [Locations.index(sorted_static_tasks[i]['start-location']) for i in range(len(sorted_static_tasks))]
static_end_locations = [Locations.index(sorted_static_tasks[i]['end-location']) for i in range(len(sorted_static_tasks))]

# assumes final location is remote location
next_static_task_start_location = [
    ((next_static_task_id[i] == 0) | (presence_of(assignment_times[i]) == 0)) * (len(Locations)-1) +
    ((next_static_task_id[i] != 0) & (presence_of(assignment_times[i]) != 0)) *
    element(static_start_locations, abs(next_static_task_id[i] - 1))
    for i in range(len(AssignmentOptions))
]

end_location_options = [AssignmentOptions[i]['end-location'] for i in range(len(AssignmentOptions))]
driving_times_flat = np.array(travel_matrix).flatten()
index = end_location_options + next_static_task_start_location
travelTimes = [
    element(
        driving_times_flat,
        end_location_options[i] * len(data['locations']) + next_static_task_start_location[i])
    * presence_of(assignment_times[i])
    * (next_static_task_id[i] != 0)
    for i in range(len(AssignmentOptions))
]

non_driver_travel_list = []
for i in range(len(AssignmentOptions)):
    if AssignmentOptions[i]['resourceId'] not in traveler_worker_ids:
        non_driver_travel_list.append(
            { 'assignment_option': AssignmentOptions[i], 
              'index':i,
              'travel_start': AssignmentOptions[i]['end-location'],
              'travel_end': next_static_task_start_location[i]
            })
        
non_driver_travel = [interval_var(end=[0,H], optional=True) for i in range(len(non_driver_travel_list))]
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

driver_task_start_locations = ([AssignmentOptions[i]['start-location'] for i in range(len(AssignmentOptions)) 
                                if AssignmentOptions[i]['resourceId'] in transport_worker_ids] +
                                [driver_combinations[i]['travel_start'] for i in range(len(driver_combinations))])

driver_task_end_locations = ([AssignmentOptions[i]['end-location'] for i in range(len(AssignmentOptions))
                              if AssignmentOptions[i]['resourceId'] in transport_worker_ids] +
                              [driver_combinations[i]['travel_end'] for i in range(len(driver_combinations))])

all_driver_tasks = ([assignment_times[i] for i in range(len(AssignmentOptions))
                    if AssignmentOptions[i]['resourceId'] in transport_worker_ids] +
                    [driver_task_options[i] for i in range(len(driver_combinations))])

driver_task_names = ([AssignmentOptions[i]['taskName'] for i in range(len(AssignmentOptions))
                     if AssignmentOptions[i]['resourceId'] in transport_worker_ids] +
                     ["transportation from" + driver_combinations[i]['previous_task']['taskName'] for i in range(len(driver_combinations))])

driver_task_workers = ([AssignmentOptions[i]['resourceId'] for i in range(len(AssignmentOptions))
                       if AssignmentOptions[i]['resourceId'] in transport_worker_ids] +
                       [driver_combinations[i]['driver'] for i in range(len(driver_combinations))])

driver_task_ids = ([AssignmentOptions[i]['taskId'] for i in range(len(AssignmentOptions))
                     if AssignmentOptions[i]['resourceId'] in transport_worker_ids] +
                     [driver_combinations[i]['previous_task']['taskId'] for i in range(len(driver_combinations))])

task_id_by_worker = [[] for _ in range(len(Workers))]
task_name_by_worker = [[] for _ in range(len(Workers))]
for i in range(len(all_driver_tasks)):
    if driver_task_workers[i] in transport_worker_ids:
        task_id_by_worker[driver_task_workers[i]-1].append(i)
        task_name_by_worker[driver_task_workers[i]-1].append(driver_task_names[i])

driver_schedule = [
    model.sequence_var(
        [all_driver_tasks[i] for i in range(len(all_driver_tasks)) if driver_task_workers[i] == w["id"]],
        task_id_by_worker[w["id"]-1]
    ) 
    for w in Workers if w["id"] in transport_worker_ids
]

id_to_driverschedule_index = {worker_id: idx for idx, worker_id in enumerate(transport_worker_ids)}
next_task_id_driver_schedule = [type_of_next(driver_schedule[id_to_driverschedule_index[driver_task_workers[i]]],
                                all_driver_tasks[i], -1) 
                                * (size_of(all_driver_tasks[i]) != 0) for i in range(len(all_driver_tasks))]

next_task_start_location_driver_schedule = [element(driver_task_start_locations, abs(next_task_id_driver_schedule[i]))
                                            for i in range(len(all_driver_tasks))]

index = driver_task_end_locations + next_task_start_location_driver_schedule
travel_times_driver_schedule = [
    element(
    driving_times_flat,
    driver_task_end_locations[i] * len(data['locations']) + next_task_start_location_driver_schedule[i])
    * (size_of(all_driver_tasks[i]) != 0)
    * (next_task_id_driver_schedule[i] != -1)
    for i in range(len(all_driver_tasks))
]

travel = [interval_var(end=[0,H], optional=True) for i in range(len(all_driver_tasks))]

completed_schedule = [
    model.sequence_var(
        [assignment_times[i] for i in range(len(AssignmentOptions)) if AssignmentOptions[i]["resourceId"] == w["id"]] +
        [non_driver_travel[i] for i in range(len(non_driver_travel_list)) if non_driver_travel_list[i]['assignment_option']["resourceId"] == w["id"]] + 
        [travel[i] for i in range(len(all_driver_tasks)) if driver_task_workers[i] == w["id"]] +
        [driver_task_options[i] for i in range(len(driver_combinations)) if driver_combinations[i]["driver"] == w["id"]],
    ) 
    for w in Workers
]

model.add(
    [size_of(requirement_times[j]) == Requirements[j]['duration'] 
                                        for i in range(len(Templates))
                                        for j in range(len(Requirements)) if Templates[i]['id'] == Requirements[j]['requestId']] +
    [alternative(requirement_times[j], [assignment_times[k] 
                                        for k in range(len(AssignmentOptions))
                                        if AssignmentOptions[k]["taskId"] == Requirements[j]["taskId"]
                                        and AssignmentOptions[k]['capabilityId'] == Requirements[j]['capabilityId']])
                                        # and AssignmentOptions[k]['requirement']['beneficiary_id'] == Requirements[j]['beneficiary_id']])
                                        for i in range(len(Templates))
                                        for j in range(len(Requirements)) if Templates[i]['id'] == Requirements[j]['requestId'] ] +
    [alternative(driver_tasks[i], [driver_task_options[j] for j in range(len(driver_combinations)) 
                                        if driver_combinations[j]["previous_task"]['taskId'] == non_driver_travel_list[i]['assignment_option']['taskId']])
                                        for i in range(len(non_driver_travel_list))] +
    [end_of(requirement_times[j]) <= Requirements[j]['duedate'] for j in range(len(Requirements))] +
    [start_of(requirement_times[j]) >= Requirements[j]['earlieststartdate'] for j in range(len(Requirements))] + 
    [size_of(non_driver_travel[i]) == travelTimes[non_driver_travel_list[i]['index']] for i in range(len(non_driver_travel_list))] +
    [end_before_start(assignment_times[non_driver_travel_list[i]['index']], non_driver_travel[i]) for i in range(len(non_driver_travel_list))] +
    # [end_of(non_driver_travel[i]) <= nextTaskStart[non_driver_travel_list[i]['index']] for i in range(len(non_driver_travel_list))] +
    [presence_of(non_driver_travel[i]) == (size_of(non_driver_travel[i]) > 0) for i in range(len(non_driver_travel_list))] +
    [size_of(travel[i]) == travel_times_driver_schedule[i] for i in range(len(all_driver_tasks))] +
    [presence_of(travel[i]) == (size_of(travel[i]) > 0) for i in range(len(all_driver_tasks))] +
    [start_of(driver_tasks[i]) == start_of(non_driver_travel[i]) for i in range(len(non_driver_travel_list))] +
    [end_of(driver_tasks[i]) == end_of(non_driver_travel[i]) for i in range(len(non_driver_travel_list))] +
    [presence_of(driver_tasks[i]) == (size_of(driver_tasks[i]) > 0) for i in range(len(non_driver_travel_list))] +
    [no_overlap(driver_schedule[w]) for w in range(len(transport_worker_ids))] +
    [no_overlap(completed_schedule[w]) for w in range(len(Workers))] +
    [no_overlap(static_task_schedule[w]) for w in range(len(Workers))] +
    [start_at_end(travel[i],all_driver_tasks[i]) for i in range(len(all_driver_tasks))]
)

#for i in range(len(all_driver_tasks)):
    #model.add_kpi(next_task_start_location_driver_schedule[i], "next task location for worker " + str(driver_task_workers[i]) + " after " + driver_task_names[i] + str(i))
    #model.add_kpi(next_task_id_driver_schedule[i], "next task id for worker " + str(driver_task_workers[i]) + " after " + driver_task_names[i] + str(i))
    #model.add_kpi(travel_times_driver_schedule[i], "travel time for worker " + str(driver_task_workers[i]) + " after " + driver_task_names[i] + str(i))

for i in range(len(non_driver_travel_list)):
    model.add_kpi(next_static_task_start_location[i], non_driver_travel_list[i]['assignment_option']['taskName'] + str(i))

for i in range(len(Templates)):
    # Request constraint
    model.add(span(request_times[i], 
                   [requirement_times[j] 
                   for j in range(len(Requirements)) if Requirements[j]["requestId"] == Templates[i]["id"]]))
    subtasks = Templates[i]['subtasks']
    if len(subtasks) > 1:
        for k in range(len(subtasks) - 1):
            current_task_id = subtasks[k]['id']
            next_task_id = subtasks[k + 1]['id']

    
for i in range(len(Requirements)):
    equivalent_task = [j for j in range(len(Tasks)) if Tasks[j]['id'] == Requirements[i]['taskId']][0]
    model.add(start_of(requirement_times[i]) == start_of(task_times[equivalent_task]))
    model.add(end_of(requirement_times[i]) == end_of(task_times[equivalent_task]))


for i in range(len(Templates)):
    subtasks = Templates[i]['subtasks']
    if len(subtasks) > 1:
        for k in range(len(subtasks) - 1):
            current_task_id = subtasks[k]['id']
            next_task_id = subtasks[k + 1]['id']
            current_task = [i for i in range(len(Tasks)) if Tasks[i]['id'] == current_task_id][0]
            next_task = [i for i in range(len(Tasks)) if Tasks[i]['id'] == next_task_id][0]
            model.add(start_at_end(task_times[next_task], task_times[current_task]))


for oc in OrderConstraints:
    source_request = [i for i in range(len(Templates)) if Templates[i]['name'] == oc['source']][0]
    destination_request = [i for i in range(len(Templates)) if Templates[i]['name'] == oc['destination']][0]
    model.add(end_before_start(request_times[source_request], request_times[destination_request]))
            

for w in range(len(Workers)):
    for u in range(len(Unavailabilities)):
        if Workers[w]['name'] == Unavailabilities[u]['resourceName']:
            not_allowed_options = [ao for ao in range(len(AssignmentOptions)) if AssignmentOptions[ao]['capabilityId']
                                   not in Unavailabilities[u]['permitted_skill_ids'] and AssignmentOptions[ao]['resourceId'] == Workers[w]['id']]
            for i in range(len(not_allowed_options)):
                model.add(no_overlap([unavailable_times[u]] + [assignment_times[not_allowed_options[i]]]))


obj = model.minimize(max([end_of(requirement_times[j]) for j in range(len(Requirements))]))
model.add(obj)
solution = model.solve(TimeLimit=100, agent='local', execfile = '/Applications/CPLEX_Studio2211/cpoptimizer/bin/arm64_osx/cpoptimizer')
if solution:
    print("Solved")
else:
    print("Not solved")

a_times = [solution.get_var_solution(assignment_times[i]) for i in range(len(AssignmentOptions))]
t_times = [solution.get_var_solution(travel[i]) for i in range(len(all_driver_tasks))]
non_driver_travel_times = [solution.get_var_solution(non_driver_travel[i]) for i in range(len(non_driver_travel_list))]
additional_t_times = [solution.get_var_solution(driver_task_options[i]) for i in range(len(driver_combinations))]
data = []
transport = []

dynamic_locations = solution.get_kpis()

for i in range(len(AssignmentOptions)):
    if a_times[i].is_present():
        data.append([
            AssignmentOptions[i]['resourceName'],
            AssignmentOptions[i]['taskName'],
            a_times[i].start,
            a_times[i].end,
            AssignmentOptions[i]['requestName'],
            AssignmentOptions[i]['capability']
        ])
for i in range(len(non_driver_travel_list)):
    data.append([
        non_driver_travel_list[i]['assignment_option']['resourceName'],
        "travel from" + non_driver_travel_list[i]['assignment_option']['taskName'],
        non_driver_travel_times[i].start,
        non_driver_travel_times[i].end,
        "travel",
        "travel"
    ])
    if non_driver_travel_times[i].is_present():
        transport.append([
            non_driver_travel_list[i]['assignment_option']['requestName'],
            non_driver_travel_list[i]['assignment_option']['taskName'],
            non_driver_travel_list[i]['assignment_option']['resourceName'],
            non_driver_travel_list[i]['travel_start'],
            dynamic_locations[non_driver_travel_list[i]['assignment_option']['taskName']+ str(i)],
        ])
for i in range(len(driver_combinations)):
    data.append([
        Workers[driver_combinations[i]['driver']-1]['name'],
        "transportation from" + driver_combinations[i]['previous_task']['taskName'],
        additional_t_times[i].start,
        additional_t_times[i].end,
        "TRANSPORT",
        "travel"
    ])

for i in range(len(all_driver_tasks)):
    if t_times[i].is_present():
        data.append([
            Workers[driver_task_workers[i]-1]['name'],
            "travel from " + driver_task_names[i],
            t_times[i].start,
            t_times[i].end,
            "travel",
            "travel"
        ])

df = pd.DataFrame(data, columns=["Worker", "Task", "Start", "End", "Request", "Skill"])
transport_df = pd.DataFrame(transport, columns=["name", "previous_subtask", "resource", "start-location", "end-location"])
df.to_csv("output.csv", index=False)
transport_df.to_json("transport.json", orient="records", lines=True)

with open("/Users/esmerubinstein/Desktop/ICLL/ResilientMultiAgentTeaming/schedule_manager/y3_scenario_stn.json") as file:
    request_file = json.load(file)

# loop through transport df
for row in transport_df.iterrows():
    for request in request_file['templates']:
        if request['name'] == row[1]['name']:
            resource_capability = row[1]["resource"].lower()+"_presence"
            request['subtasks'].append({
                "taskName": "pickup_" + row[1]['previous_subtask'],
                "start-location": row[1]['start-location'],
                "end-location": row[1]['start-location'],
                "duration": 0,
                "requiredCapabilities": ["transport", resource_capability],
                "requiredCapabilityIds": []
            })
            request['subtasks'].append({
                "taskName": "dropoff_" + row[1]['previous_subtask'],
                "start-location": row[1]['end-location'],
                "end-location": row[1]['end-location'],
                "duration": 0,
                "requiredCapabilities": ["transport", resource_capability],
                "requiredCapabilityIds": []
            })

# output a new json file with the updated request_file
with open("updated_request_file.json", "w") as outfile:
    json.dump(request_file, outfile, indent=4)

