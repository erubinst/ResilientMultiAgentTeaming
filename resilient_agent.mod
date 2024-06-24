// --------------------------------------------------------------------------
// Licensed Materials - Property of IBM
//
// 5725-A06 5725-A29 5724-Y48 5724-Y49 5724-Y54 5724-Y55
// Copyright IBM Corporation 1998, 2022. All Rights Reserved.
//
// Note to U.S. Government Users Restricted Rights:
// Use, duplication or disclosure restricted by GSA ADP Schedule
// Contract with IBM Corp.
// --------------------------------------------------------------------------

/* ------------------------------------------------------------

Problem Description
-------------------


------------------------------------------------------------ */

using CP;

int H = ...;

// Reads in workers from data file
{string} Workers = ...;

// Reads in tasks from data file
{string} Tasks = ...;

// Task data
int Durations[Tasks] = ...;
int EarliestStart[Tasks] = ...; // Earliest start time for each task
int LatestEnd[Tasks] = ...;   // Latest end time for each task
int TaskType[Tasks] = ...;

// Mapping of workers and tasks they are able to do
tuple Skill {
  string worker;
  string task; 
};
{Skill} Skills = ...;


// Interval variable that has one per each task
dvar interval tasks[t in Tasks] in 0..H size Durations[t];
// Interval variable that goes through mapping of tasks/workers and assigns (unassigned will be zero interval)
dvar interval wtasks[s in Skills] optional;

// define an optional array of interval variables for each worker
dvar interval busyTime[w in Workers][s in Skills] optional;

// the sequence of tasks for each worker (the chart we normally look at)
dvar sequence busyTimes[w in Workers] in all(s in Skills: s.worker == w) busyTime[w][s] types all(s in Skills: s.worker == w) TaskType[s.task];

// This will grab the start of the next interval
dexpr int nextIntervalStart[w in Workers][s in Skills] = presenceOf(busyTime[w][s])*startOfNext(busyTimes[w], busyTime[w][s], H);
dexpr int prevIntervalEnd[w in Workers][s in Skills] = presenceOf(busyTime[w][s])*endOfPrev(busyTimes[w], busyTime[w][s], 0);
dexpr int endOfTask[s in Skills] = endOf(busyTime[s.worker][s]);
// dexpr int startOfFirst[w in Workers][s in Skills] = (endOfPrev(busyTimes[w], busyTime[w][s], 0) == 0) * (startOf(busyTime[w][s]));


// for each worker, calculate all break starts
dexpr int breakStarts[w in Workers][s in Skills] = (s.worker == w)*presenceOf(wtasks[s])*(TaskType[s.task] == 1)*startOf(wtasks[s]);

// calculate the difference between each break and the end of each task
dexpr int trueBreakDifference[s in Skills][sk in Skills] = (breakStarts[sk.worker][sk] - endOf(wtasks[s]))
	* ((breakStarts[sk.worker][sk] - endOf(wtasks[s])) >= 0)
	* (TaskType[s.task] != 1)
	* (s.worker == sk.worker);

// set break difference greater than horizon if no difference to avoid incorrect minimum status
dexpr int breakDifference[s in Skills][sk in Skills] = 
	  ((((trueBreakDifference[s][sk] == 0) && (typeOfNext(busyTimes[s.worker], busyTime[s.worker][s], 0) != 1)))*(H+1)) 
	+ ((((trueBreakDifference[s][sk] == 0) && (typeOfNext(busyTimes[s.worker], busyTime[s.worker][s], 0) == 1)
	&& ((startOfNext(busyTimes[s.worker], busyTime[s.worker][s], H) - endOf(wtasks[s])) !=0)))*(H+1))
	+ ((trueBreakDifference[s][sk] != 0) * trueBreakDifference[s][sk]);

dexpr int nextBreakStarts[s in Skills] = sum(ski in Skills:ski.worker == s.worker) 
	(((min(sk in Skills: sk.worker == s.worker) breakDifference[s][sk])==breakDifference[s][ski])
	* (breakDifference[s][ski] <= H)
	* (breakDifference[s][ski] > 0)
	* presenceOf(wtasks[s])
	* (TaskType[s.task] != 1)
	* startOf(wtasks[ski]));
	
dexpr int trueLatestEndsInFront[s in Skills][sk in Skills] = 
	  ((1 - ((startOf(wtasks[sk]) >= startOf(wtasks[s]))
	* (endOf(wtasks[sk]) <= nextBreakStarts[s])
	* (presenceOf(wtasks[s])
	* presenceOf(wtasks[sk]))
	* (TaskType[sk.task] != 1)
	* (s.worker == sk.worker))) * (H+1)
	+ LatestEnd[sk.task])
	* (TaskType[s.task] != 1);
//	
dexpr int slidingConstraint[s in Skills] = presenceOf(wtasks[s])
	* minl(nextBreakStarts[s],min(sk in Skills) minl(trueLatestEndsInFront[s][sk], LatestEnd[s.task]));
	
	
dexpr int tasksInFront[s in Skills] = sum(sk in Skills: sk.worker == s.worker) 
	  ((startOf(wtasks[sk]) >= endOf(wtasks[s]))
	* (startOf(wtasks[sk]) < slidingConstraint[s])
	* presenceOf(wtasks[s])
	* presenceOf(wtasks[sk])
	* (TaskType[s.task] != 1)
	* (TaskType[sk.task] != 1)
	* (s != sk)
	* Durations[sk.task]);
