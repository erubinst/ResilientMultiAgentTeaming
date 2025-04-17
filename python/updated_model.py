from docplex.cp.model import * 
import json
import pandas as pd
import numpy as np

with open("/Users/esmerubinstein/Desktop/ICLL/ResilientMultiAgentTeaming/python/y3_scenario.json") as file:
    data = json.load(file)

H = data["H"]
Workers = data["Workers"]
Precedences = data["Precedences"]
Tasks = data["Tasks"]
Requests = data["Requests"]
Recipes = data["Recipes"]
Dependencies = data["Dependencies"]
Skills = data["Skills"]
# maps workers to skills they have
WorkerSkillsRaw = data["WorkerSkillsRaw"]
# maps tasks to needed skills
RequirementsRaw = data["RequirementsRaw"]
DrivingTimes = data["DrivingTimes"]
Unavailabilities = data["Unavailabilities"]

Operations = [
    {"request": r, "task": t}
    for r in data["Requests"]
    for m in data["Recipes"]
    for t in data["Tasks"]
    if r["name"] == m["request"] and t["name"] == m["task"]
]

Requirements = [
    {"operation": o, "skill": s, "beneficiary_id": rr["beneficiary_id"]}
    for o in Operations
    for s in data["Skills"]
    for rr in data["RequirementsRaw"]
    if rr["task_id"] == o["task"]["id"] and rr["skill_id"] == s["id"]
]

WorkerSkills = [
    {"worker": w, "skill": s, "beneficiary_preference": wsr["beneficiary_preference"], "worker_preference": wsr["worker_preference"]}
    for w in data["Workers"]
    for s in data["Skills"]
    for wsr in data["WorkerSkillsRaw"]
    if wsr["worker_id"] == w["id"] and wsr["skill_id"] == s["id"]
]

AssignmentOptions = [
    {"worker_skill": ws, "requirement": r}
    for ws in WorkerSkills
    for r in Requirements
    if ws["skill"]["id"] == r["skill"]["id"]
]

driving_worker_ids = {ws["worker"]["id"] for ws in WorkerSkills if ws["skill"]["name"] == "driver"}
driving_worker_ids = list(driving_worker_ids)

model = CpoModel()

request_times = [interval_var(end=[0,H]) for r in Requests]
# interval variable for every task - not necessarily needed
task_times = [interval_var(end=[0,H]) for t in Tasks]
# interval variable for every skill needed for each task
requirement_times = [interval_var(end=[0,H]) for r in Requirements]
# interval variable for every combination of worker and skill for each task
assignment_times = [interval_var(end=[0,H], optional=True) for a in AssignmentOptions]
# travel = [interval_var(end=[0,H], optional=True) for a in AssignmentOptions]
unavailable_times = [interval_var(start=u["start"], end=u["end"]) for u in Unavailabilities]

task_schedule = [
    sequence_var(
        [assignment_times[i] for i in range(len(AssignmentOptions)) if AssignmentOptions[i]["worker_skill"]["worker"]["id"] == w["id"]],
        [ao["requirement"]["operation"]["task"]["id"] for ao in AssignmentOptions if ao["worker_skill"]["worker"]["id"] == w["id"]]
    ) 
    for w in data["Workers"]
]

nextTaskId = [type_of_next(task_schedule[AssignmentOptions[i]["worker_skill"]["worker"]["id"]-1],
                           assignment_times[i], 0 ) for i in range(len(AssignmentOptions))]

prevTaskId = [type_of_prev(task_schedule[AssignmentOptions[i]["worker_skill"]["worker"]["id"]-1],
                           assignment_times[i], 0 ) for i in range(len(AssignmentOptions))]


# sort tasks by id
sorted_tasks = sorted(Tasks, key=lambda x: x['id'])
start_locations = [sorted_tasks[i]['start_location'] for i in range(len(sorted_tasks))]
end_locations = [sorted_tasks[i]['end_location'] for i in range(len(sorted_tasks))]

