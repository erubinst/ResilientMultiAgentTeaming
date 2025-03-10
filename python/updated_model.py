from docplex.cp.model import * 
import json
import pandas as pd

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
travel = [interval_var(end=[0,H], optional=True) for a in AssignmentOptions]
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


# sort tasks by id
sorted_tasks = sorted(Tasks, key=lambda x: x['id'])
start_locations = [sorted_tasks[i]['start_location'] for i in range(len(sorted_tasks))]

nextTaskStartLocation = [element(abs(nextTaskId[i]-1), start_locations) 
                         * presence_of(assignment_times[i])
                         for i in range(len(AssignmentOptions))]


travelTimes = [
    element(
        DrivingTimes[AssignmentOptions[i]['requirement']['operation']['task']['end_location']],
        nextTaskStartLocation[i]
    ) * presence_of(assignment_times[i])
    * (nextTaskId[i] != 0)
    for i in range(len(AssignmentOptions))
]

# tasks_needing_driver = []
# for i in range(len(AssignmentOptions)):
#     if AssignmentOptions[i]['worker_skill']['worker']['id'] not in driving_worker_ids:
#         # add the assignment option to the driverOptions list and ids in the driver_ids list
#         tasks_needing_driver.append([AssignmentOptions[i], i])


# driver_combinations = []
# for i in range(len(tasks_needing_driver)):
#     for j in range(len(driving_worker_ids)):
#         driver_combinations.append({
#             "driver": driving_worker_ids[j],
#             "previous_task": tasks_needing_driver[i][0]
#         })

# driver_tasks = [interval_var(end=[0,H]) for d in tasks_needing_driver]
# driver_task_options = [interval_var(end=[0,H], optional=True) for d in driver_combinations]


for w in range(len(Workers)):
    for u in range(len(Unavailabilities)):
        if Workers[w]['id'] == Unavailabilities[u]['worker_id']:
            not_allowed_options = [ao for ao in range(len(AssignmentOptions)) if AssignmentOptions[ao]['worker_skill']['skill']
                                   ['id'] not in Unavailabilities[u]['permitted_skill_ids'] and AssignmentOptions[ao]['worker_skill']['worker']['id'] == Workers[w]['id']]
            print(Workers[w]['name'],not_allowed_options)
            for i in range(len(not_allowed_options)):
                model.add(no_overlap([unavailable_times[u]] + [assignment_times[not_allowed_options[i]]]))
            # model.add(no_overlap([unavailable_times[u]], [assignment_times[i] for i in not_allowed_options]))

fullSchedule = [
    model.sequence_var(
        [assignment_times[i] for i in range(len(AssignmentOptions)) if AssignmentOptions[i]["worker_skill"]["worker"]["id"] == w["id"]] +
        [travel[i] for i in range(len(AssignmentOptions)) if AssignmentOptions[i]["worker_skill"]["worker"]["id"] == w["id"]]
        # [driver_task_options[i] for i in range(len(driver_combinations)) if driver_combinations[i]["driver"] == w["id"]],
    ) 
    for w in data["Workers"]
]

