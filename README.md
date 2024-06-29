# ResilientMultiAgentTeaming

OPL Model for AI Caring project.  
Run the files using IBM ILOG CPLEX Optimization Studio

# Decision Variable Breakdown

- **tasks[t in Tasks]** (interval) is an array of interval variables of size Durations[t] for each task that lie between 0 and the horizon H. Each interval variable has a start, end, and duration (these are fixed to Durations).  These are also constrained to fall within the EarliestStart[t] and LatestEnd[t]

- **wtasks[s in Skills]** (interval) is an array of interval variables of size Durations[t] for each task-worker combination.  This is an optional variable, meaning only the task-worker assignments that actually happen will have an interval variable present.  Each interval will contain a presence indication (1 or 0) to indicate this.  Each present wtasks variable is constrained to match the associated task interval.  That is, if worker w is assigned to task t, wtasks[w-t] will equal tasks[t].

- **busyTime[w in Workers][s in Skills]** (interval) is a double array of intervals that splits the wtasks[s] set on the worker level.  They are also optional and will not exist for any worker-skill combination that does not exist, or a worker-skill combination that does not match w for the outer array.

- **busyTimes[w in Workers]** (sequence) is a sequence array containing a sequence for every worker.  The sequence is made up of the busyTime[w][s] intervals for worker w.  The intervals in the sequence are also assigned a type from TaskTypes[t] to indicate if they are a break or regular task.

# Decision Expression Breakdown

- **nextIntervalStart[w in Workers][s in Skills]** (integer) is an integer that gives the start time of the interval after busyTime[w][s] in the sequence busyTimes[w][s].  If no interval next, it will default to horizon H.

- **prevIntervalEnd[w in Workers][s in Skills]** (integer) is an integer that gives the end time of the interval before busyTime[w][s] in the sequence busyTimes[w][s].  If no interval previous, it will default to 0. 

- **endOfTask[s in Skills]** (integer) is an integer value that gives the end time of the interval busyTime[s.worker][s].

- **breakStarts[w in Workers][s in Skills]** (integer) finds all the start times for break intervals for worker w.  For each worker, there are s slots, but all slots where s.task is not a break or does not belong to w will be 0.

- **trueBreakDifference[s in Skills][sk in Skills]** (integer) is an double array that holds the difference between the breakStarts[sk.worker][sk] (all the starts of breaks for worker) and endOf(wtasks[s]).  It is 0 if s.task is a break, s.worker != sk.worker, or if the difference is less than 0.

- **breakDifference[s in Skills][sk in Skills]** (integer) is a double array that takes trueBreakDifference and sets all 0 values (except for when the break difference actually is zero) to the horizon value.  

- **nextBreakStarts[s in Skills]** (integer) gives the start of the next break for wtasks[s] by grabbing the minimum value from the breakDifference array.  It will be 0 for any break tasks.

- **trueLatestEndsInFront[s in Skills][sk in Skills]** (integer) grabs all the LatestEnd constraints for each