nextTaskStartLocation = [element(start_locations, abs(nextTaskId[i]-1)) 
                         * presence_of(assignment_times[i])
                         for i in range(len(AssignmentOptions))]

prevTaskEndLocation = [element(end_locations, abs(prevTaskId[i]-1))
                         * presence_of(assignment_times[i])
                         for i in range(len(AssignmentOptions))]

for i in range(len(AssignmentOptions)):
    if AssignmentOptions[i]['requirement']['operation']['task']['start_location'] == 4:
        AssignmentOptions[i]['requirement']['operation']['task']['end_location'] = prevTaskEndLocation[i]

nextTaskStart = [start_of_next(task_schedule[AssignmentOptions[i]["worker_skill"]["worker"]["id"]-1],  
                            assignment_times[i], 0) for i in range(len(AssignmentOptions))]

# flatten driving times
all_end_locations = [AssignmentOptions[i]['requirement']['operation']['task']['end_location'] for i in range(len(AssignmentOptions))]
DrivingTimes_flat = np.array(DrivingTimes).flatten()
index = all_end_locations + nextTaskStartLocation
travelTimes = [
    element(
        DrivingTimes_flat,
        all_end_locations[i] * data['nLocations'] + nextTaskStartLocation[i])
    * presence_of(assignment_times[i])
    * (nextTaskId[i] != 0)
    for i in range(len(AssignmentOptions))
]

non_driver_travel_list = []
for i in range(len(AssignmentOptions)):
    if AssignmentOptions[i]['worker_skill']['worker']['id'] not in driving_worker_ids:
        # add the assignment option to the driverOptions list and ids in the driver_ids list
        non_driver_travel_list.append(
            { 'assignment_option': AssignmentOptions[i], 
              'index':i,
              'travel_start': AssignmentOptions[i]['requirement']['operation']['task']['end_location'],
              'travel_end': nextTaskStartLocation[i]
            })

non_driver_travel = [interval_var(end=[0,H], optional=True) for i in range(len(non_driver_travel_list))]

driver_combinations = []
for i in range(len(non_driver_travel_list)):
    for j in range(len(driving_worker_ids)):
        driver_combinations.append({
            "driver": driving_worker_ids[j],
            "previous_task": non_driver_travel_list[i]['assignment_option'],
            "travel_start": non_driver_travel_list[i]['travel_start'],
            "travel_end": non_driver_travel_list[i]['travel_end']
        })

driver_tasks = [interval_var(end=[0,H], optional=True) for d in non_driver_travel_list]
driver_task_options = [interval_var(end=[0,H], optional=True) for d in driver_combinations]


for w in range(len(Workers)):
    for u in range(len(Unavailabilities)):
        if Workers[w]['id'] == Unavailabilities[u]['worker_id']:
            not_allowed_options = [ao for ao in range(len(AssignmentOptions)) if AssignmentOptions[ao]['worker_skill']['skill']
                                   ['id'] not in Unavailabilities[u]['permitted_skill_ids'] and AssignmentOptions[ao]['worker_skill']['worker']['id'] == Workers[w]['id']]
            for i in range(len(not_allowed_options)):
                model.add(no_overlap([unavailable_times[u]] + [assignment_times[not_allowed_options[i]]]))


driver_task_start_locations = ([AssignmentOptions[i]['requirement']['operation']['task']['start_location'] for i in range(len(AssignmentOptions)) 
                                if AssignmentOptions[i]['worker_skill']['worker']['id'] in driving_worker_ids] +
               [driver_combinations[i]['travel_start'] for i in range(len(driver_combinations))])

driver_task_end_locations = ([AssignmentOptions[i]['requirement']['operation']['task']['end_location'] for i in range(len(AssignmentOptions))
                              if AssignmentOptions[i]['worker_skill']['worker']['id'] in driving_worker_ids] +
               [driver_combinations[i]['travel_end'] for i in range(len(driver_combinations))])

all_driver_tasks = ([assignment_times[i] for i in range(len(AssignmentOptions))
                 if AssignmentOptions[i]['worker_skill']['worker']['id'] in driving_worker_ids] +
             [driver_task_options[i] for i in range(len(driver_combinations))])