//	* (minl(slidingConstraint[s], endOf(wtasks[sk])) - startOf(wtasks[s])));
	
//dexpr int tasksInFrontToBreak[s in Skills] = sum(sk in Skills: sk.worker == s.worker) 
//	 ((startOf(wtasks[sk]) >= startOf(wtasks[s]))
//	* (startOf(wtasks[sk]) < nextBreakStarts[s])
//	* (presenceOf(wtasks[s]) && presenceOf(wtasks[sk]))
//	* ((TaskType[s.task] != 1) && (TaskType[sk.task] != 1))
//	* (s != sk)
//	* (minl(nextBreakStarts[s], endOf(wtasks[sk])) - startOf(wtasks[s])));
	
dexpr int forwardSlack[s in Skills] = presenceOf(wtasks[s])
	* (minl(slidingConstraint[s], LatestEnd[s.task]) - (tasksInFront[s] + endOf(wtasks[s])))
	* (nextBreakStarts[s] > 0);
	
dexpr int individualSlotSlack[s in Skills][sk in Skills] = 	(((minl(nextIntervalStart[sk.worker][sk],LatestEnd[s.task]) 
 	- maxl(endOfTask[sk], EarliestStart[s.task])) - Durations[s.task] + 1)
	* ((Durations[s.task] <= (minl(nextIntervalStart[sk.worker][sk],LatestEnd[s.task]) - maxl(endOfTask[sk], EarliestStart[s.task])))
	&& (sk != s)));

dexpr int slotSlack[s in Skills] = presenceOf(wtasks[s])* sum(ski in Skills: ski.task == s.task) sum(sk in Skills: sk.worker == ski.worker) individualSlotSlack[s][sk];  
// Consider if we need to count before slack for first task for each worker
// dexpr int swapSpace[s in Skills][sk in Skills] = (minl(nextIntervalStart[sk.worker][sk], LatestEnd[s.task]) - maxl(prevIntervalEnd[sk.worker][sk], EarliestStart[s.task]));


//commented work for getting swap slack
//Need a value that sums over any worker who can do a task so we can find the max slack task in the set of all workers who can do task
//dexpr int tasksToDropSlack[s in Skills][sk in Skills] = (forwardSlack[sk]+slotSlack[sk])
//	* (swapSpace[s][sk] >= Durations[s.task])
//	* ((sum(ski in Skills: ski.task == s.task) (ski.worker == sk.worker)) >= 1)
//	* presenceOf(wtasks[s])
//	* (s != sk);
//
//dexpr int leftShiftWindow[s in Skills][sk in Skills] = minl(nextIntervalStart[sk.worker][sk], LatestEnd[sk.task])
//	- maxl(EarliestStart[s.task], prevIntervalEnd[sk.worker][sk])
//	+ Durations[s.task];
//													 
//dexpr int rightShiftWindow[s in Skills][sk in Skills] = minl(LatestEnd[s.task], nextIntervalStart[sk.worker][sk])
//	- Durations[s.task]
//	- maxl(EarliestStart[sk.task], prevIntervalEnd[sk.worker][sk]);
//	
//dexpr int taskToDrop[s in Skills] = sum(sk in Skills) ((max(ski in Skills) tasksToDropSlack[s][ski]) == totalSlack[sk])
//	*swapSpace[s][sk]
//	*((slotSlack[sk] > 0) || (leftShiftWindow[s][sk] >= Durations[sk.task]) || (rightShiftWindow[s][sk] >= Durations[sk.task]));
//	


maximize sum(s in Skills) (slotSlack[s] + forwardSlack[s]);

subject to {
  forall(t in Tasks) {
    // if tasks[t] is present in the solution, then exactly one of the interval variables in wtasks[s] will be present, and tasks[t] starts and ends together with this chosen interval.
    alternative(tasks[t], all(s in Skills: s.task==t) wtasks[s]); 
    // stay within bounds of task window
    endOf(tasks[t]) <= LatestEnd[t];
    startOf(tasks[t]) >= EarliestStart[t];
    endOf(tasks[t]) - startOf(tasks[t]) >= Durations[t];   
  }
  // No overlap for the workers
  forall(w in Workers) {
    noOverlap(all(s in Skills: s.worker==w) wtasks[s]);
    noOverlap(busyTimes[w]);
    forall(s in Skills: s.worker == w){
      // constrain worker intervals to align with wtasks
      startOf(busyTime[w][s]) == startOf(wtasks[s]);
      endOf(busyTime[w][s]) == endOf(wtasks[s]);
    }
  } 

};

execute {
		cp.param.FailLimit = 10000;
		var f = new IloOplOutputFile("solution.csv");
		f.writeln("Worker,Task,TaskType,Start,End,Forward Slack,Slot Slack,Sliding Constraint");
		for(s in Skills)
			f.writeln(s.worker,",",s.task,",",TaskType[s.task],",",wtasks[s].start,",",wtasks[s].end,",",forwardSlack[s],",",slotSlack[s],",",slidingConstraint[s]);	
		f.close()		
}