model.add(
    [size_of(requirement_times[j]) >= Requirements[j]['operation']['task']['duration'] 
                                        for i in range(len(Requests))
                                        for j in range(len(Requirements)) if Requests[i]['id'] == Requirements[j]['operation']['request']['id']] +
    [alternative(requirement_times[j], [assignment_times[k] 
                                        for k in range(len(AssignmentOptions))
                                        if AssignmentOptions[k]["requirement"]["operation"]["task"]["id"] == Requirements[j]["operation"]["task"]["id"]
                                        and AssignmentOptions[k]['requirement']['skill']['id'] == Requirements[j]['skill']['id']
                                        and AssignmentOptions[k]['requirement']['beneficiary_id'] == Requirements[j]['beneficiary_id']])
                                        for i in range(len(Requests))
                                        for j in range(len(Requirements)) if Requests[i]['id'] == Requirements[j]['operation']['request']['id'] ] +
    # [alternative(driver_tasks[i], [driver_task_options[j] for j in range(len(driver_combinations)) 
    #                                     if driver_combinations[j]["previous_task"]['requirement']['operation']['task']["id"] == tasks_needing_driver[i][0]['requirement']['operation']['task']["id"]])
    #                                     for i in range(len(tasks_needing_driver))] +
    [no_overlap(task_schedule[w]) for w in range(len(Workers))] +
    [end_of(requirement_times[j]) <= Requirements[j]['operation']['task']['lft'] for j in range(len(Requirements))] +
    [start_of(requirement_times[j]) >= Requirements[j]['operation']['task']['est'] for j in range(len(Requirements))] + 
    [size_of(travel[i]) == travelTimes[i] for i in range(len(AssignmentOptions))] +
    # [size_of(driver_tasks[i]) == travelTimes[tasks_needing_driver[i][1]] for i in range(len(tasks_needing_driver))] +
    [no_overlap(fullSchedule[w]) for w in range(len(Workers))] +
    [start_at_end(travel[i], assignment_times[i]) for i in range(len(AssignmentOptions))]
)

# for i in range(len(travelTimes)):
#     model.add_kpi(nextTaskId[i], AssignmentOptions[i]['requirement']['operation']['task']['name'] + " with " + AssignmentOptions[i]['worker_skill']['worker']['name'] + " next task id")
#     model.add_kpi(nextTaskStartLocation[i], AssignmentOptions[i]['requirement']['operation']['task']['name'] + " with " + AssignmentOptions[i]['worker_skill']['worker']['name'] + " next task start location")
#     model.add_kpi(travelTimes[i], AssignmentOptions[i]['requirement']['operation']['task']['name'] + " with " + AssignmentOptions[i]['worker_skill']['worker']['name'])

for i in range(len(Requests)):
    rq_list = []
    for rq in range(len(Requirements)):
        if Requirements[rq]['operation']['request']['id'] == Requests[i]['id']:
            rq_list.append([rq, Requirements[rq]])
    relevant_deps = [tc for tc in Dependencies if tc['request'] == Requests[i]['name']]
    for tc in relevant_deps:
        matching_rq_pairs = [
            (rq_list[j][0], rq_list[j2][0])
            for j in range(len(rq_list)) if rq_list[j][1]['operation']['task']['name'] == tc['task1']
            for j2 in range(len(rq_list)) if rq_list[j2][1]['operation']['task']['name'] == tc['task2']
        ]
        
        model.add([
            end_before_start(requirement_times[j], requirement_times[j2]) 
            for j, j2 in matching_rq_pairs
        ])
        
        model.add([
            start_at_end(requirement_times[j2], requirement_times[j]) 
            for j, j2 in matching_rq_pairs
        ])

    # Request constraint
    model.add(span(request_times[i], 
                   [requirement_times[j] 
                   for j in range(len(Requirements)) if Requirements[j]["operation"]["request"]["id"] == Requests[i]["id"]]))


for i in range(len(Requirements)):
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
t_times = [solution.get_var_solution(travel[i]) for i in range(len(AssignmentOptions))]
# additional_t_times = [solution.get_var_solution(driver_task_options[i]) for i in range(len(driver_combinations))]
data = []
# print(solution.get_kpis())
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
    data.append([
        AssignmentOptions[i]['worker_skill']['worker']['name'],
        "travelfrom" + AssignmentOptions[i]['requirement']['operation']['task']['name'],
        t_times[i].start,
        t_times[i].end,
        "travelrequest",
        "travel"
    ])
# for i in range(len(driver_combinations)):
#     data.append([
#         Workers[driver_combinations[i]['driver']]['name'],
#         "transportationfrom" + AssignmentOptions[i]['requirement']['operation']['task']['name'],
#         additional_t_times[i].start,
#         additional_t_times[i].end,
#         "TRANSPORT",
#         "travel"
#     ])

df = pd.DataFrame(data, columns=["Worker", "Task", "Start", "End", "Request", "Skill"])
df.to_csv("output.csv", index=False)