driver_task_names = ([AssignmentOptions[i]['requirement']['operation']['task']['name'] for i in range(len(AssignmentOptions))
                        if AssignmentOptions[i]['worker_skill']['worker']['id'] in driving_worker_ids] +
                ["transportation from" + driver_combinations[i]['previous_task']['requirement']['operation']['task']['name'] for i in range(len(driver_combinations))])


driver_task_workers = ([AssignmentOptions[i]['worker_skill']['worker']['id'] for i in range(len(AssignmentOptions))
                        if AssignmentOptions[i]['worker_skill']['worker']['id'] in driving_worker_ids] +
                [driver_combinations[i]['driver'] for i in range(len(driver_combinations))])

task_or_prev_tasks = ([AssignmentOptions[i]['requirement']['operation']['task']['name'] for i in range(len(AssignmentOptions))
                       if AssignmentOptions[i]['worker_skill']['worker']['id'] in driving_worker_ids] +
                        [driver_combinations[i]['previous_task']['requirement']['operation']['task']['name'] for i in range(len(driver_combinations))])


# initialize task_id_by_worker list to be nested array with size of number of workers
task_id_by_worker = [[] for _ in range(len(Workers))]
task_name_by_worker = [[] for _ in range(len(Workers))]
for i in range(len(all_driver_tasks)):
    if driver_task_workers[i] in driving_worker_ids:
        task_id_by_worker[driver_task_workers[i]-1].append(i)
        task_name_by_worker[driver_task_workers[i]-1].append(driver_task_names[i])


driverSchedule = [
    model.sequence_var(
        [all_driver_tasks[i] for i in range(len(all_driver_tasks)) if driver_task_workers[i] == w["id"]],
        task_id_by_worker[w["id"]-1]
    ) 
    for w in data["Workers"] if w["id"] in driving_worker_ids
]

id_to_driverschedule_index = {worker_id: idx for idx, worker_id in enumerate(driving_worker_ids)}

nextTaskId_driverschedule = [type_of_next(driverSchedule[id_to_driverschedule_index[driver_task_workers[i]]],
                           all_driver_tasks[i], -1 ) 
                           * (size_of(all_driver_tasks[i]) != 0) for i in range(len(all_driver_tasks))]

nextTaskStartLocation_driverschedule = [element(driver_task_start_locations, abs(nextTaskId_driverschedule[i]))
                         for i in range(len(all_driver_tasks))]


index = driver_task_end_locations + nextTaskStartLocation_driverschedule
travelTimes_driverschedule = [
    element(
    DrivingTimes_flat,
    driver_task_end_locations[i] * data['nLocations'] + nextTaskStartLocation_driverschedule[i])
    * (size_of(all_driver_tasks[i]) != 0)
    * (nextTaskId_driverschedule[i] != -1)
    for i in range(len(all_driver_tasks))
]

travel = [interval_var(end=[0,H], optional=True) for i in range(len(all_driver_tasks))]

completedSchedule = [
    model.sequence_var(
        [assignment_times[i] for i in range(len(AssignmentOptions)) if AssignmentOptions[i]["worker_skill"]["worker"]["id"] == w["id"]] +
        [non_driver_travel[i] for i in range(len(non_driver_travel_list)) if non_driver_travel_list[i]['assignment_option']["worker_skill"]["worker"]["id"] == w["id"]] + 
        [travel[i] for i in range(len(all_driver_tasks)) if driver_task_workers[i] == w["id"]] +
        [driver_task_options[i] for i in range(len(driver_combinations)) if driver_combinations[i]["driver"] == w["id"]],
    ) 
    for w in data["Workers"]
]

