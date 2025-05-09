from docplex.cp.model import * 

mdl0 = CpoModel()

task1 = mdl0.interval_var(start=[0,10], end=[5,20])
task2 = mdl0.interval_var(start=[0,10], end=[5,20])
task3 = mdl0.interval_var(start = 0, end = 5, size=5)

mdl0.add(mdl0.no_overlap([task1, task2]))
mdl0.add(mdl0.no_overlap([task1, task3]))

start_min = task2.start[0]
end_max = task2.end[1]
print("Task2 start_min: {}".format(start_min))
print("Task2 end_max: {}".format(end_max))
#obj = mdl0.maximize(get_domain_max(task2.end) - get_domain_min(task2.start))
#mdl0.add(obj)
#msol0 = mdl0.solve(TimeLimit=10, agent='local', execfile = '/Applications/CPLEX_Studio2211/cpoptimizer/bin/arm64_osx/cpoptimizer')

# if msol0:
#     var_sol = msol0.get_var_solution(task1)
#     print("Task1 : {}..{}".format(var_sol.get_start(), var_sol.get_end()))
#     var_sol = msol0.get_var_solution(task2)
#     print("Task2 : {}..{}".format(var_sol.get_start(), var_sol.get_end()))

propagated = mdl0.propagate(agent='local', execfile = '/Applications/CPLEX_Studio2211/cpoptimizer/bin/arm64_osx/cpoptimizer')
print(propagated.get_var_solution(task1))
print(propagated.get_var_solution(task2))
print(propagated.get_var_solution(task3))