model.add(
    [size_of(requirement_times[j]) == Requirements[j]['operation']['task']['duration'] 
                                        for i in range(len(Requests))
                                        for j in range(len(Requirements)) if Requests[i]['id'] == Requirements[j]['operation']['request']['id']] +
    [alternative(requirement_times[j], [assignment_times[k] 
                                        for k in range(len(AssignmentOptions))
                                        if AssignmentOptions[k]["requirement"]["operation"]["task"]["id"] == Requirements[j]["operation"]["task"]["id"]
                                        and AssignmentOptions[k]['requirement']['skill']['id'] == Requirements[j]['skill']['id']
                                        and AssignmentOptions[k]['requirement']['beneficiary_id'] == Requirements[j]['beneficiary_id']])
                                        for i in range(len(Requests))
                                        for j in range(len(Requirements)) if Requests[i]['id'] == Requirements[j]['operation']['request']['id'] ] +
    [alternative(driver_tasks[i], [driver_task_options[j] for j in range(len(driver_combinations)) 
                                        if driver_combinations[j]["previous_task"]['requirement']['operation']['task']["id"] == non_driver_travel_list[i]['assignment_option']['requirement']['operation']['task']["id"]])
                                        for i in range(len(non_driver_travel_list))] +
    [no_overlap(task_schedule[w]) for w in range(len(Workers))] +
    [end_of(requirement_times[j]) <= Requirements[j]['operation']['task']['lft'] for j in range(len(Requirements))] +
    [start_of(requirement_times[j]) >= Requirements[j]['operation']['task']['est'] for j in range(len(Requirements))] + 
    [size_of(non_driver_travel[i]) == travelTimes[non_driver_travel_list[i]['index']] for i in range(len(non_driver_travel_list))] +
    [end_before_start(assignment_times[non_driver_travel_list[i]['index']], non_driver_travel[i]) for i in range(len(non_driver_travel_list))] +
    [end_of(non_driver_travel[i]) <= nextTaskStart[non_driver_travel_list[i]['index']] for i in range(len(non_driver_travel_list))] +
    [presence_of(non_driver_travel[i]) == (size_of(non_driver_travel[i]) > 0) for i in range(len(non_driver_travel_list))] +
    [size_of(travel[i]) == travelTimes_driverschedule[i] for i in range(len(all_driver_tasks))] +
    [presence_of(travel[i]) == (size_of(travel[i]) > 0) for i in range(len(all_driver_tasks))] +
    [start_of(driver_tasks[i]) == start_of(non_driver_travel[i]) for i in range(len(non_driver_travel_list))] +
    [end_of(driver_tasks[i]) == end_of(non_driver_travel[i]) for i in range(len(non_driver_travel_list))] +
    [presence_of(driver_tasks[i]) == (size_of(driver_tasks[i]) > 0) for i in range(len(non_driver_travel_list))] +
    [no_overlap(driverSchedule[w]) for w in range(len(driving_worker_ids))] +
    [no_overlap(completedSchedule[w]) for w in range(len(Workers))] +
    [start_at_end(travel[i],all_driver_tasks[i]) for i in range(len(all_driver_tasks))]
)

for i in range(len(all_driver_tasks)):
    model.add_kpi(nextTaskStartLocation_driverschedule[i], "next task location for worker " + str(driver_task_workers[i]) + " after " + driver_task_names[i] + str(i))
    model.add_kpi(nextTaskId_driverschedule[i], "next task id for worker " + str(driver_task_workers[i]) + " after " + driver_task_names[i] + str(i))
    #model.add_kpi(travelTimes_driverschedule[i], "travel time for worker " + str(driver_task_workers[i]) + " after " + driver_task_names[i] + str(i))

for i in range(len(Requests)):
    # Request constraint
    model.add(span(request_times[i], 
                   [requirement_times[j] 
                   for j in range(len(Requirements)) if Requirements[j]["operation"]["request"]["id"] == Requests[i]["id"]]))
    

for i in range(len(Dependencies)):
    task1_interval = [task_times[j] for j in range(len(Tasks)) if Tasks[j]['name'] == Dependencies[i]['task1']]
    task2_interval = [task_times[j] for j in range(len(Tasks)) if Tasks[j]['name'] == Dependencies[i]['task2']]
    model.add(start_at_end(task2_interval[0], task1_interval[0]))

for i in range(len(Requirements)):
    equivalent_task = [task_times[j] for j in range(len(Tasks)) if Tasks[j]['id'] == Requirements[i]['operation']['task']['id']][0]
    model.add(start_of(requirement_times[i]) == start_of(equivalent_task))
    model.add(end_of(requirement_times[i]) == end_of(equivalent_task))
    for j in range(len(Requirements)):
        if Requirements[i]['operation']['task']['id'] == Requirements[j]['operation']['task']['id'] and i != j:
            model.add(start_of(requirement_times[i]) == start_of(requirement_times[j]))
            model.add(end_of(requirement_times[i]) == end_of(requirement_times[j]))


for p in range(len(Precedences)):
    for rq in range(len(Requirements)):
        if Requirements[rq]['operation']['request']['name'] == Precedences[p]['pre']:
            for rq2 in range(len(Requirements)):
                if Requirements[rq2]['operation']['request']['name'] == Precedences[p]['post']:
                    model.add(end_before_start(requirement_times[rq], requirement_times[rq2]))


# propagated = model.propagate(agent='local', execfile = '/Applications/CPLEX_Studio2211/cpoptimizer/bin/arm64_osx/cpoptimizer')
# # find index where requirements[j]['operation']['task']['name'] == 'cleaning'
# for k in range(len(AssignmentOptions)):
#     if AssignmentOptions[k]['requirement']['operation']['task']['name'] == 'cleaning':
#         worker = AssignmentOptions[k]['worker_skill']['worker']['name']
#         print("Cleaning task domain after propagation for worker", worker)
#         print(propagated.get_var_solution(assignment_times[k]))

# objective function
# obj = model.minimize(max([end_of(requirement_times[j]) for j in range(len(Requirements))]))
obj = model.maximize(sum(presence_of(assignment_times[i]) 
                         * (AssignmentOptions[i]['worker_skill']['beneficiary_preference']
                            + AssignmentOptions[i]['worker_skill']['worker_preference']) for i in range(len(AssignmentOptions))))
model.add(obj)
solution = model.solve(TimeLimit=100, agent='local', execfile = '/Applications/CPLEX_Studio2211/cpoptimizer/bin/arm64_osx/cpoptimizer')
if solution:
    print("Solved")
else:
    print("Not solved")


a_times = [solution.get_var_solution(assignment_times[i]) for i in range(len(AssignmentOptions))]
t_times = [solution.get_var_solution(travel[i]) for i in range(len(driver_tasks))]
non_driver_travel_times = [solution.get_var_solution(non_driver_travel[i]) for i in range(len(non_driver_travel_list))]
additional_t_times = [solution.get_var_solution(driver_task_options[i]) for i in range(len(driver_combinations))]
data = []

for i in range(len(AssignmentOptions)):
    if a_times[i].is_present():
        data.append([
            AssignmentOptions[i]['worker_skill']['worker']['name'],
            AssignmentOptions[i]['requirement']['operation']['task']['name'],
            a_times[i].start,
            a_times[i].end,
            AssignmentOptions[i]['requirement']['operation']['request']['name'],
            AssignmentOptions[i]['worker_skill']['skill']['name']
        ])
for i in range(len(non_driver_travel_list)):
    data.append([
        non_driver_travel_list[i]['assignment_option']['worker_skill']['worker']['name'],
        "travelfrom" + non_driver_travel_list[i]['assignment_option']['requirement']['operation']['task']['name'],
        non_driver_travel_times[i].start,
        non_driver_travel_times[i].end,
        "travel",
        "travel"
    ])
for i in range(len(driver_combinations)):
    data.append([
        Workers[driver_combinations[i]['driver']-1]['name'],
        "transportationfrom" + driver_combinations[i]['previous_task']['requirement']['operation']['task']['name'],
        additional_t_times[i].start,
        additional_t_times[i].end,
        "TRANSPORT",
        "travel"
    ])

for i in range(len(driver_tasks)):
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
df.to_csv("output.csv", index=False)